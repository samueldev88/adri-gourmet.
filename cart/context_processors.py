from .cart import Cart


def cart(request):
    """Deixa o carrinho disponível em todos os templates (ex: contador no cabeçalho)."""
    return {"cart": Cart(request)}
