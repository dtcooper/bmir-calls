import asyncio
import enum

from . import config, constants
from .utils import logger, retry_task_on_failure, twilio_client


class CallStatus(enum.StrEnum):
    RINGING = enum.auto()  # Incoming
    CONNECTED = enum.auto()  # Incoming
    OUTGOING = enum.auto()
    AVAILABLE = enum.auto()
    BLOCKED = enum.auto()


class CallManager:
    def __init__(self):
        self._queue_sid = None
        self._call_status = CallStatus.AVAILABLE
        self._call_sid = None
        self._ringing_sid = None
        self._unblock_event = asyncio.Event()
        self._tasks = None

    async def test(self):
        last_status = None
        while True:
            if self._call_status != last_status:
                logger.critical(f"Call status: {self._call_status}")
                last_status = self._call_status
            await asyncio.sleep(0.001)

    async def start(self):
        await self._init_queue()
        self._tasks = [
            asyncio.create_task(retry_task_on_failure(self._call_watcher_loop, name="broadcast call watcher")),
            asyncio.create_task(retry_task_on_failure(self._unblock_loop, name="broadcast call unblocker")),
            asyncio.create_task(self.test()),
        ]

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks)

    @property
    def call_status(self):
        return self._call_status

    @property
    def ringing_sid(self):
        return self._ringing_sid

    def update_broadcast_call(self, *, call_sid, call_status, ringing_sid=None):
        logger.debug(f"Updating call status to {str(call_status)} - {call_sid=} / {ringing_sid=}")
        self._call_sid = call_sid
        self._call_status = call_status
        self._ringing_sid = ringing_sid

    def hangup_broadcast_call(self):
        self.update_broadcast_call(call_sid=None, call_status=CallStatus.AVAILABLE)

    def temporarily_block_broadcast_calls(self):
        self._unblock_event.set()

    async def _init_queue(self):
        async for queue in await twilio_client.queues.stream_async():
            if queue.friendly_name == config.TWILIO_QUEUE_NAME:
                self._queue_sid = queue.sid
                break
        else:
            logger.warning(f"Twilio queue named {config.TWILIO_QUEUE_NAME} does not exist! Creating it.")
            queue = await twilio_client.queues.create_async(
                friendly_name=config.TWILIO_QUEUE_NAME, max_size=config.TWILIO_QUEUE_MAX_SIZE
            )
            self._queue_sid = queue.sid
        if queue.max_size != config.TWILIO_QUEUE_MAX_SIZE:
            await queue.update_async(max_size=config.TWILIO_QUEUE_MAX_SIZE)
            logger.warning(f"Updated queue max_size={config.TWILIO_QUEUE_MAX_SIZE}")
        logger.info(f"Got Twilio queue {config.TWILIO_QUEUE_NAME} ({self._queue_sid})")

    async def _call_watcher_loop(self):
        logger.info("Starting broadcast call watcher task")
        last_status = None
        while True:
            if self._call_sid is not None:
                call = await twilio_client.calls(self._call_sid).fetch_async()
                if last_status != call.status:
                    logger.critical(f"Current call status from API: {call.status}")
                    last_status = call.status
            else:
                last_status = None

            await asyncio.sleep(0.25)

    async def _unblock_loop(self):
        logger.info("Starting broadcast call unblocker task")
        while True:
            await self._unblock_event.wait()
            logger.debug(f"Temporarily blocking calls for {constants.UNBLOCK_TIMEOUT}s")
            self.update_broadcast_call(call_sid=None, call_status=CallStatus.BLOCKED)

            await asyncio.sleep(constants.UNBLOCK_TIMEOUT)

            if self.call_status == CallStatus.BLOCKED:
                self.hangup_broadcast_call()

            self._unblock_event.clear()
            logger.debug("Now unblocking calls")
