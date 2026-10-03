from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("adicionar/<int:product_id>/", views.cart_add, name="add"),
    path("atualizar/<int:product_id>/", views.cart_update, name="update"),
    path("remover/<int:product_id>/", views.cart_remove, name="remove"),
    path("limpar/", views.cart_clear, name="clear"),
]
