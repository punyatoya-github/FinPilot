"""In-memory sliding-window rate limiter (single-process; use Redis when scaling out)."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

_SWEEP_THRESHOLD = 10_000


class RateLimiter:
    """Allows `limit` hits per `window_seconds` per key. `limit <= 0` disables limiting."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._limit > 0

    def check(self, key: str) -> float:
        """Record a hit. Returns 0.0 if allowed, else seconds until a slot frees up."""
        if not self.enabled:
            return 0.0
        now = self._clock()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(hits[0] + self._window - now, 0.001)
            hits.append(now)
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(cutoff)
            return 0.0

    def _sweep(self, cutoff: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
        for key in stale:
            del self._hits[key]
