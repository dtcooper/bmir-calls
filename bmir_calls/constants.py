from pathlib import Path


HOLD_TRACKS = tuple(
    p.stem
    for p in (Path(__file__).parent / "static" / "bmir_calls" / "twilio" / "sounds").iterdir()
    if p.suffix == ".mp3" and p.stem.startswith("hold-music-")
)
RINGBACK_PAUSE_AMOUNT = 4
BLOCK_CALL_TIMEOUT = 15
CALL_WATCHER_TIMEOUT = 30
BROADCAST_OUTGOING_CALL_FROM_QUEUE_TIMEOUT = 45
