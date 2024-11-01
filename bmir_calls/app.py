import contextlib

from twilio.twiml.voice_response import Dial, Gather, VoiceResponse

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import config, constants
from .manager import CallManager, CallStatus
from .utils import TwilioRoute, logger, parse_sip_address, twilio_client, url


def index(request: Request):
    return PlainTextResponse("There are forty people in this world, and five of them are hamburgers.")


def outgoing(request: Request, caller: str):
    response = VoiceResponse()

    caller = parse_sip_address(caller)

    if caller == config.TWILIO_SIP_SIMULATE_USER:
        logger.debug("Simulating a call based on SIP username")
        response.redirect(url(request, "incoming"))
    elif caller == config.TWILIO_SIP_BROADCAST_USER:
        response.redirect(url(request, "outgoing_broadcast"))
    else:
        logger.warning(f"Invalid outgoing caller: {caller}")
        response.hangup()

    return response


async def outgoing_broadcast(request: Request, called: str, call_sid: str):
    manager.update_broadcast_call(call_sid=call_sid, call_status=CallStatus.OUTGOING)

    response = VoiceResponse()
    number = called

    for prefix in ("00", "011"):
        if number.startswith(prefix):
            number = f"+{number.removeprefix(prefix)}"
            break

    lookup = await twilio_client.lookups.v2.phone_numbers(parse_sip_address(number)).fetch_async()
    if lookup.valid:
        dial: Dial = response.dial(caller_id=config.TWILIO_BROADCAST_NUMBER)
        dial.number(lookup.phone_number)
    else:
        logger.warning(f'Invalid outgoing number {called}: {", ".join(lookup.validation_errors)}')
        response.say("Your call cannot be completed as dialed. Please check the number and try you call again.")

    return response


async def outgoing_broadcast_status_callback(
    request: Request, caller: str, called: str, call_sid: str, call_status: str
):
    caller = parse_sip_address(caller)
    called = parse_sip_address(called)

    logger.debug(f"Got broadcast phone status callback, {caller} => {called}, {call_sid=} {call_status=}")

    # Was an outgoing call
    if parse_sip_address(caller) == config.TWILIO_SIP_BROADCAST_USER:
        if call_status not in ("initiated", "ringing", "answered", "in-progress"):
            manager.hangup_broadcast_call()

    # Incoming call
    elif parse_sip_address(called) == config.TWILIO_SIP_BROADCAST_USER:
        if call_status in ("answered", "in-progress"):
            manager.update_broadcast_call(call_sid=call_sid, call_status=CallStatus.CONNECTED)
        elif call_status == "completed":
            manager.hangup_broadcast_call()
        else:
            manager.temporarily_block_broadcast_calls()

    return Response(status_code=204)


def incoming(request: Request):
    response = VoiceResponse()
    response.enqueue(
        name=config.TWILIO_QUEUE_NAME,
        action=url(request, "incoming_left_queue"),
        wait_url=url(request, "incoming_waiting_room"),
    )
    return response


async def incoming_waiting_room(
    request: Request,
    caller: str,
    call_sid: str,
    queue_position: int,
    queue_time: int,
    digits: str = None,
    gather_while_ringing: bool = False,
):
    response = VoiceResponse()

    if digits == "*":
        response.leave()
        return response

    # TODO leave with a message after queue time > 20 minutes?

    if queue_position == 1 and manager.call_status == CallStatus.AVAILABLE:
        logger.info("Broadcast phone seems available, placing outgoing call to it from waiting room.")

        call_twiml = VoiceResponse()
        call_twiml_dial: Dial = call_twiml.dial()
        call_twiml_dial.queue(name=config.TWILIO_QUEUE_NAME)

        call = await twilio_client.calls.create_async(
            to=f"sip:{config.TWILIO_SIP_BROADCAST_USER}@{config.TWILIO_SIP_DOMAIN}",
            from_=parse_sip_address(caller),
            timeout=45,
            twiml=call_twiml,
            status_callback=url(request, "outgoing_broadcast_status_callback"),
            status_callback_event=["answered", "completed"],
        )
        manager.update_broadcast_call(call_sid=call.sid, ringing_sid=call_sid, call_status=CallStatus.RINGING)

    gather_kwargs = {"num_digits": 1, "action_on_empty_result": True, "timeout": 0, "finish_on_key": ""}
    logger.critical(f"{digits=}, {gather_while_ringing=}")

    if manager.ringing_sid == call_sid:

        def ring(twiml_node):
            for _ in range(2):
                twiml_node.play(url(request, "static", path="ringback.mp3"))
                twiml_node.pause(constants.RINGBACK_PAUSE_AMOUNT)

        redirect_url = url(request, "incoming_waiting_room", query={"gather_while_ringing": gather_while_ringing})
        if gather_while_ringing:
            gather: Gather = response.gather(redirect_url, **gather_kwargs)
            ring(gather)
        else:
            ring(response)
            response.redirect(redirect_url)

    else:
        # response.play(url(request, "static", path=f"hold-music-{random.randint(1, constants.NUM_HOLD_TRACKS)}.mp3"))
        gather: Gather = response.gather(
            url(request, "incoming_waiting_room", query={"gather_while_ringing": True}),
            **gather_kwargs,
        )
        gather.say(f"Music queue position: position {queue_position} and {queue_time} seconds")
        gather.pause(1)

    return response


def incoming_left_queue(request: Request):
    response = VoiceResponse()
    # TODO check if call was connected, otherwise voicemail
    response.say("Incoming left ended")
    return response


def voicemail(request: Request):
    response = VoiceResponse()
    response.say("Would leave voicemail")
    return response


def test(request: Request, test_user_id: int, test: str):
    return PlainTextResponse(f"hi, mom {type(test_user_id)}")


routes = [
    Route("/", index),
    TwilioRoute("/outgoing", outgoing),
    TwilioRoute("/outgoing/broadcast", outgoing_broadcast),
    TwilioRoute("/outgoing/broadcast/status", outgoing_broadcast_status_callback),
    TwilioRoute("/incoming", incoming),
    TwilioRoute("/incoming/waiting-room", incoming_waiting_room),
    TwilioRoute("/incoming/left-queue", incoming_left_queue),
    TwilioRoute("/voicemail", voicemail),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]


@contextlib.asynccontextmanager
async def lifespan(app):
    await manager.start()
    yield
    await manager.stop()


manager = CallManager()
app = Starlette(debug=config.DEBUG, routes=routes, lifespan=lifespan)
