import datetime
import enum
import logging

from twilio.base.exceptions import TwilioRestException

from django.conf import settings
from django.utils import timezone

from constance.codecs import dumps, loads
from constance.models import Constance

from ...twilio import client, get_sip_address


logger = logging.getLogger(__name__)


class CallStatus(enum.StrEnum):
    AVAILABLE = enum.auto()
    INCOMING = enum.auto()
    OUTGOING = enum.auto()


CONFIG_DB_KEY = "__bmir_status__"
NEXT_VALIDATION_DB_KEY = "__bmir_next_validation__"
VALIDATE_CALL_TIMEOUT = datetime.timedelta(seconds=30)


def load_db_value(key, *, default=None):
    try:
        return loads(Constance.objects.values_list("value", flat=True).get(key=key))
    except Exception:
        logger.warning(f"Error loading constance key={key}. Using default={default}.", exc_info=True)
        return default


def save_db_value(key, value):
    Constance.objects.update_or_create(key=key, defaults={"value": dumps(value)})


def delete_db_value(key):
    Constance.objects.filter(key=key).delete()


class CallManager:
    def __init__(self, *, initialize=False):
        self._initialized: bool = False
        self._called_validate_from_server_once: bool = False
        self._status: tuple[CallStatus, str | None] = (None, None)
        self._next_validation: datetime.datetime = None
        if initialize:
            self._initialize_and_validate(force_validate=True)

    def _initialize_and_validate(self, *, force_validate=False):
        if not self._initialized:
            self.refresh_from_db()
        if force_validate or not self._called_validate_from_server_once:
            self.validate_from_server(force=force_validate)

    def _save(self):
        if not self._initialized:
            raise Exception("Can't save uninitialized CallManager!")
        status, sid = self._status
        save_db_value(CONFIG_DB_KEY, {"status": status, "sid": sid})

    @staticmethod
    def _delete():
        for key in (CONFIG_DB_KEY, NEXT_VALIDATION_DB_KEY):
            delete_db_value(key)

    @property
    def status(self) -> CallStatus:
        self._initialize_and_validate()
        return self._status[0]

    @property
    def sid(self) -> None | str:
        self._initialize_and_validate()
        return self._status[1]

    def __repr__(self):
        s = f"<CallManager status={self.status}"
        if self.sid is not None:
            s += f" sid={self.sid}"
        return f"{s}>"

    def set_status(self, status, *, sid=None, save=True):
        if status not in CallStatus:
            raise ValueError(f"Invalid call status={str(status)}")

        status = CallStatus(status)

        if status != CallStatus.AVAILABLE and sid is None:
            raise ValueError(f"Must set sid for status={str(status)}")

        self._initialized = True
        self._status = (status, sid)
        if save:
            logger.info(f"Set call status to status={str(self.status)}")
            self._save()

    def refresh_from_db(self):
        kwargs = load_db_value(key=CONFIG_DB_KEY)
        try:
            self.set_status(**kwargs, save=False)
        except Exception:
            logger.warning(
                f"An exception occurred while reading {CONFIG_DB_KEY} constance config. Setting status=available",
                exc_info=True,
            )
            self.set_status(CallStatus.AVAILABLE)

    def validate_from_server(self, *, force=True):
        called_once = self._called_validate_from_server_once
        self._called_validate_from_server_once = True

        if not force and called_once:
            return

        if not self._initialized:
            self.refresh_from_db()

        if not force:
            if self._next_validation is None:
                self._next_validation = load_db_value(NEXT_VALIDATION_DB_KEY)
                if self._next_validation is None:
                    self._next_validation = timezone.now() + VALIDATE_CALL_TIMEOUT
                    save_db_value(NEXT_VALIDATION_DB_KEY, self._next_validation)

            if self._next_validation >= timezone.now():
                # Skip until the next time a validation is needed
                return

        save_db_value(NEXT_VALIDATION_DB_KEY, timezone.now() + VALIDATE_CALL_TIMEOUT)

        if self.sid is not None:
            try:
                call = client.calls(self.sid).fetch()
            except TwilioRestException:
                logger.warning(f"Error fetching call during verify {self.sid}. Not verifying.")
                return

            if call.status not in ("queued", "ringing", "in-progress"):
                logger.warning(f"Broadcast call found in state {call.status!r}, so hanging up.")
                self.set_status(CallStatus.AVAILABLE)

        # Not an 'elif' since we could have reset the sid from above
        if self.sid is None:
            sip_addr = get_sip_address(settings.TWILIO_SIP_BROADCAST_USER)
            for outgoing in (False, True):
                for status in ("queued", "ringing", "in-progress"):
                    calls = client.calls.list(status=status, limit=1, **{"from_" if outgoing else "to": sip_addr})
                    if calls:
                        call = calls[0]
                        logger.info(f"Found an untracked {'outgoing' if outgoing else 'incoming'} call in progress!")
                        self.set_status(CallStatus.OUTGOING if outgoing else CallStatus.INCOMING, sid=call.sid)
                        return
