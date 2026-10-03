from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Discount


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "category", "price", "current_price_display", "stock_display", "active")
    list_filter = ("category", "active")
    list_editable = ("active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("stock_info",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").prefetch_related("discounts")
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description", "image")}),
        ("Preço e visibilidade", {"fields": ("price", "active")}),
        ("Estoque", {
            "fields": ("stock_info",),
            "description": (
                "O estoque não é editado diretamente aqui. Vá em "
                "Inventário → Movimentações de estoque para registrar uma "
                "entrada, saída ou ajuste — isso mantém o histórico completo."
            ),
        }),
    )

    @admin.display(description="foto")
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:4px;" />', obj.image.url)
        return "—"

    @admin.display(description="preço com desconto")
    def current_price_display(self, obj):
        current = obj.current_price()
        if obj.has_discount():
            return format_html(
                '<span style="color:#b45309;font-weight:600;">R$ {}</span> '
                '<span style="text-decoration:line-through;color:#999;">R$ {}</span>',
                f"{current:.2f}", f"{obj.price:.2f}",
            )
        return f"R$ {current:.2f}"

    @admin.display(description="estoque")
    def stock_display(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color:#b91c1c;font-weight:600;">esgotado</span>')
        if obj.stock <= 5:
            return format_html('<span style="color:#b45309;">{} (baixo)</span>', obj.stock)
        return obj.stock

    @admin.display(description="estoque atual")
    def stock_info(self, obj):
        if not obj.pk:
            return "Salve o produto primeiro; depois registre a entrada inicial em Movimentações de estoque."
        return f"{obj.stock} unidade(s) em estoque"


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "value_display", "active", "starts_at", "ends_at", "product_count")
    list_filter = ("active",)
    filter_horizontal = ("products",)

    @admin.display(description="tipo")
    def kind(self, obj):
        return "Percentual" if obj.percentage else "Valor fixo"

    @admin.display(description="valor")
    def value_display(self, obj):
        if obj.percentage:
            clean = f"{obj.percentage:.2f}".rstrip("0").rstrip(".")
            return f"{clean}%"
        return f"R$ {obj.fixed_value:.2f}"

    @admin.display(description="produtos")
    def product_count(self, obj):
        return obj.products.count()
