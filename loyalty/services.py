"""Toda a lógica que mexe em pontos fica aqui (nunca no navegador)."""
import re
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import rules
from .models import LoyaltyAccount, PointsTransaction, Redemption, Reward

# Devem ser iguais às chaves usadas em orders/views.py
CUSTOMER_SESSION_KEY = "checkout_customer"
MY_ORDERS_SESSION_KEY = "my_order_ids"

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class InsufficientPoints(Exception):
    pass


class RewardUnavailable(Exception):
    pass


def normalize_phone(phone):
    return re.sub(r"\D", "", phone or "")


def get_session_customer(request):
    """(dados_da_sessão, conta) do cliente identificado neste aparelho."""
    saved = request.session.get(CUSTOMER_SESSION_KEY)
    if not saved or not saved.get("phone"):
        return None, None
    account = LoyaltyAccount.objects.filter(phone=normalize_phone(saved["phone"])).first()
    return saved, account


def reward_progress(balance):
    """Recompensas ativas com 'affordable', 'missing', 'percent' + a próxima a conquistar."""
    rewards = list(Reward.objects.filter(active=True).select_related("product"))
    for r in rewards:
        r.affordable = balance >= r.points_cost
        r.missing = max(r.points_cost - balance, 0)
        r.percent = min(100, int(balance * 100 / r.points_cost))
    next_reward = next((r for r in rewards if not r.affordable), None)
    return rewards, next_reward


def _lock_account(account_id):
    return LoyaltyAccount.objects.select_for_update().get(pk=account_id)


@transaction.atomic
def credit_order_points(order):
    """Credita os pontos de um pedido confirmado. Seguro para chamar várias vezes:
    o mesmo pedido nunca gera pontos duas vezes. Retorna a movimentação ou None."""
    phone = normalize_phone(order.customer_phone)
    if not phone:
        return None

    account, _ = LoyaltyAccount.objects.get_or_create(phone=phone, defaults={"name": order.customer_name or ""})
    account = _lock_account(account.pk)

    if PointsTransaction.objects.filter(order=order, kind=PointsTransaction.EARN).exists():
        return None

    base, bonus = rules.calculate_points(order.total)
    total_points = base + bonus
    if total_points <= 0:
        return None

    try:
        with transaction.atomic():
            tx = PointsTransaction.objects.create(
                account=account,
                kind=PointsTransaction.EARN,
                points=total_points,
                base_points=base,
                bonus_points=bonus,
                balance_after=account.balance + total_points,
                description=f"Pedido #{order.pk}",
                order=order,
            )
    except IntegrityError:  # outro processo creditou no mesmo instante
        return None

    account.balance += total_points
    if order.customer_name and not account.name:
        account.name = order.customer_name
    account.save()
    return tx


@transaction.atomic
def redeem_reward(account_id, reward_id):
    """Troca pontos por uma recompensa. Desconta o saldo e registra o histórico."""
    account = _lock_account(account_id)
    try:
        reward = Reward.objects.get(pk=reward_id, active=True)
    except Reward.DoesNotExist:
        raise RewardUnavailable()

    if account.balance < reward.points_cost:
        raise InsufficientPoints()

    account.balance -= reward.points_cost
    account.save()

    redemption = Redemption.objects.create(
        account=account,
        reward=reward,
        reward_name=reward.display_name,
        points_spent=reward.points_cost,
        code=_generate_code(),
    )
    PointsTransaction.objects.create(
        account=account,
        kind=PointsTransaction.REDEEM,
        points=-reward.points_cost,
        balance_after=account.balance,
        description=f"Resgate: 1 {reward.display_name}",
        redemption=redemption,
    )
    return redemption


@transaction.atomic
def cancel_redemption(redemption_id):
    """Cancela um resgate pendente e devolve os pontos."""
    redemption = Redemption.objects.select_for_update().get(pk=redemption_id)
    if redemption.status != Redemption.PENDING:
        return False
    account = _lock_account(redemption.account_id)
    account.balance += redemption.points_spent
    account.save()
    PointsTransaction.objects.create(
        account=account,
        kind=PointsTransaction.REFUND,
        points=redemption.points_spent,
        balance_after=account.balance,
        description=f"Estorno: resgate {redemption.code} ({redemption.reward_name})",
        redemption=redemption,
    )
    redemption.status = Redemption.CANCELED
    redemption.save(update_fields=["status"])
    return True


def mark_delivered(redemption):
    if redemption.status == Redemption.PENDING:
        redemption.status = Redemption.DELIVERED
        redemption.delivered_at = timezone.now()
        redemption.save(update_fields=["status", "delivered_at"])
        return True
    return False


@transaction.atomic
def adjust_points(account, points, description=""):
    """Ajuste manual feito pelo admin (positivo ou negativo)."""
    account = _lock_account(account.pk)
    if account.balance + points < 0:
        raise ValueError("O saldo ficaria negativo.")
    account.balance += points
    account.save()
    return PointsTransaction.objects.create(
        account=account,
        kind=PointsTransaction.ADJUST,
        points=points,
        balance_after=account.balance,
        description=description or "Ajuste manual",
    )


def _generate_code():
    for _ in range(30):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if not Redemption.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Não foi possível gerar um código único.")   