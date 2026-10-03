"""Monta o resumo do pedido (formatado para WhatsApp) e o link wa.me."""
import re
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

DIVIDER = "━━━━━━━━━━━━━━━"


def _brl(value) -> str:
    value = Decimal(value).quantize(Decimal("0.01"))
    text = f"{value:,.2f}"  # 1,234.56
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def build_order_message(order) -> str:
    paid = order.status not in ("aguardando_pagamento", "cancelado")
    lines = [
        f"🧾 *PEDIDO #{order.pk}*",
        "_Adriê Gourmet_",
        DIVIDER,
        "👤 *Cliente*",
        order.customer_name,
        f"📱 {order.customer_phone}",
        "",
        "🛍️ *Itens*",
    ]
    for item in order.items.select_related("product"):
        lines.append(f"▪️ {item.quantity}x {item.product.name} — {_brl(item.subtotal)}")

    lines += [
        "",
        DIVIDER,
        f"💰 *Total: {_brl(order.total)}*",
        "✅ Pagamento confirmado" if paid else "⏳ Pagamento pendente",
        "",
    ]

    if order.delivery_type == "entrega":
        address = order.address_text
        if order.address_complement:
            address += f" — {order.address_complement}"
        lines += ["🏍️ *Entrega*", address]
        if order.cep:
            lines.append(f"CEP {order.cep}")
        if order.distance_km is not None:
            lines.append(f"📏 {order.distance_km:.1f} km da loja".replace(".", ","))
    else:
        lines.append("🚶 *Retirada no local*")

    lines += ["", f"🕒 {timezone.localtime(order.created_at):%d/%m/%Y às %H:%M}"]
    return "\n".join(lines)


def whatsapp_link(order) -> str:
    number = re.sub(r"\D", "", getattr(settings, "STORE_WHATSAPP", "") or "")
    if not number:
        return ""
    return f"https://wa.me/{number}?text={quote(build_order_message(order), safe='')}"
