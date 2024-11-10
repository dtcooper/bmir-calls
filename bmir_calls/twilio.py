import logging

from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

from django.conf import settings


client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, http_client=TwilioHttpClient(timeout=10))

logger = logging.getLogger(__name__)


def parse_sip_address(address):
    return address.removeprefix("sip:").split("@")[0]


def get_sip_address(address):
    return f"sip:{address}@{settings.TWILIO_SIP_DOMAIN}"


def validate_phone_number(number):
    lookup = client.lookups.v2.phone_numbers(number).fetch()
    if lookup.valid:
        return lookup.phone_number
    else:
        logger.warning(f'Invalid number {number}: {", ".join(lookup.validation_errors)}')
        return None


def create_or_find_queue(name=None, *, create=True):
    if name is None:
        name = settings.TWILIO_QUEUE_NAME

    queue = None
    for queue_to_test in client.queues.stream():
        if queue_to_test.friendly_name == name:
            queue = queue_to_test
            break

    if create:
        if queue is None:
            queue = client.queues.create(friendly_name=name, max_size=settings.TWILIO_QUEUE_MAX_SIZE)
        elif queue.max_size != settings.TWILIO_QUEUE_MAX_SIZE:
            logger.info(f"Setting queue {name} max_size to {settings.TWILIO_QUEUE_MAX_SIZE}")
            queue = client.queues(queue.sid).update(max_size=settings.TWILIO_QUEUE_MAX_SIZE)
    return queue
