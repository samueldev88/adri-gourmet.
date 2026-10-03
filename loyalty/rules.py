"""Regras do programa de pontos. Tudo é calculado aqui, no servidor."""
from decimal import Decimal

# (valor mínimo do pedido, pontos de bônus) — em ordem crescente.
# Os bônus NÃO são acumulativos: vale só a maior faixa atingida.
BONUS_TIERS = (
    (Decimal("50"), 20),
    (Decimal("80"), 40),
    (Decimal("120"), 70),
)


def to_decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def base_points(total):
    """R$1 gasto = 1 ponto (centavos não contam)."""
    return int(to_decimal(total))


def bonus_points(total):
    total = to_decimal(total)
    bonus = 0
    for threshold, value in BONUS_TIERS:
        if total >= threshold:
            bonus = value
    return bonus


def calculate_points(total):
    """Retorna (pontos_base, pontos_bonus)."""
    return base_points(total), bonus_points(total)


def next_tier(total):
    """Próxima faixa de bônus ainda não atingida: (valor, bônus) ou None."""
    total = to_decimal(total)
    for threshold, value in BONUS_TIERS:
        if total < threshold:
            return threshold, value
    return None
