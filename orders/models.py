from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.signals import post_save
from django.dispatch import receiver


class Order(models.Model):
    DELIVERY_CHOICES = [
        ("retirada", "Retirar na loja"),
        ("entrega", "Entrega"),
    ]
    STATUS_CHOICES = [
        ("aguardando_pagamento", "Aguardando pagamento"),
        ("pago", "Pago"),
        ("preparando", "Preparando"),
        ("saiu_para_entrega", "Saiu para entrega"),
        ("concluido", "Concluído / entregue"),
        ("cancelado", "Cancelado"),
    ]

    customer_name = models.CharField("nome do cliente", max_length=100)
    customer_phone = models.CharField("telefone/WhatsApp", max_length=20)
    customer_birth_date = models.DateField("data de nascimento", null=True, blank=True)

    delivery_type = models.CharField("tipo", max_length=10, choices=DELIVERY_CHOICES, default="retirada")
    cep = models.CharField("CEP", max_length=9, blank=True)
    address_text = models.CharField("endereço", max_length=255, blank=True)
    address_complement = models.CharField("complemento", max_length=100, blank=True)
    distance_km = models.DecimalField("distância (km)", max_digits=6, decimal_places=2, null=True, blank=True)

    status = models.CharField("status", max_length=25, choices=STATUS_CHOICES, default="aguardando_pagamento")
    total = models.DecimalField("total", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    payment_id = models.CharField("ID do pagamento (Mercado Pago)", max_length=100, blank=True)
    payment_preference_id = models.CharField("ID da preferência (Mercado Pago)", max_length=100, blank=True)

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.pk} — {self.customer_name}"

    def mark_as_paid(self, payment_id: str):
        self.status = "pago"
        self.payment_id = payment_id
        self.save(update_fields=["status", "payment_id", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="pedido")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, verbose_name="produto")
    quantity = models.PositiveIntegerField("quantidade")
    # "Congelamos" o preço no momento da compra: se o produto mudar de preço
    # ou o desconto expirar depois, pedidos já feitos não são afetados.
    unit_price = models.DecimalField("preço unitário (no momento da compra)", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


# ====================================================================
# Programa de pontos
# ====================================================================
class Customer(models.Model):
    """Cliente identificado pelo telefone (mesmo formato salvo no pedido)."""
    phone = models.CharField("telefone", max_length=20, unique=True)
    name = models.CharField("nome", max_length=100)
    birth_date = models.DateField("nascimento", null=True, blank=True)
    created_at = models.DateTimeField("cliente desde", auto_now_add=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def points(self) -> int:
        """Saldo = soma do extrato (ganhos positivos, resgates negativos)."""
        return self.entries.aggregate(total=Sum("points"))["total"] or 0


class PointsEntry(models.Model):
    """Extrato de pontos: cada linha é um ganho ou um gasto."""
    EARN, REDEEM, REVOKE, ADJUST = "earn", "redeem", "revoke", "adjust"
    KIND_CHOICES = [
        (EARN, "Compra"),
        (REDEEM, "Troca por brinde"),
        (REVOKE, "Pedido cancelado"),
        (ADJUST, "Ajuste manual"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="entries", verbose_name="cliente")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="points_entries", verbose_name="pedido")
    kind = models.CharField("tipo", max_length=10, choices=KIND_CHOICES)
    points = models.IntegerField("pontos", help_text="Positivo ganha, negativo gasta.")
    note = models.CharField("observação", max_length=200, blank=True)
    created_at = models.DateTimeField("data", auto_now_add=True)

    class Meta:
        verbose_name = "lançamento de pontos"
        verbose_name_plural = "extrato de pontos"
        ordering = ["-created_at", "-id"]
        constraints = [
            # O banco garante: um pedido só ganha ponto uma vez e só é estornado uma vez.
            models.UniqueConstraint(fields=["order"], condition=Q(kind="earn"), name="uniq_earn_per_order"),
            models.UniqueConstraint(fields=["order"], condition=Q(kind="revoke"), name="uniq_revoke_per_order"),
        ]

    def __str__(self):
        return f"{self.customer.name}: {self.points:+d} ({self.get_kind_display()})"


PAID_STATUSES = {"pago", "preparando", "saiu_para_entrega", "concluido"}


@receiver(post_save, sender=Order)
def sync_points(sender, instance, **kwargs):
    """Dá 1 ponto quando o pedido fica pago (webhook, admin, etc.) e estorna se cancelar."""
    if not instance.customer_phone:
        return
    if instance.status in PAID_STATUSES:
        points = getattr(settings, "LOYALTY_POINTS_PER_ORDER", 1)
        if points <= 0:
            return
        with transaction.atomic():
            customer, created = Customer.objects.get_or_create(
                phone=instance.customer_phone,
                defaults={"name": instance.customer_name, "birth_date": instance.customer_birth_date},
            )
            if not created and not customer.birth_date and instance.customer_birth_date:
                customer.birth_date = instance.customer_birth_date
                customer.save(update_fields=["birth_date"])
            PointsEntry.objects.get_or_create(
                order=instance, kind=PointsEntry.EARN,
                defaults={"customer": customer, "points": points, "note": f"Pedido #{instance.pk}"},
            )
    elif instance.status == "cancelado":
        earned = PointsEntry.objects.filter(order=instance, kind=PointsEntry.EARN).first()
        if earned:
            PointsEntry.objects.get_or_create(
                order=instance, kind=PointsEntry.REVOKE,
                defaults={"customer": earned.customer, "points": -earned.points,
                          "note": f"Pedido #{instance.pk} cancelado"},
            )