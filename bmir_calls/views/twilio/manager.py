import datetime
import enum
import logging

from twilio.base.exceptions import TwilioRestException

from django.conf import settings
from django.utils import timezone
from django.utils.functional import classproperty

from constance.codecs import dumps, loads
from constance.models import Constance

from ...twilio import client, create_or_find_queue


logger = logging.getLogger(__name__)


class CallStatus(enum.StrEnum):
    AVAILABLE = enum.auto()
    RINGING = enum.auto()  # Incoming
    CONNECTED = enum.auto()  # Incoming
    OUTGOING = enum.auto()


CONFIG_DB_KEY = "__call_manager_status__"
NEXT_VALIDATION_DB_KEY = "__call_manager_last_validation__"
VALIDATE_CALL_TIMEOUT = datetime.timedelta(seconds=45)


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
    _queue = None

    def __init__(self, *, initialize=False):
        self._initialized: bool = False
        self._status: CallStatus = None
        self._call_sid: str = None
        self._ringing_sid: None
        self._next_validation: datetime.datetime = None
        if initialize:
            self._initialize_and_validate()

    def _needs_validation(self):
        if self._next_validation is None:
            self._next_validation = load_db_value(NEXT_VALIDATION_DB_KEY, default=False)
        return not self._next_validation or self._next_validation <= timezone.now()

    def _initialize_and_validate(self):
        if not self._initialized:
            self.refresh_from_db()
        if self._needs_validation():
            self.validate_from_server()

    def _save(self):
        if not self._initialized:
            raise Exception("Can't save uninitialized CallManager!")
        serialize = {k.removeprefix("_"): getattr(self, k) for k in ("_status", "_call_sid", "_ringing_sid")}
        save_db_value(CONFIG_DB_KEY, {k: v for k, v in serialize.items() if v is not None})

    @staticmethod
    def _delete():
        for key in (CONFIG_DB_KEY, NEXT_VALIDATION_DB_KEY):
            delete_db_value(key)

    @classproperty
    def queue(cls):
        if cls._queue is None:
            cls._queue = create_or_find_queue(settings.TWILIO_QUEUE_NAME)
        return cls._queue

    @property
    def status(self) -> CallStatus:
        self._initialize_and_validate()
        return self._status

    @property
    def call_sid(self) -> None | str:
        self._initialize_and_validate()
        return self._call_sid

    @property
    def ringing_sid(self) -> None | str:
        self._initialize_and_validate()
        return self._call_sid

    def __repr__(self):
        s = f"<CallManager status={self.status}"
        if self.call_sid is not None:
            s += f" call_sid={self.call_sid}"
        if self.ringing_sid is not None:
            s += f" ringing_sid={self.ringing_sid}"
        return f"{s}>"

    def set_status(self, status, *, call_sid=None, ringing_sid=None, save=True):
        if status not in CallStatus:
            raise ValueError(f"Invalid call {status=}")

        self._call_sid = self._ringing_sid = None
        self._status = CallStatus(status)

        if status != CallStatus.AVAILABLE:
            if call_sid is None:
                raise ValueError(f"Must set call_sid for {status=}")
            self._call_sid = call_sid

            if status == CallStatus.RINGING:
                if ringing_sid is None:
                    raise ValueError(f"Must set ringing_sid for {status=}")
                self._ringing_sid = ringing_sid

        self._initialized = True
        if save:
            logger.info(f"Set call status to {self.status}")
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

    def validate_from_server(self):
        self._next_validation = timezone.now() + VALIDATE_CALL_TIMEOUT
        save_db_value(NEXT_VALIDATION_DB_KEY, self._next_validation)

        if self.call_sid is not None:
            try:
                call = client.calls(self.call_sid).fetch()
            except TwilioRestException:
                logger.warning(f"Error fetching call during verify {self.call_sid}. Not verifying.")
                return

            if call.status not in ("queued", "ringing", "in-progress"):
                logger.warning(f"Broadcast call found in state {call.status!r}, so hanging up.")
                self.set_status(CallStatus.AVAILABLE)

        # Not an 'elif' since we could have reset the call_sid from above
        if self.call_sid is None:
            sip_addr = f"sip:{settings.TWILIO_SIP_BROADCAST_USER}@{settings.TWILIO_SIP_DOMAIN}"
            for outgoing in (False, True):
                for status in ("queued", "ringing", "in-progress"):
                    calls = client.calls.list(status=status, limit=1, **{"from_" if outgoing else "to": sip_addr})
                    if calls:
                        call = calls[0]
                        if outgoing:
                            logger.info("Found an untracked outgoing call in progress! Tracking it.")
                            self.set_status(CallStatus.OUTGOING, call_sid=call.sid)
                        else:
                            set_ringing_status = False
                            if status in ("queued", "ringing"):
                                members = self.queue.members.list(limit=1)
                                if members:
                                    logger.info("Found an untracked incoming ringing call in progress. Tracking it.")
                                    member = members[0]
                                    self.set_status(CallStatus.RINGING, call_sid=call.sid, ringing_sid=member.call_sid)
                                    set_ringing_status = True

                            if not set_ringing_status:
                                self.set_status(CallStatus.CONNECTED, call_sid=call.sid)
                                logger.info("Found an untracked incoming accepted call in progress. Tracking it.")
                        return
