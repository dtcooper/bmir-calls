from pathlib import Path


HOLD_TRACKS = [p.name for p in (Path(__file__).parent.parent / "static").iterdir() if p.name.startswith("hold-music")]
RINGBACK_PAUSE_AMOUNT = 4
BLOCK_CALL_TIMEOUT = 15
CALL_WATCHER_TIMEOUT = 30
BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT = 45
