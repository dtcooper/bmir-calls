import datetime
import logging
from pathlib import Path
import random

from num2words import num2words
import requests
from twilio.twiml.voice_response import Dial

from django.conf import settings
from django.core.files.base import ContentFile

from constance import config
from ninja import Form

from ...models import LOCATION_UNKNOWN, Voicemail
from ...twilio import client, get_sip_address, parse_sip_address, validate_phone_number
from .call_manager import CallManager, CallStatus
from .utils import EmptyResponse, Gather, VoiceResponse, create_ninja_api, generate_url_for


api = create_ninja_api("incoming")
url_for = generate_url_for("incoming")

logger = logging.getLogger(__name__)


RINGBACK_PAUSE_AMOUNT = 4
BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT = 45
SOUNDS_DIR = Path(__file__).parent.parent.parent / "static" / "bmir_calls" / "twilio" / "sounds"
HOLD_TRACKS = tuple(p.stem for p in SOUNDS_DIR.iterdir() if p.suffix == ".mp3" and p.stem.startswith("hold-music-"))
QUEUE_POSITION_TRACKS = {
    int(p.stem): f"queue-position/{p.stem}"
    for p in (SOUNDS_DIR / "queue-position").iterdir()
    if p.suffix == ".mp3" and p.stem.isdigit()
}


@api.post("/call-outgoing/")
def call_outgoing(request):
    response = VoiceResponse()
    dial: Dial = response.dial(answer_on_bridge=True)
    dial.sip(get_sip_address(settings.TWILIO_SIP_OUTGOING_USER))
    return response


@api.post("/")
def call(request, called: Form[str]):
    response = VoiceResponse()
    called = parse_sip_address(called)
    response.play("welcome")
    if config.TAKING_CALLS:
        response.enqueue(
            name=settings.TWILIO_QUEUE_NAME, action=url_for("left_queue"), wait_url=url_for("waiting_room")
        )
    else:
        response.play("not-taking-calls")
        response.redirect(url_for("voicemail"))
    return response


@api.post("/waiting-room/")
def waiting_room(
    request,
    caller: Form[str],
    queue_position: Form[int],
    queue_time: Form[int],
    digits: Form[str] = None,
    call_count: int = 0,  # Number of calls placed when 1st in queue
):
    response = VoiceResponse()

    if digits == "*" or queue_time > settings.TWILIO_QUEUE_MAX_WAIT_TIME:
        response.leave()  # Leaving goes to Voicemail
        return response

    manager = CallManager()
    first_in_queue = queue_position == 1
    if call_placed := (first_in_queue and manager.status == CallStatus.AVAILABLE):
        logger.info("Broadcast phone seems available, placing outgoing call to it from waiting room.")
        twiml_response = VoiceResponse()
        twiml_dial: Dial = twiml_response.dial(timeout=15)
        twiml_dial.queue(settings.TWILIO_QUEUE_NAME)
        placed_call = client.calls.create(
            to=get_sip_address(settings.TWILIO_SIP_BROADCAST_USER),
            from_=parse_sip_address(caller),
            timeout=BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT,
            twiml=twiml_response,
            status_callback=url_for("broadcast_call_status_callback", _external=True),
        )
        manager.set_status(CallStatus.INCOMING, sid=placed_call.sid)
        call_count += 1

    action = url_for("waiting_room", call_count=call_count)
    gather = Gather(action=action, num_digits=1, action_on_empty_result=True, timeout=0, finish_on_key="")

    # Fall through to recording on second placed call
    if first_in_queue and (call_count == 1 or (call_count > 1 and not call_placed)):
        if call_count > 1:
            gather.play("ringback")
            gather.pause(RINGBACK_PAUSE_AMOUNT)
            response.append(gather)
        else:
            response.play("ringback")
            response.pause(RINGBACK_PAUSE_AMOUNT)
            response.redirect(action)

    else:
        if call_count >= 1:
            gather.play("queue-position/ringing")
        else:
            gather.play("attempting-to-connect")

        gather.play("queue-instructions")

        if call_count == 0:
            asset = QUEUE_POSITION_TRACKS.get(queue_position)
            if asset is None:
                gather.play("queue-position/generic")
                gather.say(f'{num2words(queue_position, to="ordinal").replace("-", " ").capitalize()}.')
            else:
                gather.play(asset)
            gather.play(random.choice(HOLD_TRACKS))
        response.append(gather)

    return response


@api.post("/broadcast/status/")
def broadcast_call_status_callback(request, call_status: Form[str]):
    manager = CallManager()

    if call_status in ("no-answer", "busy", "rejected"):
        if manager.status == CallStatus.AVAILABLE:
            logger.warning("Call manager not in connected status when busy/no-answer/rejected. Forcing a validation.")
            manager.validate_from_server()
    elif call_status == "completed":
        manager.set_status(CallStatus.AVAILABLE)

    return EmptyResponse()


@api.post("/left-queue/")
def left_queue(request, queue_result: Form[str]):
    response = VoiceResponse()

    if queue_result == "leave" or queue_result == "queue-full":
        response.redirect(url_for("voicemail"))
        return response  # Avoid hangup as below
    elif queue_result == "hangup":
        manager = CallManager()
        manager.validate_from_server()

    elif queue_result == "bridged":
        response.play("fun-music")
    else:
        logger.warning(f"Got unexpected left queue result: {queue_result}")

    response.hangup()
    return response


@api.post("/voicemail/")
def voicemail(
    request,
    caller: Form[str],
    digits: Form[str] = None,
    caller_city: Form[str] = None,
    caller_state: Form[str] = None,
    caller_country: Form[str] = None,
):
    response = VoiceResponse()

    if digits:
        response.play("goodbye")
        response.play("fun-music")
        response.hangup()
        return response

    response.play("voicemail-instructions")
    response.play("beep")

    caller_id = validate_phone_number(parse_sip_address(caller)) or ""
    location = ", ".join(s for s in (caller_city, caller_state, caller_country) if s) or LOCATION_UNKNOWN

    response.record(
        timeout=15,
        max_length=150,  # 2.5 minutes
        recording_status_callback=url_for("voicemail_status_callback", caller_id=caller_id, location=location),
        play_beep=False,
    )

    return response


@api.post("/voicemail/status/")
def voicemail_status_callback(
    request,
    recording_sid: Form[str],
    recording_url: Form[str],
    recording_duration: Form[int],
    location: str,
    caller_id: str = "",
):
    recording = requests.get(f"{recording_url}.mp3")
    Voicemail.objects.create(
        phone_number=caller_id,
        location=location,
        duration=datetime.timedelta(seconds=recording_duration),
        file=ContentFile(recording.content, name=f"{recording_sid}.mp3"),
    )

    # logger.info(f"Deleting recording {recording_sid}.")
    if config.DELETE_RECORDINGS_FROM_TWILIO_AFTER_DOWNLOAD:
        logger.info(f"Removing downloaded recording {recording_sid} from Twilio.")
        client.recordings(recording_sid).delete()

    return EmptyResponse()
