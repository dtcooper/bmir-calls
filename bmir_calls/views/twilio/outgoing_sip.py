import logging

from twilio.twiml.voice_response import Dial

from django.conf import settings

from ninja import Form

from .utils import EmptyResponse, VoiceResponse, client, create_ninja_api, generate_url_for, parse_sip_address


api = create_ninja_api("outgoing")
url_for = generate_url_for("outgoing")

logger = logging.getLogger(__name__)


@api.post("/")
def call(request, caller: Form[str], called: Form[str], call_sid: Form[str]):
    response = VoiceResponse()

    caller = parse_sip_address(caller)
    called = parse_sip_address(called)

    if caller == settings.TWILIO_SIP_BROADCAST_USER:
        caller_id = settings.TWILIO_BROADCAST_NUMBER

    elif caller == settings.TWILIO_SIP_OUTGOING_USER:
        caller_id = settings.TWILIO_OUTGOING_NUMBER
        if called.lower() == "simulate":
            logger.info("Simulating a dialed request from outgoing phone")
            response.redirect(url_for("incoming:call"))
            return response

    else:
        logger.warning(f"Invalid outgoing caller: {caller}")
        response.hangup()
        return response

    for prefix in ("00", "011"):
        if called.startswith(prefix):
            called = f"+{called.removeprefix(prefix)}"
            break

    lookup = client.lookups.v2.phone_numbers(called).fetch()
    if lookup.valid:
        logger.info(f"Dialing {called} (caller ID = {caller_id})")
        dial: Dial = response.dial(caller_id=caller_id)
        dial.number(lookup.phone_number)
    else:
        logger.warning(f'Invalid outgoing number {called}: {", ".join(lookup.validation_errors)}')
        response.play("call-cannot-be-completed")

    return response


@api.post("/status/")
def broadcast_call_status_callback(request, call_status: Form[str], caller: Form[str]):
    return EmptyResponse()
