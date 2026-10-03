from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("", views.checkout, name="checkout"),
    path("dados/", views.customer_info, name="customer_info"),
    path("fora-da-area/", views.leave_out_of_range_message, name="leave_message"),
    path("confirmacao/<int:order_id>/", views.order_confirmation, name="confirmation"),
    path("perfil/", views.profile, name="profile"),
    path("perfil/dados/", views.profile_edit, name="profile_edit"),
    path("perfil/sair/", views.profile_forget, name="profile_forget"),
]