"""Karivex backend settings — env-driven, Docker-ready."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Single source of truth is the .env file at the project root (one level
# above backend/). In Docker, docker-compose's `env_file: .env` already
# injects these into the container's environment before this process starts,
# and load_dotenv() never overrides an already-set variable — so this is a
# no-op there. It only matters for running manage.py/gunicorn directly on a
# host, where nothing else would load the root .env.
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "https://karivex.co.ke").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "cloudinary_storage",
    "django.contrib.staticfiles",
    "cloudinary",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "catalog",
    "ai_tools",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "karivex.urls"
WSGI_APPLICATION = "karivex.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "karivex"),
        "USER": os.environ.get("POSTGRES_USER", "karivex"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "karivex_db"),
        "PORT": "5432",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "catalog.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    # Session/Basic unchanged for Django admin & browsable API; SignedTokenAuthentication
    # is additive — it doesn't touch any view's permission_classes, so every existing
    # AllowAny catalog endpoint is unaffected. It also makes ai_tools' existing
    # IsAdminUser views (draft-product, internal-links) work with the admin
    # control center's bearer token for free.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "dashboard.authentication.SignedTokenAuthentication",
    ],
}

# Admin control-center session length (hours) — bearer tokens are signed via
# Django's TimestampSigner using DJANGO_SECRET_KEY; no separate secret needed.
DASHBOARD_SESSION_HOURS = int(os.environ.get("DASHBOARD_SESSION_HOURS", "12"))

# Frontend revalidation webhook (container-name URL, not shared alias — see compose)
FRONTEND_INTERNAL_URL = os.environ.get("FRONTEND_INTERNAL_URL", "http://karivex_frontend:3000")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "change-me")

CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Business identity — mirrors frontend/lib/site.ts. Single source is the .env
# file; used server-side only (AI prompts, future notification emails), never
# exposed to a public endpoint.
SITE = {
    "name": os.environ.get("SITE_NAME", "Karivex Solutions Ltd"),
    "short_name": os.environ.get("SITE_SHORT_NAME", "Karivex"),
    "tagline": os.environ.get("SITE_TAGLINE", "Chemical Division"),
    "phone": os.environ.get("SITE_PHONE", "+254700000000"),
    "whatsapp": os.environ.get("SITE_WHATSAPP", "+254700000000"),
    "email": os.environ.get("SITE_EMAIL", "sales@karivex.co.ke"),
    "regions": [r.strip() for r in os.environ.get("SITE_REGIONS", "Kenya,Uganda,Tanzania,Rwanda").split(",") if r.strip()],
    "hours": os.environ.get("SITE_HOURS", "Mo-Fr 08:00-17:00, Sa 08:00-13:00"),
    "delivery_nairobi": os.environ.get("SITE_DELIVERY_NAIROBI", "24-hour delivery in Nairobi"),
    "delivery_regional": os.environ.get("SITE_DELIVERY_REGIONAL", "2-3 day delivery to Uganda, Tanzania & Rwanda"),
    "certifications": os.environ.get("SITE_CERTIFICATIONS", "COA & MSDS with every order"),
    # --- E-E-A-T signals. Every one of these is BLANK by default and is only
    # rendered when set, because these are exactly the claims that are damaging
    # to fabricate: a certification the business does not hold, or a founding
    # year that contradicts the company register. Fill them in .env only with
    # what can be evidenced.
    "founded_year": os.environ.get("SITE_FOUNDED_YEAR", "").strip(),
    "quality_statement": os.environ.get("SITE_QUALITY_STATEMENT", "").strip(),
    "compliance": os.environ.get("SITE_COMPLIANCE", "").strip(),
    "industries_served": [
        i.strip() for i in os.environ.get("SITE_INDUSTRIES_SERVED", "").split(",") if i.strip()
    ],
}

# Cities the business actually delivers to, as "City:Country" pairs.
#
# Drives geographic keyword generation in ai_tools/keywords.py. It is config
# rather than a constant for one reason: a city named here becomes a phrase the
# content is optimised for, and optimising for a town nobody ships to is how a
# supplier site drifts into doorway-page territory. Removing a row here removes
# it from every page's keyword strategy on the next generation.
#
# Cities whose country is not in SITE["regions"] are ignored at runtime, so
# pruning the regions list is enough to retire a whole market.
SITE_DELIVERY_CITIES = [
    tuple(part.split(":", 1))
    for part in os.environ.get(
        "SITE_DELIVERY_CITIES",
        "Nairobi:Kenya,Mombasa:Kenya,Kisumu:Kenya,Eldoret:Kenya,Nakuru:Kenya,"
        "Thika:Kenya,Kampala:Uganda,Dar es Salaam:Tanzania,Kigali:Rwanda",
    ).split(",")
    if ":" in part
]

# Without an explicit config, Django only wires up the `django` logger — app
# loggers like catalog.emails fall through to logging's last-resort handler,
# which emits WARNING and above and drops INFO entirely. That made a successful
# quote notification indistinguishable from one that never ran. Everything to
# stdout, where `docker compose logs` picks it up.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

# Resend — transactional email for quote requests. Blank key disables sending
# (logged as a warning, never an exception), same degrade-gracefully contract
# as the OpenAI and Cloudinary blocks below.
#
# QUOTE_FROM_EMAIL must be on a domain verified in Resend. The DKIM key is
# published at resend._domainkey.karivexsolutionsltd.com — i.e. the ROOT domain
# is the verified one, with send.karivexsolutionsltd.com only as the custom
# MAIL FROM — so an address at the apex is correct here.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# `or` rather than a get() default throughout: docker-compose's env_file passes
# every declared key through even when it is blank, so an unfilled
# `QUOTE_NOTIFY_TO=` in .env arrives as "" and would silently beat a get()
# default — which is exactly how the first version of this shipped with an
# empty recipient list.
QUOTE_FROM_EMAIL = os.environ.get("QUOTE_FROM_EMAIL", "").strip() or (
    f"{os.environ.get('SITE_NAME') or 'Karivex Solutions Ltd'} <quotes@karivexsolutionsltd.com>"
)
# Where new quote requests land. Comma-separated; falls back to SITE_EMAIL so
# the notification always has somewhere to go even if this is never configured.
QUOTE_NOTIFY_TO = [
    e.strip() for e in (
        os.environ.get("QUOTE_NOTIFY_TO", "").strip()
        or os.environ.get("SITE_EMAIL", "").strip()
        or "info@karivexsolutionsltd.com"
    ).split(",") if e.strip()
]
QUOTE_SEND_CUSTOMER_ACK = os.environ.get("QUOTE_SEND_CUSTOMER_ACK", "true").lower() == "true"

# OpenAI — used for staff-side content drafting and the public FAQ chatbot.
# Blank key means AI features are disabled; ai_tools.services raises a clear
# error rather than the app crashing at import/boot time.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CONTENT_MODEL = os.environ.get("OPENAI_CONTENT_MODEL", "gpt-4o-mini")
OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# Cloudinary — all product/blog image uploads (ImageField) go straight to
# Cloudinary's CDN instead of local disk when configured. Blank creds fall
# back to local FileSystemStorage so dev/CI never hard-depends on a Cloudinary
# account — same degrade-gracefully pattern as the OpenAI config above.
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
}
USE_CLOUDINARY = bool(
    CLOUDINARY_STORAGE["CLOUD_NAME"] and CLOUDINARY_STORAGE["API_KEY"] and CLOUDINARY_STORAGE["API_SECRET"]
)
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"
        if USE_CLOUDINARY else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
# django-cloudinary-storage==0.3.0 predates Django's STORAGES setting and its
# collectstatic override still reads the legacy attribute directly.
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
