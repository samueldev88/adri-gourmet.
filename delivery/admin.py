from django.contrib import admin
from .models import DeliveryMessage


@admin.register(DeliveryMessage)
class DeliveryMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "phone", "cep", "distance_km", "attended")
    list_filter = ("attended",)
    list_editable = ("attended",)
    search_fields = ("name", "phone", "cep")
