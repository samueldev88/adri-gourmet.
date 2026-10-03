from django.conf import settings


def delivery(request):
    return {"DELIVERY_RADIUS_KM": getattr(settings, "DELIVERY_RADIUS_KM", 3)}