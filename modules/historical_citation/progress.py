from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional, TextIO


PROGRESS_SCHEMA_VERSION = "historical_citation.progress.v1"


def build_progress_event(
    event: str,
    *,
    phase: Optional[str] = None,
    current: Optional[int] = None,
    total: Optional[int] = None,
    global_current: Optional[int] = None,
    global_total: Optional[int] = None,
    candidate_id: Optional[str] = None,
    footnote_id: Optional[str] = None,
    status: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
    **payload: Any,
) -> Dict[str, Any]:
    message: Dict[str, Any] = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    optional = {
        "phase": phase,
        "current": current,
        "total": total,
        "global_current": global_current,
        "global_total": global_total,
        "candidate_id": candidate_id,
        "footnote_id": footnote_id,
        "status": status,
        "metrics": metrics,
        **payload,
    }
    message.update({key: value for key, value in optional.items() if value is not None})
    return message


class ProgressReporter:
    """Emit JSONL progress events and optional periodic heartbeats."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        interval_seconds: float = 30.0,
        stream: Optional[TextIO] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.interval_seconds = max(0.0, float(interval_seconds or 0.0))
        self.stream = stream or sys.stdout
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {}
        self._stopped = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if self.enabled and self.interval_seconds > 0:
            self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._thread.start()

    def update(self, **state: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._state.update({key: value for key, value in state.items() if value is not None})

    def event(self, event: str, **payload: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            state = dict(self._state)
        message = build_progress_event(event, **{**state, **payload})
        print(json.dumps(message, ensure_ascii=False), file=self.stream, flush=True)

    def close(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _heartbeat_loop(self) -> None:
        while not self._stopped.wait(self.interval_seconds):
            self.event("progress_heartbeat")

    def __enter__(self) -> "ProgressReporter":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
