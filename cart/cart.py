"""
Carrinho guardado na sessão do navegador (não precisa de login).
Guardamos só {product_id: quantidade} na sessão; o preço e os dados do
produto são sempre buscados do banco na hora de exibir, para nunca
mostrar um preço desatualizado.
"""
from decimal import Decimal

from catalog.models import Product

SESSION_KEY = "carrinho"


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(SESSION_KEY)
        if cart is None:
            cart = self.session[SESSION_KEY] = {}
        self.cart = cart

    def get_quantity(self, product: Product) -> int:
        return self.cart.get(str(product.id), 0)

    def add(self, product: Product, quantity: int = 1):
        product_id = str(product.id)
        self.cart[product_id] = self.cart.get(product_id, 0) + quantity
        self._save()

    def set_quantity(self, product: Product, quantity: int):
        if quantity <= 0:
            self.remove(product)
            return
        self.cart[str(product.id)] = quantity
        self._save()

    def remove(self, product: Product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self._save()

    def clear(self):
        self.session[SESSION_KEY] = {}
        self.cart = self.session[SESSION_KEY]
        self._save()

    def _save(self):
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(id__in=self.cart.keys())
        products_by_id = {str(p.id): p for p in products}

        for product_id, quantity in self.cart.items():
            product = products_by_id.get(product_id)
            if not product:
                continue  # produto foi removido do catálogo depois de adicionado
            unit_price = product.current_price()
            yield {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": unit_price * quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    def total(self) -> Decimal:
        return sum((item["subtotal"] for item in self), Decimal("0.00"))

    def is_empty(self) -> bool:
        return len(self.cart) == 0
