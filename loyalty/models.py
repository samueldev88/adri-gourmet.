from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class LoyaltyAccount(models.Model):
    """Conta de pontos do cliente (identificada pelo telefone)."""
    phone = models.CharField("telefone", max_length=20, unique=True, help_text="Somente números.")
    name = models.CharField("nome", max_length=120, blank=True)
    balance = models.PositiveIntegerField("saldo de pontos", default=0)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "cliente (fidelidade)"
        verbose_name_plural = "clientes e pontos"
        ordering = ["-balance", "name"]

    def __str__(self):
        return f"{self.name or 'Sem nome'} ({self.phone})"


class Reward(models.Model):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="loyalty_rewards", verbose_name="produto",
        help_text="Escolha um produto cadastrado: o nome e a foto dele aparecem na recompensa.",
    )
    name = models.CharField("nome", max_length=80, blank=True, help_text="Opcional. Se vazio, usa o nome do produto.")
    emoji = models.CharField("emoji", max_length=8, blank=True, help_text="Usado quando a recompensa não tem produto com foto.")
    points_cost = models.PositiveIntegerField("pontos necessários", validators=[MinValueValidator(1)])
    active = models.BooleanField("ativa", default=True)
    position = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "recompensa"
        verbose_name_plural = "recompensas"
        ordering = ["position", "points_cost"]

    @property
    def display_name(self):
        if self.name:
            return self.name
        return self.product.name if self.product_id else "Recompensa"

    @property
    def image_url(self):
        if self.product_id and getattr(self.product, "image", None):
            try:
                return self.product.image.url
            except ValueError:
                return ""
        return ""

    def clean(self):
        if not self.name and not self.product_id:
            raise ValidationError("Escolha um produto ou informe um nome para a recompensa.")

    def __str__(self):
        return f"{self.display_name} — {self.points_cost} pts"


class Redemption(models.Model):
    PENDING = "pendente"
    DELIVERED = "entregue"
    CANCELED = "cancelado"
    STATUS_CHOICES = [
        (PENDING, "Aguardando entrega"),
        (DELIVERED, "Entregue"),
        (CANCELED, "Cancelado (pontos devolvidos)"),
    ]

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="redemptions", verbose_name="cliente")
    reward = models.ForeignKey(Reward, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="recompensa")
    reward_name = models.CharField("recompensa (nome na hora do resgate)", max_length=120)
    points_spent = models.PositiveIntegerField("pontos gastos")
    code = models.CharField("código", max_length=12, unique=True)
    status = models.CharField("status", max_length=12, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField("resgatado em", auto_now_add=True)
    delivered_at = models.DateTimeField("entregue em", null=True, blank=True)

    class Meta:
        verbose_name = "resgate"
        verbose_name_plural = "resgates"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} — {self.reward_name}"


class PointsTransaction(models.Model):
    EARN = "earn"
    REDEEM = "redeem"
    REFUND = "refund"
    ADJUST = "adjust"
    KIND_CHOICES = [
        (EARN, "Ganho (pedido)"),
        (REDEEM, "Resgate"),
        (REFUND, "Estorno"),
        (ADJUST, "Ajuste manual"),
    ]

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="transactions", verbose_name="cliente")
    kind = models.CharField("tipo", max_length=10, choices=KIND_CHOICES)
    points = models.IntegerField("pontos", help_text="Positivo = ganhou, negativo = gastou.")
    base_points = models.PositiveIntegerField("pontos da compra", default=0)
    bonus_points = models.PositiveIntegerField("pontos de bônus", default=0)
    balance_after = models.PositiveIntegerField("saldo depois", default=0)
    description = models.CharField("descrição", max_length=200)
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="loyalty_transactions", verbose_name="pedido")
    redemption = models.ForeignKey(Redemption, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="transactions", verbose_name="resgate")
    created_at = models.DateTimeField("data", auto_now_add=True)

    class Meta:
        verbose_name = "movimentação de pontos"
        verbose_name_plural = "histórico de pontos"
        ordering = ["-created_at", "-id"]
        constraints = [
            # Garante no banco que um pedido só credita pontos UMA vez.
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(kind="earn"),
                name="loyalty_unique_earn_per_order",
            ),
        ]

    @property
    def signed_points(self):
        return f"+{self.points}" if self.points > 0 else str(self.points)

    def __str__(self):
        return f"{self.signed_points} pts — {self.description}" 