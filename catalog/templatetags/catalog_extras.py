from django import template

register = template.Library()

# exemplo de simple_tag ou filter, ajuste conforme o que seu
# product_list.html está tentando usar
@register.filter
def multiply(value, arg):
    return value * arg
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Permite acessar dictionary[key] dentro do template."""
    if dictionary is None:
        return None
    return dictionary.get(key)