from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order

from .services import credit_order_points


@receiver(post_save, sender=Order, dispatch_uid="loyalty_credit_when_confirmed")
def credit_points_when_confirmed(sender, instance, **kwargs):
    """Quando o pedido passa para um status confirmado (ex.: pago), credita os pontos."""
    confirmed = getattr(settings, "LOYALTY_CONFIRMED_STATUSES", ("pago",))
    if instance.status in confirmed:
        transaction.on_commit(lambda: credit_order_points(instance))
