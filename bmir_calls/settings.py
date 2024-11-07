from collections import OrderedDict
from pathlib import Path

import environ


env = environ.Env()
env.read_env("/.env")


PROJECT_DIR = Path(__file__).resolve().parent
BASE_DIR = PROJECT_DIR.parent

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
DEBUG_VERBOSE_REQUESTS = DEBUG and env.bool("DEBUG_VERBOSE_REQUESTS", default=False)
DOMAIN_NAME = env("DOMAIN_NAME")

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_BROADCAST_NUMBER = env("TWILIO_BROADCAST_NUMBER")
TWILIO_OUTGOING_NUMBER = env("TWILIO_OUTGOING_NUMBER", default=TWILIO_BROADCAST_NUMBER)
TWILIO_QUEUE_NAME = env("TWILIO_QUEUE_NAME")
TWILIO_SIP_DOMAIN = env("TWILIO_SIP_DOMAIN")
TWILIO_SIP_BROADCAST_USER = env("TWILIO_SIP_BROADCAST_USER", default="broadcast")
TWILIO_SIP_OUTGOING_USER = env("TWILIO_SIP_OUTGOING_USER", default="outgoing")


ALLOWED_HOSTS = [DOMAIN_NAME]
if DEBUG:
    ALLOWED_HOSTS.append("localhost")
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda req: req.user.is_superuser}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "constance",
]
if DEBUG:
    INSTALLED_APPS.extend([
        "debug_toolbar",
        "django_extensions",
    ])
INSTALLED_APPS.append("bmir_calls")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if DEBUG:
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "bmir_calls.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_DIR / "templates"],  # To make base_site.html work
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bmir_calls.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",
        "PORT": 5432,
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        }
    },
    "formatters": {
        "console": {
            "format": "[%(asctime)s] %(levelname)s:%(name)s:%(lineno)s:%(funcName)s: %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "console", "level": "INFO"},
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "huey": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "bmir_calls": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TZ", default="US/Eastern")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = "/serve/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = "/serve/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CONSTANCE_CONFIG = {
    "TAKING_CALLS": (True, "Application is currently taking calls. Set to false to reject."),
}

if DEBUG:
    CONSTANCE_CONFIG.update({
        "SKIP_TWILIO_PLAY": (False, "Skip Twilio <Play /> verb, just use <Say /> verb instead"),
    })

CONSTANCE_CONFIG_FIELDSETS = OrderedDict((("General settings", ("TAKING_CALLS",)),))
if DEBUG:
    CONSTANCE_CONFIG_FIELDSETS["Debug settings"] = ("SKIP_TWILIO_PLAY",)

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

SHELL_PLUS_IMPORTS = ("from constance import config",)
