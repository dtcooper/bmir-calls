import asyncio
import enum
import logging
from time import monotonic as now

from . import constants, settings
from .utils import retry_task_on_failure, twilio_client


logger = logging.getLogger(__name__)


class CallStatus(enum.StrEnum):
    RINGING = enum.auto()  # Incoming
    CONNECTED = enum.auto()  # Incoming
    OUTGOING = enum.auto()
    AVAILABLE = enum.auto()
    BLOCKED = enum.auto()


CALL_ESTABLISHED_STATUSES = (CallStatus.RINGING, CallStatus.CONNECTED, CallStatus.OUTGOING)


class CallManager:
    def __init__(self):
        self._queue_sid = None
        self._call_status = CallStatus.AVAILABLE
        self._call_sid = None
        self._blocked_until = None
        self._tasks = None

    async def start(self):
        await self._init_queue()
        self._tasks = [
            asyncio.create_task(retry_task_on_failure(self._call_watcher_loop, name="broadcast call watcher")),
        ]

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks)

    @property
    def call_status(self) -> CallStatus:
        if self._blocked_until is not None and now() < self._blocked_until:
            return CallStatus.BLOCKED
        return self._call_status

    @property
    def call_sid(self) -> str | None:
        if self.call_status in CALL_ESTABLISHED_STATUSES:
            return self._call_sid
        return None

    def update_broadcast_call(self, *, call_sid, call_status):
        if settings.DEBUG:
            logger.debug(f"Updating broadcast call status to {str(call_status)} - {call_sid=}")
        else:
            logger.info(f"Broadcast call status to: {str(call_status)}")
        self._blocked_until = None
        self._call_sid = call_sid
        self._call_status = call_status

    def hangup_broadcast_call(self):
        self.update_broadcast_call(call_sid=None, call_status=CallStatus.AVAILABLE)

    @staticmethod
    async def _get_active_broadcast_call():
        sip_address = f"sip:{settings.TWILIO_SIP_BROADCAST_USER}@{settings.TWILIO_SIP_DOMAIN}"
        for address, is_outgoing in (({"from_": sip_address}, True), ({"to": sip_address}, False)):
            for status in ("queued", "ringing", "in-progress"):
                calls = await twilio_client.calls.list_async(status=status, page_size=1, **address)
                if len(calls) >= 1:
                    return calls[1], CallStatus.OUTGOING if is_outgoing else CallStatus.CONNECTED
        return None, None

    async def reject_incoming_broadcast_call(self):
        if self.call_sid is None:
            logger.info("Call was rejected but no call is tracked, so attempting to track the broadcast call.")
            self.temporarily_block_broadcast_calls()

            call, call_status = await self._get_active_broadcast_call()
            if call is None:
                logger.warning("Call was rejected when no active call appeared to be in place.")
                self.hangup_broadcast_call()
            else:
                logger.warning(f"Found an active {call_status} call, and updating manager to reflect that.")
                self.update_broadcast_call(call_sid=call, call_status=call_status)

    def temporarily_block_broadcast_calls(self):
        self.hangup_broadcast_call()
        self._blocked_until = now() + constants.BLOCK_CALL_TIMEOUT

    async def _init_queue(self):
        async for queue in await twilio_client.queues.stream_async():
            if queue.friendly_name == settings.TWILIO_QUEUE_NAME:
                self._queue_sid = queue.sid
                break
        else:
            logger.warning(f"Twilio queue named {settings.TWILIO_QUEUE_NAME} does not exist! Creating it.")
            queue = await twilio_client.queues.create_async(
                friendly_name=settings.TWILIO_QUEUE_NAME, max_size=settings.TWILIO_QUEUE_MAX_SIZE
            )
            self._queue_sid = queue.sid
        if queue.max_size != settings.TWILIO_QUEUE_MAX_SIZE:
            await queue.update_async(max_size=settings.TWILIO_QUEUE_MAX_SIZE)
            logger.warning(f"Updated queue max_size={settings.TWILIO_QUEUE_MAX_SIZE}")
        logger.info(f"Got Twilio queue {settings.TWILIO_QUEUE_NAME} ({self._queue_sid})")

    async def _call_watcher_loop(self):
        logger.info("Starting broadcast call watcher task")
        while True:
            if self.call_sid is not None and self.call_status in CALL_ESTABLISHED_STATUSES:
                call = await twilio_client.calls(self.call_sid).fetch_async()
                if call.status not in ("queued", "ringing", "in-progress"):
                    logger.warning(f"Broadcast call found in state {call.status!r}, so hanging up.")
                    self.hangup_broadcast_call()

            await asyncio.sleep(constants.CALL_WATCHER_TIMEOUT)
