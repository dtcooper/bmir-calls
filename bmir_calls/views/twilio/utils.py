import logging
from pathlib import Path
import pprint
import re
from urllib.parse import urlencode

from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather as BaseGather, TwiML, VoiceResponse as BaseVoiceResponse

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.templatetags.static import static
from django.urls import reverse

from constance import config
from ninja import NinjaAPI
from ninja.parser import Parser
from ninja.renderers import BaseRenderer


if settings.DEBUG_VERBOSE_REQUESTS:
    import xml.dom.minidom  # No need to import in production


logger = logging.getLogger(__name__)

underscore_converter_re = re.compile(r"(?<!^)(?=[A-Z])")


def generate_url_for(namespace):
    def url_for(name, _external=False, **params):
        url = reverse(f'twilio_{name if ":" in name else f"{namespace}:{name}"}')
        if params:
            url = f"{url}?{urlencode(params)}"
        if _external:
            url = f"https://{settings.DOMAIN_NAME}{url}"
        return url

    return url_for


class EmptyResponse(HttpResponse):
    def __init__(self, *args, **kwargs):
        status = kwargs.pop("status", 204)
        super().__init__(*args, status=status, **kwargs)


class TwiMLRenderer(BaseRenderer):
    media_type = "text/xml"

    def render(self, request, data, *, response_status):
        if isinstance(data, TwiML):
            data = str(data)

            if settings.DEBUG_VERBOSE_REQUESTS:
                data = xml.dom.minidom.parseString(data).toprettyxml(indent=" " * 4).strip()
                logger.info(f"Responding to {request.get_full_path()} with\n{data}\n")

        return data


class TwilioParser(Parser):
    # Converts PascalCase and camelCase to Pythonic underscores
    def parse_querydict(self, data, list_fields, request):
        result = super().parse_querydict(data, list_fields, request)
        return {underscore_converter_re.sub("_", k).lower(): v for k, v in result.items()}


class SkipTwilioPlayMixin:
    def play(self, url, *args, _external=False, **kwargs):
        is_media = url.startswith(settings.MEDIA_URL)
        if is_media:
            full_url = url
        else:
            full_url = f"bmir_calls/twilio/sounds/{url}.mp3"
            if settings.DEBUG and not finders.find(full_url):
                logger.warning(f"Couldn't find path for <Play /> verb: {full_url}!")
                if settings.DEBUG:
                    super().say("Warning! Path does not exist. Check logs.")
            full_url = static(full_url)

        if settings.DEBUG and config.SKIP_TWILIO_PLAY:
            super().say(re.sub(r"[\W\s]+", " ", Path(url).stem if is_media else url).strip().lower())
        else:
            if _external:
                full_url = f"https://{settings.DOMAIN_NAME}{full_url}"
            super().play(full_url, *args, **kwargs)


class Gather(SkipTwilioPlayMixin, BaseGather):
    pass


class VoiceResponse(SkipTwilioPlayMixin, BaseVoiceResponse):
    def gather(self, *args, **kwargs) -> Gather:
        return self.nest(Gather(*args, **kwargs))


validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)


def twilio_auth(request):
    authorized = False
    signature = request.headers.get("X-Twilio-Signature")
    if signature:
        authorized = validator.validate(request.build_absolute_uri(), request.POST, signature)

    if settings.DEBUG:
        if not authorized:
            logger.warning("Request not properly signed from Twilio, but allowing it since DEBUG = True")
            authorized = True
    if settings.DEBUG_VERBOSE_REQUESTS:
        logger.info(f"path={request.get_full_path()} - POST:\n{pprint.pformat(dict(request.POST))}")
        session = dict(request.session)
        if session:
            logger.info(f"path={request.get_full_path()} - Session:{'\n' + pprint.pformat(dict(session))}")

    return authorized


def create_ninja_api(name) -> NinjaAPI:
    return NinjaAPI(
        renderer=TwiMLRenderer(),
        parser=TwilioParser(),
        urls_namespace=f"twilio_{name}",
        auth=twilio_auth,
        docs_url=None,
        openapi_url=None,
    )
