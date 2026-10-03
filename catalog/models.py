from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    name = models.CharField("nome", max_length=100)
    slug = models.SlugField("slug", max_length=110, unique=True, blank=True)
    order = models.PositiveIntegerField("ordem", default=0, help_text="Categorias com número menor aparecem primeiro.")

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Discount(models.Model):
    """
    Uma campanha de desconto aplicada a um conjunto de produtos escolhidos
    (não a todo o catálogo). Pode ser por porcentagem ou por valor fixo,
    e pode ter data de início/fim — ou ficar ativa até ser desligada manualmente.
    """
    name = models.CharField("nome da campanha", max_length=100, help_text='Ex: "Queima de estoque", "Black Friday"')
    products = models.ManyToManyField("catalog.Product", related_name="discounts", verbose_name="produtos")
    percentage = models.DecimalField(
        "percentual de desconto (%)", max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("90"))],
        help_text="Preencha ESSE campo OU o valor fixo abaixo, não os dois.",
    )
    fixed_value = models.DecimalField(
        "valor fixo de desconto (R$)", max_digits=10, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    active = models.BooleanField("ativo", default=True)
    starts_at = models.DateTimeField("início", null=True, blank=True)
    ends_at = models.DateTimeField("fim", null=True, blank=True)

    class Meta:
        verbose_name = "desconto"
        verbose_name_plural = "descontos"

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.percentage and not self.fixed_value:
            raise ValidationError("Preencha o percentual OU o valor fixo de desconto.")
        if self.percentage and self.fixed_value:
            raise ValidationError("Preencha só um dos dois: percentual OU valor fixo, não ambos.")

    def is_valid_now(self):
        if not self.active:
            return False
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    def apply_to(self, price: Decimal) -> Decimal:
        """Retorna o preço já com o desconto aplicado, nunca abaixo de zero."""
        if self.percentage:
            discounted = price - (price * self.percentage / Decimal("100"))
        else:
            discounted = price - self.fixed_value
        return max(discounted, Decimal("0.00"))


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="categoria"
    )
    name = models.CharField("nome", max_length=150)
    slug = models.SlugField("slug", max_length=160, unique=True, blank=True)
    description = models.TextField("descrição", blank=True)
    image = models.ImageField("foto", upload_to="produtos/", blank=True, null=True)
    price = models.DecimalField("preço", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(
        "estoque atual", default=0,
        help_text="Não edite aqui para registrar entrada/saída — use a tela de Movimentações de estoque, que mantém o histórico.",
    )
    active = models.BooleanField("visível na loja", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def in_stock(self):
        return self.stock > 0

    def best_active_discount(self):
        """Entre os descontos válidos agora, devolve o que dá o menor preço final."""
        valid = [d for d in self.discounts.all() if d.is_valid_now()]
        if not valid:
            return None
        return min(valid, key=lambda d: d.apply_to(self.price))

    def current_price(self) -> Decimal:
        discount = self.best_active_discount()
        if discount:
            return discount.apply_to(self.price)
        return self.price

    def has_discount(self) -> bool:
        return self.best_active_discount() is not None

    def discount_percent_label(self):
        """Só para exibir algo como '-20%' no card do produto, mesmo em desconto de valor fixo."""
        discount = self.best_active_discount()
        if not discount:
            return None
        if discount.percentage:
            clean = f"{discount.percentage:.2f}".rstrip("0").rstrip(".")
            return f"-{clean}%"
        pct = (discount.fixed_value / self.price) * 100 if self.price else 0
        return f"-{pct:.0f}%"
