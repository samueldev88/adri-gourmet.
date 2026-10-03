from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("categoria/<slug:slug>/", views.product_list, name="product_list_by_category"),
    path("produto/<slug:slug>/", views.product_detail, name="product_detail"),
    path("contato/", views.contact, name="contact"),
    path("sobre/", views.contact, name="about"),
    path("receber/", views.set_delivery_mode, name="set_delivery_mode"),
    path("receber/cep/", views.check_cep, name="check_cep"),
]