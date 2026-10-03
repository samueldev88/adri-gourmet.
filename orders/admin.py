from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_phone", "delivery_type", "status", "total", "created_at")
    list_filter = ("status", "delivery_type", "created_at")
    search_fields = ("customer_name", "customer_phone", "payment_id")
    readonly_fields = (
        "customer_name", "customer_phone", "delivery_type", "cep", "address_text",
        "address_complement", "distance_km", "total", "payment_id", "payment_preference_id",
        "created_at", "updated_at",
    )
    list_editable = ("status",)
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"

from django.conf import settings
from django.contrib import admin, messages

from .models import Customer, PointsEntry

class PointsEntryInline(admin.TabularInline):
    model = PointsEntry
    extra = 0
    fields = ("created_at", "kind", "points", "order", "note")
    readonly_fields = ("created_at",)
    raw_id_fields = ("order",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "points_balance", "birth_date")
    search_fields = ("name", "phone")
    inlines = [PointsEntryInline]
    actions = ["redeem_reward"]

    @admin.display(description="Pontos")
    def points_balance(self, obj):
        return obj.points

    @admin.action(description="Resgatar brinde (descontar os pontos da troca)")
    def redeem_reward(self, request, queryset):
        cost = getattr(settings, "LOYALTY_REWARD_POINTS", 10)
        for customer in queryset:
            if customer.points >= cost:
                PointsEntry.objects.create(customer=customer, kind=PointsEntry.REDEEM,
                                           points=-cost, note="Troca por comida grátis")
                self.message_user(request, f"Resgate registrado: {customer.name}.", messages.SUCCESS)
            else:
                self.message_user(request, f"{customer.name} tem só {customer.points} ponto(s); precisa de {cost}.",
                                  messages.WARNING)