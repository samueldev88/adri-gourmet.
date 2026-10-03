from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import LoyaltyAccount, PointsTransaction, Redemption, Reward
from .services import adjust_points, cancel_redemption, mark_delivered


class PointsTransactionInline(admin.TabularInline):
    model = PointsTransaction
    extra = 0
    can_delete = False
    fields = ("created_at", "kind", "points", "description", "order", "balance_after")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "balance", "created_at")
    search_fields = ("name", "phone")
    readonly_fields = ("balance", "created_at", "updated_at")
    inlines = [PointsTransactionInline]


class AdjustForm(forms.ModelForm):
    class Meta:
        model = PointsTransaction
        fields = ("account", "points", "description")

    def clean(self):
        data = super().clean()
        account, points = data.get("account"), data.get("points")
        if account and points is not None:
            if points == 0:
                raise forms.ValidationError("Informe um valor diferente de zero.")
            if account.balance + points < 0:
                raise forms.ValidationError("O saldo do cliente ficaria negativo.")
        return data


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    """Histórico (somente leitura). 'Adicionar' serve para ajustes manuais de pontos."""
    list_display = ("created_at", "account", "kind", "signed_points", "description", "order",
                    "base_points", "bonus_points", "balance_after")
    list_filter = ("kind", "created_at")
    search_fields = ("account__name", "account__phone", "description")
    date_hierarchy = "created_at"

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AdjustForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("account", "points", "description")
        return ("account", "kind", "points", "base_points", "bonus_points", "balance_after",
                "description", "order", "redemption", "created_at")

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else ()

    def save_model(self, request, obj, form, change):
        if change:
            return
        tx = adjust_points(obj.account, obj.points, obj.description)
        obj.pk = tx.pk

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    fields = ("product", "name", "emoji", "points_cost", "active", "position")
    list_display = ("thumb", "nome", "points_cost", "active", "position")
    list_display_links = ("thumb", "nome")
    list_editable = ("points_cost", "active", "position")

    @admin.display(description="Foto")
    def thumb(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" alt="" style="height:38px;width:38px;object-fit:cover;border-radius:8px">',
                obj.image_url,
            )
        return obj.emoji or "—"

    @admin.display(description="Recompensa")
    def nome(self, obj):
        return obj.display_name


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ("code", "account", "reward_name", "points_spent", "status", "created_at", "delivered_at")
    list_filter = ("status", "created_at")
    search_fields = ("code", "account__name", "account__phone")
    readonly_fields = ("account", "reward", "reward_name", "points_spent", "code", "status",
                       "created_at", "delivered_at")
    actions = ["action_mark_delivered", "action_cancel_and_refund"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Marcar como entregue")
    def action_mark_delivered(self, request, queryset):
        n = sum(mark_delivered(r) for r in queryset)
        self.message_user(request, f"{n} resgate(s) marcado(s) como entregue(s).", messages.SUCCESS)

    @admin.action(description="Cancelar e devolver os pontos")
    def action_cancel_and_refund(self, request, queryset):
        n = sum(cancel_redemption(r.pk) for r in queryset)
        self.message_user(request, f"{n} resgate(s) cancelado(s) e pontos devolvidos.", messages.SUCCESS)