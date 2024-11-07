import logging
import random

from twilio.twiml.voice_response import Dial, Gather

from django.conf import settings

from ninja import Form

from ... import constants
from .manager import CallManager, CallStatus
from .utils import EmptyResponse, VoiceResponse, client, create_ninja_api, generate_url_for, parse_sip_address


api = create_ninja_api("incoming")
url_for = generate_url_for("incoming")

logger = logging.getLogger(__name__)


@api.post("/")
def call(request):
    response = VoiceResponse()
    response.play("welcome")
    response.enqueue(name=settings.TWILIO_QUEUE_NAME, action=url_for("left_queue"), wait_url=url_for("waiting_room"))
    return response


@api.post("/waiting-room/")
def waiting_room(
    request,
    call_sid: Form[str],
    caller: Form[str],
    queue_position: Form[int],
    queue_time: Form[int],
    digits: str = None,
    call_count: int = 0,  # Number of calls placed when 1st in queue
):
    response = VoiceResponse()

    if digits == "*":
        response.leave()
        return response

    # should_place_call = queue_position == 1 and manager.call_status == CallStatus.AVAILABLE
    manager = CallManager()
    should_place_call = queue_position == 1 and manager.status == CallStatus.AVAILABLE
    if should_place_call:
        logger.info("Broadcast phone seems available, placing outgoing call to it from waiting room.")
        placed_call_twiml = VoiceResponse()
        placed_call_dial: Dial = placed_call_twiml.dial()
        placed_call_dial.queue(settings.TWILIO_QUEUE_NAME)
        placed_call = client.calls.create(
            to=f"sip:{settings.TWILIO_SIP_BROADCAST_USER}@{settings.TWILIO_SIP_DOMAIN}",
            from_=parse_sip_address(caller),
            timeout=constants.BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT,
            twiml=placed_call_dial,
            status_callback=url_for("broadcast_call_status_callback", _external=True),
            status_callback_event=["answered", "completed"],
        )
        manager.set_status(CallStatus.RINGING, call_sid=placed_call.sid, ringing_sid=call_sid)
        call_count += 1

    action = url_for("waiting_room", query={"call_count": call_count})
    gather = Gather(action=action, num_digits=1, action_on_empty_result=True, timeout=0, finish_on_key="")

    # Fall through on second placed call
    if (call_count == 1 or (call_count > 1 and not should_place_call)) and manager.status == CallStatus.RINGING:
        if call_count > 1:
            gather.play("ringback")
            gather.pause(constants.RINGBACK_PAUSE_AMOUNT)
            response.append(gather)
        else:
            response.play("ringback")
            response.pause(constants.RINGBACK_PAUSE_AMOUNT)
            response.redirect(action)

    else:
        gather.play("attempting-to-connect")
        # if queue_position == 1:
        #     gather.play(static("hold-next.mp3"))
        # else:
        #     gather.play(static())
        gather.play(random.choice(constants.HOLD_TRACKS))
        gather.say(f"Music queue position: position {queue_position} and {queue_time} seconds")
        gather.pause(1)
        response.append(gather)

    return response


@api.post("/left-queue/")
def left_queue(request):
    response = VoiceResponse()
    response.hangup()
    return response


@api.post("/broadcast/status/")
def broadcast_call_status_callback(request, call_sid: Form[str], call_status: Form[str]):
    # logger.debug(f"Got broadcast status={call_status} callback, {caller} => {called}, {call_sid=}")

    # if call_status in ("answered", "in-progress"):
    #     manager.update_broadcast_call(call_sid=call_sid, call_status=CallStatus.CONNECTED)
    # elif call_status in ("no-answer", "busy", "rejected"):
    #     await manager.reject_incoming_broadcast_call()
    # elif call_status == "completed":
    #     manager.hangup_broadcast_call()

    return EmptyResponse()
