from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete
from django.dispatch import receiver


class StockMovement(models.Model):
    """
    Todo produto que entra ou sai do estoque passa por aqui. Nunca mexemos
    em Product.stock diretamente — isso garante que sempre dá pra ver o
    histórico completo (quem vendeu o quê, quando repôs, etc).
    """
    REASON_CHOICES = [
        ("compra", "Entrada — compra/reposição"),
        ("ajuste", "Ajuste manual"),
        ("venda", "Saída — venda"),
        ("devolucao", "Saída — devolução/perda"),
    ]

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="stock_movements", verbose_name="produto"
    )
    quantity = models.IntegerField(
        "quantidade",
        help_text="Positivo para entrada, negativo para saída. Ex: repor 10 = 10, vender 2 = -2.",
    )
    reason = models.CharField("motivo", max_length=20, choices=REASON_CHOICES)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_movements", verbose_name="pedido relacionado",
    )
    note = models.CharField("observação", max_length=255, blank=True)
    created_at = models.DateTimeField("data", auto_now_add=True)

    class Meta:
        verbose_name = "movimentação de estoque"
        verbose_name_plural = "movimentações de estoque"
        ordering = ["-created_at"]

    def __str__(self):
        sinal = "+" if self.quantity >= 0 else ""
        return f"{self.product.name}: {sinal}{self.quantity} ({self.get_reason_display()})"


@receiver(post_delete, sender=StockMovement)
def recalcular_estoque_ao_apagar(sender, instance, **kwargs):
    from catalog.models import Product
    total = StockMovement.objects.filter(product_id=instance.product_id).aggregate(s=Sum("quantity"))["s"] or 0
    Product.objects.filter(pk=instance.product_id).update(stock=total)