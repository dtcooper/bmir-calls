import enum
import json
import logging

from constance.codecs import dumps, loads
from constance.models import Constance


logger = logging.getLogger(__name__)


class CallStatus(enum.StrEnum):
    AVAILABLE = enum.auto()
    RINGING = enum.auto()  # Incoming
    CONNECTED = enum.auto()  # Incoming
    OUTGOING = enum.auto()
    BLOCKED = enum.auto()


CONFIG_KEY = "__call_manager_status__"


class CallManager:
    def __init__(self):
        self.refresh_from_db()

    @property
    def status(self) -> CallStatus:
        return self._status

    @property
    def call_sid(self) -> None | str:
        return self._call_sid

    @property
    def ringing_sid(self) -> None | str:
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

        serialized = {"status": status}
        self._call_sid = self._ringing_sid = None

        if status in (CallStatus.RINGING, CallStatus.CONNECTED, CallStatus.OUTGOING):
            if call_sid is None:
                raise ValueError(f"Must set call_sid for {status=}")
            self._call_sid = serialized["call_sid"] = call_sid

            if status == CallStatus.RINGING:
                if ringing_sid is None:
                    raise ValueError(f"Must set ringing_sid for {status=}")
                self._ringing_sid = serialized["ringing_sid"] = ringing_sid

        self._status = CallStatus(status)
        if save:
            Constance.objects.update_or_create(key=CONFIG_KEY, defaults={"value": dumps(serialized)})

    def refresh_from_db(
        self,
    ):
        try:
            kwargs = loads(Constance.objects.values_list("value", flat=True).get(key=CONFIG_KEY))
            self.set_status(**kwargs, save=False)
        except Exception:
            kwargs = {"status": CallStatus.AVAILABLE}
            logger.info(f"An exception occurred while reading {CONFIG_KEY} constance config. Recovering.")
            Constance.objects.update_or_create(key=CONFIG_KEY, defaults={"value": dumps(kwargs)})
            self.set_status(**kwargs, save=False)
