from django.conf import settings


def delivery_settings(request):
    return {"DELIVERY_RADIUS_KM": settings.DELIVERY_RADIUS_KM}
