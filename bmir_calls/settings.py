from pathlib import Path
import logging

from starlette.config import Config
from starlette.datastructures import Secret


_config = Config(Path(__file__).parent.parent / ".env")
DEBUG = _config("DEBUG", cast=bool, default=False)
DEBUG_VERBOSE_REQUESTS = DEBUG and _config("DEBUG_VERBOSE_REQUESTS", cast=bool, default=False)
TWILIO_ACCOUNT_SID = _config("TWILIO_ACCOUNT_SID", cast=Secret)
TWILIO_AUTH_TOKEN = _config("TWILIO_AUTH_TOKEN", cast=Secret)
TWILIO_BROADCAST_NUMBER = _config("TWILIO_BROADCAST_NUMBER")
TWILIO_OUTGOING_NUMBER = _config("TWILIO_OUTGOING_NUMBER", default=TWILIO_BROADCAST_NUMBER)
TWILIO_SIP_DOMAIN = _config("TWILIO_SIP_DOMAIN")
TWILIO_SIP_BROADCAST_USER = _config("TWILIO_SIP_BROADCAST_USER", default="broadcast")
TWILIO_SIP_OUTGOING_USER = _config("TWILIO_SIP_OUTGOING_USER", default="outgoing")
TWILIO_QUEUE_NAME = _config("TWILIO_QUEUE_NAME")
TWILIO_QUEUE_MAX_SIZE = _config("TWILIO_QUEUE_MAX_SIZE", cast=int, default=20)


# Set up logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s %(levelprefix)s %(message)s",
            "use_colors": None,
        },
        "calls_debug": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s %(levelprefix)s %(filename)s:%(lineno)s: %(message)s",
            "use_colors": None,
        },
    },
    "handlers": {
        "access": {"class": "logging.StreamHandler", "formatter": "access", "stream": "ext://sys.stdout"},
        "calls_debug": {"class": "logging.StreamHandler", "formatter": "calls_debug", "stream": "ext://sys.stdout"},
        "default": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stderr"},
    },
    "loggers": {
        __name__.split(".")[0]: {
            "handlers": ["calls_debug" if DEBUG else "default"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
    },
})
