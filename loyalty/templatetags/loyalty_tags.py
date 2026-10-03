from decimal import Decimal

from django import template

from .. import rules
from ..services import get_session_customer, reward_progress

register = template.Library()


@register.inclusion_tag("loyalty/_bonus_hint.html")
def loyalty_bonus_hint(cart):
    """Mensagem de incentivo de bônus. Uso: {% loyalty_bonus_hint cart %}"""
    total = Decimal("0")
    try:
        for item in cart:
            total += rules.to_decimal(item["subtotal"])
    except TypeError:
        pass

    base, bonus = rules.calculate_points(total)
    nxt = rules.next_tier(total)
    ctx = {"show": total > 0, "unlocked": bonus > 0, "bonus": bonus, "points": base + bonus, "next_tier": nxt}
    if nxt:
        threshold, next_bonus = nxt
        ctx.update(
            missing=threshold - total,
            next_bonus=next_bonus,
            percent=min(99, int(total * 100 / threshold)),
        )
    return ctx


@register.inclusion_tag("loyalty/_summary_card.html", takes_context=True)
def loyalty_summary(context):
    """Cartão resumido de pontos (para o perfil). Uso: {% loyalty_summary %}"""
    request = context["request"]
    saved, account = get_session_customer(request)
    balance = account.balance if account else 0
    _, next_reward = reward_progress(balance)
    return {"identified": bool(saved), "balance": balance, "next_reward": next_reward}
