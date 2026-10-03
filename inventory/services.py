from django.db import transaction
from django.core.exceptions import ValidationError
from catalog.models import Product
from .models import StockMovement


class InsufficientStockError(Exception):
    """Não há estoque suficiente do produto para completar a operação."""


@transaction.atomic
def adjust_stock(product: Product, quantity_delta: int, reason: str, order=None, note: str = "") -> StockMovement:
    """
    Único ponto do sistema autorizado a mudar Product.stock.
    Bloqueia a linha do produto (select_for_update) para evitar que duas
    vendas simultâneas vendam a mesma última unidade.
    """
    locked_product = Product.objects.select_for_update().get(pk=product.pk)

    new_stock = locked_product.stock + quantity_delta
    if new_stock < 0:
        raise InsufficientStockError(
            f'Estoque insuficiente de "{locked_product.name}": '
            f"tem {locked_product.stock}, pediram {abs(quantity_delta)}."
        )

    locked_product.stock = new_stock
    locked_product.save(update_fields=["stock", "updated_at"])

    return StockMovement.objects.create(
        product=locked_product, quantity=quantity_delta, reason=reason, order=order, note=note,
    )
