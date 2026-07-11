from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
import time

_WINDOW_SECONDS = 3.0
_WARNING_THRESHOLD = 5
_events = defaultdict(deque)
_warned = set()


def _log_path():
    try:
        from app_paths import writable_path
        path = writable_path("logs/performance_debug.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        logs_dir = Path(__file__).resolve().parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "performance_debug.log"


def log_event(name, **fields):
    now = time.monotonic()
    bucket = _events[name]
    bucket.append(now)
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    count = len(bucket)
    parts = [f"[DEBUG] {name} count={count}"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    lines = [" ".join(parts)]
    warning_key = (name, int(now // _WINDOW_SECONDS))
    if count > _WARNING_THRESHOLD and warning_key not in _warned:
        _warned.add(warning_key)
        lines.append(f"[WARNING] repeated render detected: {name} count={count} in 3s")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = _log_path()
    with path.open("a", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{stamp} {line}\n")
