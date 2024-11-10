import logging

from twilio.twiml.voice_response import Dial

from django.conf import settings

from ninja import Form

from ...twilio import parse_sip_address, validate_phone_number
from .manager import CallManager, CallStatus
from .utils import EmptyResponse, VoiceResponse, create_ninja_api, generate_url_for


api = create_ninja_api("outgoing")
url_for = generate_url_for("outgoing")

logger = logging.getLogger(__name__)


@api.post("/")
def call(request, caller: Form[str], called: Form[str], call_sid: Form[str]):
    response = VoiceResponse()

    caller = parse_sip_address(caller)
    called = parse_sip_address(called)

    if caller == settings.TWILIO_SIP_BROADCAST_USER:
        manager = CallManager()
        manager.set_status(CallStatus.OUTGOING, call_sid=call_sid)
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

    number = validate_phone_number(called)
    if number is not None:
        logger.info(f"Dialing {number} (caller ID = {caller_id})")
        dial: Dial = response.dial(caller_id=caller_id, answer_on_bridge=True)
        dial.number(number)
    else:
        response.play("call-cannot-be-completed")

    return response


@api.post("/status/")
def broadcast_call_status_callback(request, call_sid: Form[str], call_status: Form[str], caller: Form[str]):
    caller = parse_sip_address(caller)

    # SIP Domains only provide call completed callbacks, however let's check just to be sure
    if caller == settings.TWILIO_SIP_BROADCAST_USER and call_status not in (
        "initiated",
        "ringing",
        "answered",
        "in-progress",
    ):
        manager = CallManager()
        if manager.status in (CallStatus.RINGING, CallStatus.OUTGOING, CallStatus.CONNECTED):
            if manager.call_sid != call_sid:
                logger.warning("Got unexpected call in progress SID!")
            manager.set_status(CallStatus.AVAILABLE)
    return EmptyResponse()
