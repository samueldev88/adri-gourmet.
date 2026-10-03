from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from orders.models import Order

from . import rules
from .models import Redemption
from .services import (MY_ORDERS_SESSION_KEY, InsufficientPoints, RewardUnavailable,
                       get_session_customer, redeem_reward, reward_progress)


def home(request):
    saved, account = get_session_customer(request)
    tiers = [(int(t), b) for t, b in rules.BONUS_TIERS]

    if not saved:
        return render(request, "loyalty/home.html", {"identified": False, "tiers": tiers})

    balance = account.balance if account else 0
    rewards, next_reward = reward_progress(balance)
    transactions = list(account.transactions.all()[:15]) if account else []
    pending = list(account.redemptions.filter(status=Redemption.PENDING)[:5]) if account else []

    return render(request, "loyalty/home.html", {
        "identified": True,
        "saved": saved,
        "first_name": (saved.get("name") or "").split(" ")[0],
        "balance": balance,
        "rewards": rewards,
        "next_reward": next_reward,
        "transactions": transactions,
        "pending": pending,
        "tiers": tiers,
    })


@require_POST
def redeem(request, reward_id):
    saved, account = get_session_customer(request)
    if not saved or not account:
        messages.error(request, "Você ainda não tem pontos para resgatar.")
        return redirect("loyalty:home")

    # Segurança: só resgata quem fez pedido com este telefone NESTE aparelho.
    ids = request.session.get(MY_ORDERS_SESSION_KEY, [])
    if not Order.objects.filter(id__in=ids, customer_phone=saved["phone"]).exists():
        messages.error(request, "Por segurança, o resgate só pode ser feito no aparelho em que você fez um pedido com este telefone.")
        return redirect("loyalty:home")

    try:
        redemption = redeem_reward(account.pk, reward_id)
    except InsufficientPoints:
        messages.error(request, "Você ainda não tem pontos suficientes para essa recompensa.")
    except RewardUnavailable:
        messages.error(request, "Essa recompensa não está disponível no momento.")
    else:
        messages.success(
            request,
            f"🎉 Resgate feito: {redemption.reward_name}! Mostre o código {redemption.code} para a loja.",
        )
    return redirect("loyalty:home")
