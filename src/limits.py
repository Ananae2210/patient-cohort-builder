"""Usage limits, so a public copy of the app can't use up your free AI quota.

Two limits, both over a rolling hour, both changeable in .env:
  MAX_QUESTIONS_PER_HOUR          all visitors together (default 60)
  MAX_QUESTIONS_PER_VISITOR_HOUR  one browser session   (default 15)
Only questions that reach the AI count. Repeated questions answered from the cache are free.
"""

import os
import threading
import time
from collections import deque


class RateLimiter:
    """Allow at most `limit` events in any `window_s` seconds. Safe to share between threads."""

    def __init__(self, limit: int, window_s: float = 3600):
        self.limit = limit
        self.window_s = window_s
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, now: float) -> None:
        while self._times and now - self._times[0] >= self.window_s:
            self._times.popleft()

    def try_acquire(self, now: float | None = None) -> bool:
        """Record one event and return True, or return False if the limit is reached."""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._trim(now)
            if len(self._times) >= self.limit:
                return False
            self._times.append(now)
            return True

    def seconds_until_free(self, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._trim(now)
            if len(self._times) < self.limit:
                return 0
            return int(self.window_s - (now - self._times[0])) + 1


def global_limit() -> int:
    return int(os.getenv("MAX_QUESTIONS_PER_HOUR", "60"))


def visitor_limit() -> int:
    return int(os.getenv("MAX_QUESTIONS_PER_VISITOR_HOUR", "15"))
