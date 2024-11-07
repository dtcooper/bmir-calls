import contextlib
import logging
#import logging.config
import random
from urllib.parse import urlencode

from twilio.twiml.voice_response import Dial, Gather, VoiceResponse

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import constants, settings
from .manager import CallManager, CallStatus
from .models import init_models
from .utils import EmptyResponse, TwilioRoute, parse_sip_address, twilio_client


logger = logging.getLogger(__name__)


def url_for(name, *, request: Request = None, query=None, **params):
    if request is None:
        url = app.url_path_for(name, **params)
    else:
        url = request.url_for(name, *params)
    if query is not None:
        url = f"{url}?{urlencode(query)}"
    return url


def static(path, *, request: Request = None):
    return url_for("static", request=request, path=path)


async def index(request: Request):
    return PlainTextResponse("There are forty people in this world, and five of them are hamburgers.")


async def outgoing_sip_call(request: Request, caller: str, called: str, call_sid: str):
    response = VoiceResponse()

    caller = parse_sip_address(caller)
    called = parse_sip_address(called)

    if caller == settings.TWILIO_SIP_BROADCAST_USER:
        caller_id = settings.TWILIO_BROADCAST_NUMBER
        manager.update_broadcast_call(call_sid=call_sid, call_status=CallStatus.OUTGOING)

    elif caller == settings.TWILIO_SIP_OUTGOING_USER:
        caller_id = settings.TWILIO_OUTGOING_NUMBER
        if called.lower() == "simulate":
            logger.info("Simulating a dialed request from outgoing phone")
            response.redirect(url_for("incoming_dialed"))
            return response

    else:
        logger.warning(f"Invalid outgoing caller: {caller}")
        response.hangup()
        return response

    for prefix in ("00", "011"):
        if called.startswith(prefix):
            called = f"+{called.removeprefix(prefix)}"
            break

    lookup = await twilio_client.lookups.v2.phone_numbers(called).fetch_async()
    if lookup.valid:
        logger.info(f"Dialing {called} (caller ID = {caller_id})")
        dial: Dial = response.dial(caller_id=caller_id)
        dial.number(lookup.phone_number)
    else:
        logger.warning(f'Invalid outgoing number {called}: {", ".join(lookup.validation_errors)}')
        response.play(static("call-cannot-be-completed.mp3"))

    return response


def outgoing_sip_broadcast_call_status_callback(request: Request, call_status: str, caller: str):
    # SIP Domains only provide call completed callbacks, however let's check just to be sure
    if parse_sip_address(caller) == settings.TWILIO_SIP_BROADCAST_USER:
        if call_status not in ("initiated", "ringing", "answered", "in-progress"):
            manager.hangup_broadcast_call()
    return EmptyResponse()


def incoming_dialed(request: Request):
    response = VoiceResponse()
    response.play(static("welcome.mp3"))
    response.enqueue(
        name=settings.TWILIO_QUEUE_NAME,
        action=url_for("incoming_dialed_left_queue"),
        wait_url=url_for("incoming_dialed_waiting_room"),
    )
    return response


async def incoming_dialed_waiting_room(
    request: Request,
    caller: str,
    queue_position: int,
    queue_time: int,
    digits: str = None,
    call_count: int = 0,  # Number of calls placed when 1st in queue
):
    response = VoiceResponse()

    if digits == "*":
        response.leave()
        return response

    should_place_call = queue_position == 1 and manager.call_status == CallStatus.AVAILABLE
    if should_place_call:
        logger.info("Broadcast phone seems available, placing outgoing call to it from waiting room.")
        call_twiml = VoiceResponse()
        call_dial: Dial = call_twiml.dial()
        call_dial.queue(settings.TWILIO_QUEUE_NAME)
        call = await twilio_client.calls.create_async(
            to=f"sip:{settings.TWILIO_SIP_BROADCAST_USER}@{settings.TWILIO_SIP_DOMAIN}",
            from_=parse_sip_address(caller),
            timeout=constants.BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT,
            twiml=call_twiml,
            status_callback=url_for("incoming_dialed_broadcast_call_status_callback", request=request),
            status_callback_event=["answered", "completed"],
        )
        manager.update_broadcast_call(call_sid=call.sid, call_status=CallStatus.RINGING)
        call_count += 1

    action = url_for("incoming_dialed_waiting_room", query={"call_count": call_count})
    gather_kw = {"action": action, "num_digits": 1, "action_on_empty_result": True, "timeout": 0, "finish_on_key": ""}

    logger.debug(f"XXX waiting room // {digits=} {call_count=}")

    # Fall through on second placed call
    if (call_count == 1 or (call_count > 1 and not should_place_call)) and manager.call_status == CallStatus.RINGING:
        if call_count > 1:
            gather: Gather = response.gather(**gather_kw)
            gather.play(static("ringback.mp3"))
            gather.pause(constants.RINGBACK_PAUSE_AMOUNT)
        else:
            response.play(static("ringback.mp3"))
            response.pause(constants.RINGBACK_PAUSE_AMOUNT)
            response.redirect(action)

    else:
        gather: Gather = response.gather(**gather_kw)
        gather.play(static("attempting-to-connect.mp3"))
        # if queue_position == 1:
        #     gather.play(static("hold-next.mp3"))
        # else:
        #     gather.play(static())
        gather.play(static(random.choice(constants.HOLD_TRACKS)))
        gather.say(f"Music queue position: position {queue_position} and {queue_time} seconds")
        gather.pause(1)

    return response


async def incoming_dialed_broadcast_call_status_callback(request: Request, call_sid: str, call_status: str):
    # logger.debug(f"Got broadcast status={call_status} callback, {caller} => {called}, {call_sid=}")

    if call_status in ("answered", "in-progress"):
        manager.update_broadcast_call(call_sid=call_sid, call_status=CallStatus.CONNECTED)
    elif call_status in ("no-answer", "busy", "rejected"):
        await manager.reject_incoming_broadcast_call()
    elif call_status == "completed":
        manager.hangup_broadcast_call()

    return EmptyResponse()


def incoming_dialed_left_queue(request: Request, queue_result: str):
    response = VoiceResponse()
    if queue_result == "leave":
        response.say("You left the queue")
    else:
        response.play(static("fun-music.mp3"))
    return response


def voicemail(request: Request):
    response = VoiceResponse()
    response.say("Would leave voicemail")
    return response


def test(request: Request, test_user_id: int, test: str):
    return PlainTextResponse(f"hi, mom {type(test_user_id)}")


routes = [
    Route("/", index),
    TwilioRoute("/outgoing", outgoing_sip_call),
    TwilioRoute("/outgoing/broadcast/status", outgoing_sip_broadcast_call_status_callback),
    TwilioRoute("/incoming", incoming_dialed),
    TwilioRoute("/incoming/broadcast/status", incoming_dialed_broadcast_call_status_callback),
    TwilioRoute("/incoming/waiting-room", incoming_dialed_waiting_room),
    TwilioRoute("/incoming/left-queue", incoming_dialed_left_queue),
    TwilioRoute("/voicemail", voicemail),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]


@contextlib.asynccontextmanager
async def lifespan(app):
    await init_models()
    await manager.start()
    yield
    await manager.stop()


manager = CallManager()
app = Starlette(debug=settings.DEBUG, routes=routes, lifespan=lifespan)
