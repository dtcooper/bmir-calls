import asyncio
from functools import wraps
import inspect
import logging
import random
from urllib.parse import urlencode

from twilio.http.async_http_client import AsyncTwilioHttpClient
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from twilio.twiml import TwiML

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from . import settings


if settings.DEBUG:
    import pprint
    from xml.dom.minidom import parseString as parse_xml_string


logger = logging.getLogger(__name__)


validator = RequestValidator(str(settings.TWILIO_AUTH_TOKEN))
twilio_client = TwilioClient(
    str(settings.TWILIO_ACCOUNT_SID), str(settings.TWILIO_AUTH_TOKEN), http_client=AsyncTwilioHttpClient()
)


def parse_sip_address(address):
    return address.removeprefix("sip:").split("@")[0]


class TwilioRoute(Route):
    def __init__(self, path, endpoint, methods=None, debug=False, **kwargs):
        if methods is None:
            methods = ["POST"]

        endpoint_signature = {}
        for name, param in inspect.signature(endpoint).parameters.items():
            if param.annotation in (int, str, bool):
                endpoint_signature[name] = (
                    "".join(word[:1].upper() + word[1:] for word in name.split("_")),  # camel_name
                    param.annotation,  # type
                    param.default,  # default
                )

        @wraps(endpoint)
        async def new_endpoint(request: Request):
            form = await request.form()

            # Check Twilio signature
            authorized = False
            signature = request.headers.get("X-Twilio-Signature")

            if signature:
                authorized = validator.validate(str(request.url), form, signature)

            if not authorized and not settings.DEBUG:
                logger.warning("Invalid Twilio signature header")
                return Response(status_code=403)

            if settings.DEBUG_VERBOSE_REQUESTS:
                logger.debug(f"Request {authorized=} url={request.url} POST=\n{pprint.pformat(dict(form))}")

            kwargs = {}  # Parse out arguments
            form = await request.form()
            for name, (camel_name, type, default) in endpoint_signature.items():
                path_param = request.path_params.get(name)
                if path_param is None:
                    value = form.get(camel_name)
                    if value is None:
                        value = request.query_params.get(name)
                else:
                    value = path_param

                if default == inspect.Parameter.empty:
                    if value is None:
                        error = f"Expecting POST ({camel_name!r}) or GET/path ({name!r}) parameter!"
                        logger.error(error)
                        return PlainTextResponse(error, status_code=400)

                if value is None:
                    value = default
                elif path_param is None:  # Type conversation already done (TODO: check)
                    if type == int:
                        value = int(value or "0")
                    elif type == bool:
                        value = value.lower() == "true"

                kwargs[name] = value

            if asyncio.iscoroutinefunction(endpoint):
                response = await endpoint(request, **kwargs)
            else:
                response = endpoint(request, **kwargs)

            if isinstance(response, TwiML):
                twiml = str(response)
                if settings.DEBUG_VERBOSE_REQUESTS:
                    xml = parse_xml_string(twiml).toprettyxml(indent=" " * 4).strip()
                    logger.debug(f'Response url={request.url} XML=\n{xml}')
                response = Response(twiml, media_type="application/xml")

            return response

        super().__init__(path, new_endpoint, methods=methods, **kwargs)


class EmptyResponse(Response):
    def __init__(self):
        super().__init__(status_code=204)


async def retry_task_on_failure(coro, *args, name=None, **kwargs):
    running = True
    try_num = 1
    name = name or f"{coro.__name__}()"
    while running:
        try:
            if try_num > 1:
                logger.debug(f"Running try #{try_num} of {name}")
            else:
                logger.debug(f"Running retry task {name}")
            value = await coro(*args, **kwargs)
        except asyncio.CancelledError:
            logger.debug(f"Cancelled try task {name}")
            running = False
        except Exception:
            sleep_time = random.uniform(0.75, 1.5)
            logger.exception(f"Error in try #{try_num} of {name}, running again in {round(sleep_time, 3)}s")
            try_num += 1
            await asyncio.sleep(sleep_time)
        else:
            logger.debug(f"Try task {name} cleanly exited. Exiting retry loop.")
            return value
