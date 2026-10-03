import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.models import Order
from .services import fetch_payment, confirm_order_payment

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook(request):
    """
    O Mercado Pago chama essa URL sempre que o status de um pagamento
    muda. É a ÚNICA fonte confiável de confirmação de pagamento — nunca
    confiamos apenas na tela de retorno do navegador, porque a pessoa
    pode fechar a aba, cair a internet, etc.
    """
    notification_type = request.GET.get("type") or request.POST.get("type")
    payment_id = request.GET.get("data.id") or request.POST.get("data.id")

    if notification_type != "payment" or not payment_id:
        return HttpResponse(status=200)  # notificação que não nos interessa; confirma o recebimento mesmo assim

    payment = fetch_payment(payment_id)
    if not payment:
        return HttpResponse(status=200)

    if payment.get("status") == "approved":
        order_id = payment.get("external_reference")
        try:
            order = Order.objects.get(id=order_id)
        except (Order.DoesNotExist, ValueError, TypeError):
            logger.warning("Webhook do Mercado Pago referenciou pedido inexistente: %s", order_id)
            return HttpResponse(status=200)

        confirm_order_payment(order, payment_id=str(payment_id))

    return HttpResponse(status=200)
