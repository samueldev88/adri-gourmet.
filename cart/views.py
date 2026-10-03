from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Product
from .cart import Cart


def _redirect_next(request, default="cart:detail"):
    """Só aceita 'next' que aponte para o próprio site (evita redirecionar para sites externos)."""
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(default)


def cart_detail(request):
    cart = Cart(request)
    items = list(cart)
    subtotal = sum((i["subtotal"] for i in items), Decimal("0.00"))

    suggestions = (
        Product.objects.filter(active=True, stock__gt=0)
        .exclude(id__in=[i["product"].id for i in items])
        .select_related("category")
        .prefetch_related("discounts")
        .order_by("name")[:8]
    )

    return render(request, "cart/detail.html", {
        "cart": cart,
        "items": items,
        "subtotal": subtotal,
        "suggestions": suggestions,
        "delivery_mode": request.session.get("delivery_mode"),
        "delivery_distance_km": request.session.get("delivery_distance_km"),
    })


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, active=True)

    try:
        requested = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        requested = 1
    requested = max(1, requested)

    current = cart.get_quantity(product)
    room_left = max(product.stock - current, 0)
    to_add = min(requested, room_left)

    if product.stock == 0:
        messages.warning(request, f'"{product.name}" está esgotado no momento.')
    elif to_add == 0:
        messages.warning(request, f'Você já tem todo o estoque de "{product.name}" na sacola ({product.stock}).')
    elif to_add < requested:
        messages.warning(request, f'Só temos {product.stock} unidade(s) de "{product.name}" em estoque.')

    if to_add > 0:
        cart.add(product, to_add)

    return _redirect_next(request)


@require_POST
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(0, min(quantity, product.stock))
    cart.set_quantity(product, quantity)
    return _redirect_next(request)


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return _redirect_next(request)


@require_POST
def cart_clear(request):
    Cart(request).clear()
    return _redirect_next(request)
