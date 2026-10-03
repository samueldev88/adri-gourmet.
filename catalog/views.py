from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from cart.cart import Cart
from .cep_distance import (
    CepNotFound,
    LookupUnavailable,
    haversine_km,
    lookup_cep,
    normalize_cep,
)
from .models import Category, Product


def _cart_quantities(request):
    """{product_id: quantidade} pra já renderizar o botão certo (Adicionar ou o contador -/+)."""
    cart = Cart(request)
    return {item["product"].id: item["quantity"] for item in cart}


def product_list(request, slug=None):
    categories = Category.objects.all()
    products = Product.objects.filter(active=True).select_related("category").prefetch_related("discounts")

    category_slug = slug or request.GET.get("category") or ""
    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(name__icontains=query)

    return render(request, "catalog/product_list.html", {
        "categories": categories,
        "current_category": current_category,
        "products": products,
        "cart_quantities": _cart_quantities(request),
        "query": query,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("discounts"),
        slug=slug, active=True,
    )
    return render(request, "catalog/product_detail.html", {
        "product": product,
        "cart_quantities": _cart_quantities(request),
    })


def contact(request):
    return render(request, "catalog/contact.html")


@require_POST
def set_delivery_mode(request):
    """Guarda na sessão se a pessoa quer entrega ou retirada.
    Entrega só é aceita se o CEP já foi validado dentro do raio."""
    mode = request.POST.get("mode")
    if mode == "retirada":
        request.session["delivery_mode"] = "retirada"
    elif mode == "entrega":
        if request.session.get("delivery_in_range"):
            request.session["delivery_mode"] = "entrega"
        else:
            messages.error(
                request,
                "Entrega indisponível: informe um CEP dentro da área de entrega.",
            )

    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect("catalog:product_list")


@require_POST
def check_cep(request):
    """Recebe o CEP, calcula a distância até a loja e valida o raio."""
    cep = normalize_cep(request.POST.get("cep"))
    if cep is None:
        return JsonResponse({"ok": False, "error": "Digite um CEP com 8 números."}, status=400)

    store_lat = getattr(settings, "STORE_LAT", None)
    store_lon = getattr(settings, "STORE_LON", None)
    if store_lat is None or store_lon is None:
        return JsonResponse(
            {"ok": False, "error": "A localização da loja ainda não foi configurada."},
            status=500,
        )

    try:
        place = lookup_cep(cep)
    except CepNotFound:
        return JsonResponse(
            {"ok": False, "error": "Não encontrei esse CEP. Confira os números."}, status=404
        )
    except LookupUnavailable:
        return JsonResponse(
            {"ok": False, "error": "Não consegui consultar o CEP agora. Tente de novo em instantes."},
            status=503,
        )

    km = round(haversine_km(float(store_lat), float(store_lon), place["lat"], place["lon"]), 1)
    radius = float(getattr(settings, "DELIVERY_RADIUS_KM", 3))
    in_range = km <= radius

    request.session["delivery_cep"] = cep
    request.session["delivery_distance_km"] = km
    request.session["delivery_in_range"] = in_range
    if in_range:
        request.session["delivery_mode"] = "entrega"
    elif request.session.get("delivery_mode") == "entrega":
        del request.session["delivery_mode"]

    return JsonResponse({
        "ok": True,
        "distance_km": km,
        "radius_km": radius,
        "in_range": in_range,
        "address": place.get("address", ""),
    })