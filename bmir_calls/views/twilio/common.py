import logging
from pathlib import Path
import pprint
import re

from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather as TwilioGather, VoiceResponse as TwilioVoiceResponse

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from constance import config
from ninja import NinjaAPI
from ninja.parser import Parser
from ninja.renderers import BaseRenderer


underscore_converter_re = re.compile(r"(?<!^)(?=[A-Z])")
depunctuate_words_re = re.compile(r"[^a-z]+")
logger = logging.getLogger(f"calls.{__name__}")


class TwiMLRenderer(BaseRenderer):
    media_type = "text/xml"

    # Accepts twilio's VoiceReponse
    def render(self, request, data, *, response_status):
        response = str(data)

        if settings.DEBUG:
            import xml.dom.minidom  # No need to import in production

            response = xml.dom.minidom.parseString(response).toprettyxml(indent=" " * 4)
            logger.info(f"Responding to {request.get_full_path()} with\n{response}\n")

        return response


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
            full_url = f"api/twilio/sounds/{url}.mp3"
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


class Gather(SkipTwilioPlayMixin, TwilioGather):
    pass


class VoiceResponse(SkipTwilioPlayMixin, TwilioVoiceResponse):
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
        logger.info(f"path={request.get_full_path()} - POST:\n{pprint.pformat(dict(request.POST))}")
        if request.session:
            logger.info(
                f"path={request.get_full_path()} -"
                f" Session:{'\n' + pprint.pformat(dict(request.session)) if dict(request.session) else ' <none>'}"
            )

    return authorized


def create_ninja_api(name) -> NinjaAPI:
    return NinjaAPI(
        renderer=TwiMLRenderer(),
        parser=TwilioParser(),
        urls_namespace=f"twilio_{name}",
        auth=twilio_auth,
        docs_url=None,
    )
