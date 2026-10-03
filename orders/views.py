import re
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cart.cart import Cart
from delivery.models import DeliveryMessage
from delivery.services import CepLookupError, check_delivery
from loyalty.services import credit_order_points
from payments.services import create_preference

from .checkout_forms import CustomerInfoForm, DeliveryForm, format_cep
from .forms import OutOfRangeMessageForm
from .models import Customer, Order, OrderItem, PointsEntry
from .whatsapp import whatsapp_link

FORA_DA_AREA_SESSION_KEY = "checkout_fora_da_area"
CUSTOMER_SESSION_KEY = "checkout_customer"
MY_ORDERS_SESSION_KEY = "my_order_ids"


def _remember_order(request, order_id):
    ids = request.session.get(MY_ORDERS_SESSION_KEY, [])
    ids.append(order_id)
    request.session[MY_ORDERS_SESSION_KEY] = ids[-20:]


def _subtotal(items):
    return sum((i["subtotal"] for i in items), Decimal("0.00"))


# ---------------------------------------------------------------- passo 1
def customer_info(request):
    """Informações pessoais: telefone, nome e data de nascimento."""
    cart = Cart(request)
    if cart.is_empty():
        messages.info(request, "Sua sacola está vazia.")
        return redirect("cart:detail")

    if request.method == "POST":
        form = CustomerInfoForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            request.session[CUSTOMER_SESSION_KEY] = {
                "phone": d["phone"],
                "name": d["name"],
                "birth_date": d["birth_date"].isoformat(),
            }
            return redirect("orders:checkout")
    else:
        saved = request.session.get(CUSTOMER_SESSION_KEY) or {}
        initial = {"phone": saved.get("phone", ""), "name": saved.get("name", "")}
        try:
            initial["birth_date"] = date.fromisoformat(saved["birth_date"]).strftime("%d/%m/%Y")
        except (KeyError, ValueError):
            initial["birth_date"] = ""
        form = CustomerInfoForm(initial=initial)

    return render(request, "orders/customer_info.html", {"form": form})


# ---------------------------------------------------------------- passo 2
def checkout(request):
    cart = Cart(request)
    if cart.is_empty():
        messages.info(request, "Sua sacola está vazia.")
        return redirect("cart:detail")

    customer = request.session.get(CUSTOMER_SESSION_KEY)
    if not customer:
        return redirect("orders:customer_info")

    items = list(cart)
    subtotal = _subtotal(items)

    def render_page(form):
        return render(request, "orders/checkout.html", {
            "form": form, "items": items, "subtotal": subtotal, "customer": customer,
        })

    if request.method == "POST":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            # Estoque pode ter mudado desde que a pessoa colocou o item na sacola.
            for item in items:
                if item["quantity"] > item["product"].stock:
                    messages.error(
                        request,
                        f'Ih, "{item["product"].name}" não tem mais {item["quantity"]} '
                        f'unidade(s) em estoque (restam {item["product"].stock}). Ajuste a sacola.',
                    )
                    return redirect("cart:detail")

            distance_km = None
            if data["delivery_type"] == "entrega":
                # A validação do raio é refeita aqui, no servidor, a cada pedido.
                try:
                    result = check_delivery(data["cep"])
                except CepLookupError as exc:
                    form.add_error("cep", str(exc))
                    return render_page(form)

                if not result.within_range:
                    request.session[FORA_DA_AREA_SESSION_KEY] = {
                        "name": customer["name"],
                        "phone": customer["phone"],
                        "cep": data["cep"],
                        "distance_km": result.distance_km,
                    }
                    return redirect("orders:leave_message")
                distance_km = result.distance_km

            try:
                birth_date = date.fromisoformat(customer["birth_date"])
            except (KeyError, ValueError):
                birth_date = None

            with transaction.atomic():
                order = Order.objects.create(
                    customer_name=customer["name"],
                    customer_phone=customer["phone"],
                    customer_birth_date=birth_date,
                    delivery_type=data["delivery_type"],
                    cep=format_cep(data["cep"]),
                    address_text=data["address_text"].strip(),
                    address_complement=data["address_complement"].strip(),
                    distance_km=distance_km,
                    total=subtotal,
                )
                OrderItem.objects.bulk_create([
                    OrderItem(order=order, product=i["product"],
                              quantity=i["quantity"], unit_price=i["unit_price"])
                    for i in items
                ])

            _remember_order(request, order.id)
            preference = create_preference(order, request)
            cart.clear()

            if preference is None:
                # Sem credenciais do Mercado Pago (ambiente de desenvolvimento).
                credit_order_points(order)  # sem pagamento online, o pedido já vale pontos
                messages.warning(request, "Pagamento não configurado — pedido criado sem cobrança (modo de teste).")
                return redirect("orders:confirmation", order_id=order.id)

            return redirect(preference["init_point"])
    else:
        mode = request.session.get("delivery_mode")
        initial = {"delivery_type": mode if mode in ("entrega", "retirada") else "retirada"}
        if mode == "entrega" and request.session.get("delivery_cep"):
            initial["cep"] = format_cep(request.session["delivery_cep"])
        form = DeliveryForm(initial=initial)

    return render_page(form)


