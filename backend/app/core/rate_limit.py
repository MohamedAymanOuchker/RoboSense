"""A small in-process, per-key fixed-window rate limiter.

A single FastAPI process owns ingestion (see the project non-goals — no queues,
no distributed infrastructure), so an in-memory limiter is the right tool. It is
thread-safe and keyed by device id.
"""

import time
from threading import Lock


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._state: dict[str, tuple[float, int]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Record a hit for ``key``. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._state.get(key, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0
            count += 1
            self._state[key] = (window_start, count)
            if count <= self.max_requests:
                return True, 0.0
            return False, self.window_seconds - (now - window_start)
