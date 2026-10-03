from django.urls import path

from . import views

app_name = "loyalty"

urlpatterns = [
    path("", views.home, name="home"),
    path("resgatar/<int:reward_id>/", views.redeem, name="redeem"),
]