def leave_out_of_range_message(request):
    pending = request.session.get(FORA_DA_AREA_SESSION_KEY)
    if not pending:
        return redirect("catalog:product_list")

    if request.method == "POST":
        form = OutOfRangeMessageForm(request.POST)
        if form.is_valid():
            DeliveryMessage.objects.create(
                name=form.cleaned_data["name"],
                phone=form.cleaned_data["phone"],
                cep=pending["cep"],
                distance_km=pending["distance_km"],
                message=form.cleaned_data["message"],
            )
            del request.session[FORA_DA_AREA_SESSION_KEY]
            return render(request, "orders/out_of_range_thanks.html")
    else:
        form = OutOfRangeMessageForm(initial={"name": pending["name"], "phone": pending["phone"]})

    return render(request, "orders/out_of_range.html", {
        "form": form, "distance_km": pending["distance_km"],
    })


# ------------------------------------------------------------ confirmação
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Dados pessoais só aparecem para quem fez o pedido (mesmo navegador).
    is_owner = order.id in request.session.get(MY_ORDERS_SESSION_KEY, [])

    payment_configured = bool(getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", ""))
    awaiting_payment = order.status == "aguardando_pagamento" and payment_configured
    can_send = is_owner and not awaiting_payment and order.status != "cancelado"

    points_earned = points_balance = 0
    if is_owner:
        entry = PointsEntry.objects.filter(order=order, kind=PointsEntry.EARN).select_related("customer").first()
        if entry:
            points_earned, points_balance = entry.points, entry.customer.points

    return render(request, "orders/confirmation.html", {
        "points_earned": points_earned,
        "points_balance": points_balance,
        "order": order,
        "order_items": order.items.select_related("product"),
        "is_owner": is_owner,
        "awaiting_payment": awaiting_payment,
        "whatsapp_url": whatsapp_link(order) if can_send else "",
    })


# ----------------------------------------------------------------- perfil
def _redeem_url(name, phone, points):
    number = re.sub(r"\D", "", getattr(settings, "STORE_WHATSAPP", "") or "")
    if not number:
        return ""
    text = (
        "🎁 *Troca de pontos*\n"
        "Olá! Quero trocar meus pontos por comida grátis.\n\n"
        f"👤 {name}\n📱 {phone}\n⭐ Pontos: {points}"
    )
    return f"https://wa.me/{number}?text={quote(text, safe='')}"


def profile(request):
    saved = request.session.get(CUSTOMER_SESSION_KEY)
    reward = getattr(settings, "LOYALTY_REWARD_POINTS", 10)
    per_order = getattr(settings, "LOYALTY_POINTS_PER_ORDER", 1)
    base_ctx = {"reward": reward, "per_order": per_order}

    if not saved:
        return render(request, "orders/profile.html", {**base_ctx, "identified": False})

    try:
        birth = date.fromisoformat(saved.get("birth_date", ""))
    except ValueError:
        birth = None

    customer = Customer.objects.filter(phone=saved["phone"]).first()
    points = customer.points if customer else 0
    entries = list(customer.entries.all()[:10]) if customer else []

    # O histórico mostra só os pedidos feitos NESTE aparelho e com este telefone:
    # assim ninguém vê pedidos (itens, endereço) de outra pessoa digitando o número dela.
    ids = request.session.get(MY_ORDERS_SESSION_KEY, [])
    orders = (
        Order.objects.filter(id__in=ids, customer_phone=saved["phone"])
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    can_redeem = reward > 0 and points >= reward
    return render(request, "orders/profile.html", {
        **base_ctx,
        "identified": True,
        "name": saved["name"],
        "initial": saved["name"][:1].upper(),
        "phone": saved["phone"],
        "birth": birth,
        "points": points,
        "entries": entries,
        "orders": orders,
        "percent": min(100, int(points * 100 / reward)) if reward > 0 else 0,
        "remaining": max(reward - points, 0),
        "can_redeem": can_redeem,
        "rewards_available": (points // reward) if reward > 0 else 0,
        "redeem_url": _redeem_url(saved["name"], saved["phone"], points) if can_redeem else "",
    })


def profile_edit(request):
    """Informar ou alterar os dados pessoais (usados nos próximos pedidos)."""
    if request.method == "POST":
        form = CustomerInfoForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            request.session[CUSTOMER_SESSION_KEY] = {
                "phone": d["phone"],
                "name": d["name"],
                "birth_date": d["birth_date"].isoformat(),
            }
            messages.success(request, "Dados salvos.")
            return redirect("orders:profile")
    else:
        saved = request.session.get(CUSTOMER_SESSION_KEY) or {}
        initial = {"phone": saved.get("phone", ""), "name": saved.get("name", "")}
        try:
            initial["birth_date"] = date.fromisoformat(saved["birth_date"]).strftime("%d/%m/%Y")
        except (KeyError, ValueError):
            initial["birth_date"] = ""
        form = CustomerInfoForm(initial=initial)
    return render(request, "orders/profile_edit.html", {"form": form})


@require_POST
def profile_forget(request):
    """'Não sou eu': tira os dados e o histórico deste aparelho."""
    request.session.pop(CUSTOMER_SESSION_KEY, None)
    request.session.pop(MY_ORDERS_SESSION_KEY, None)
    return redirect("orders:profile")