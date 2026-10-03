"""
Integração com o Mercado Pago usando o Checkout Pro (a pessoa é
redirecionada para uma página de pagamento hospedada pelo Mercado Pago —
não precisamos lidar com dados de cartão diretamente, o que evita boa
parte da dor de cabeça de segurança/PCI).
"""
import logging

import mercadopago
from django.conf import settings
from django.urls import reverse

from inventory.services import adjust_stock, InsufficientStockError

logger = logging.getLogger(__name__)


def _sdk():
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        return None
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def create_preference(order, request):
    """
    Cria a "preferência de pagamento" no Mercado Pago para um pedido.
    Devolve None se as credenciais não estiverem configuradas (útil em
    desenvolvimento, sem travar o fluxo).
    """
    sdk = _sdk()
    if sdk is None:
        logger.warning("MERCADOPAGO_ACCESS_TOKEN não configurado — pagamento pulado.")
        return None

    site_url = settings.SITE_URL.rstrip("/")

    items = [
        {
            "title": item.product.name,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "currency_id": "BRL",
        }
        for item in order.items.select_related("product")
    ]

    preference_data = {
        "items": items,
        "payer": {"name": order.customer_name},
        "external_reference": str(order.id),
        "back_urls": {
            "success": f"{site_url}{reverse('orders:confirmation', args=[order.id])}",
            "pending": f"{site_url}{reverse('orders:confirmation', args=[order.id])}",
            "failure": f"{site_url}{reverse('orders:confirmation', args=[order.id])}",
        },
        "auto_return": "approved",
        "notification_url": f"{site_url}{reverse('payments:webhook')}",
    }

    response = sdk.preference().create(preference_data)
    preference = response.get("response", {})

    order.payment_preference_id = preference.get("id", "")
    order.save(update_fields=["payment_preference_id", "updated_at"])

    return preference


def fetch_payment(payment_id: str) -> dict:
    sdk = _sdk()
    if sdk is None:
        return {}
    response = sdk.payment().get(payment_id)
    return response.get("response", {})


def confirm_order_payment(order, payment_id: str):
    """
    Chamado quando o webhook confirma que o pagamento foi aprovado.
    É seguro chamar mais de uma vez para o mesmo pedido (o Mercado Pago
    pode reenviar a notificação) — só processa se ainda não tiver pago.
    """
    if order.status == "pago":
        return  # já processado antes; evita dar baixa de estoque duas vezes

    order.mark_as_paid(payment_id)

    for item in order.items.select_related("product"):
        try:
            adjust_stock(
                item.product, quantity_delta=-item.quantity,
                reason="venda", order=order,
                note=f"Venda referente ao pedido #{order.id}",
            )
        except InsufficientStockError:
            # Não deveria acontecer (já checamos no checkout), mas se
            # acontecer não queremos que o estoque fique negativo — loga
            # para o lojista resolver manualmente.
            logger.error("Estoque insuficiente ao confirmar pedido #%s, produto %s", order.id, item.product.name)

    notify_new_order(order)


def notify_new_order(order):
    """
    Ponto de extensão: chame aqui a notificação que a loja quiser receber
    quando um pedido novo é pago (Telegram, WhatsApp Business API, e-mail...).
    Por padrão só registra no log.
    """
    logger.info("Novo pedido pago: #%s — %s — R$ %s", order.id, order.customer_name, order.total)
