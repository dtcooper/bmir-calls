from pathlib import Path

from starlette.config import Config


config = Config(Path(__file__).parent.parent / ".env")
DEBUG = config("DEBUG", cast=bool, default=False)
DEBUG_VERBOSE_REQUESTS = DEBUG and config("DEBUG_VERBOSE_REQUESTS", cast=bool, default=False)
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
TWILIO_BROADCAST_NUMBER = config("TWILIO_BROADCAST_NUMBER")
TWILIO_SIP_DOMAIN = config("TWILIO_SIP_DOMAIN")
TWILIO_SIP_BROADCAST_USER = config("TWILIO_SIP_BROADCAST_USER")
TWILIO_SIP_SIMULATE_USER = config("TWILIO_SIP_SIMULATE_USER")
TWILIO_QUEUE_NAME = config("TWILIO_QUEUE_NAME")
TWILIO_QUEUE_MAX_SIZE = config("TWILIO_QUEUE_MAX_SIZE", cast=int, default=20)
