from django.contrib import admin
from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "quantity", "reason", "order", "note")
    list_filter = ("reason", "created_at")
    search_fields = ("product__name", "note")
    autocomplete_fields = ("product",)
    date_hierarchy = "created_at"

    def has_change_permission(self, request, obj=None):
        # Movimentação é um registro histórico — não deve ser editada depois de criada.
        return False
