from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-troque-em-producao")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "catalog",
    "inventory",
    "delivery",
    "cart",
    "orders",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lojinha_mae.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cart.context_processors.cart",
                "delivery.context_processors.delivery_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "lojinha_mae.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Configurações específicas da loja ---

MERCADOPAGO_ACCESS_TOKEN = config("MERCADOPAGO_ACCESS_TOKEN", default="")
SITE_URL = config("SITE_URL", default="http://127.0.0.1:8000")

# Coordenadas reais da loja (Google Maps: botão direito no endereço > copiar)
SHOP_LATITUDE = config("SHOP_LATITUDE", default=-23.024559847816793, cast=float)    # TROQUE
SHOP_LONGITUDE = config("SHOP_LONGITUDE", default=-43.47739265185506, cast=float)  # TROQUE
DELIVERY_RADIUS_KM = config("DELIVERY_RADIUS_KM", default=3, cast=float) 

# Apelidos usados pelo catalog/views.py (mesmos valores acima)
STORE_LAT = SHOP_LATITUDE
STORE_LON = SHOP_LONGITUDE

LOGIN_URL = "/admin/login/"
MESSAGE_TAGS = {}
STORE_WHATSAPP = config("STORE_WHATSAPP", default="5521980401317")

LOYALTY_POINTS_PER_ORDER = config("LOYALTY_POINTS_PER_ORDER", default=1, cast=int)
LOYALTY_REWARD_POINTS = config("LOYALTY_REWARD_POINTS", default=10, cast=int)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
INSTALLED_APPS += ["loyalty"]
LOYALTY_CONFIRMED_STATUSES = ["pago"]