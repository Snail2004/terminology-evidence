from __future__ import annotations

import threading
import time
import urllib.parse
from typing import Callable, Protocol


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class RateLimiter(Protocol):
    def wait(self, url: str) -> None: ...


class HostRateLimiter:
    def __init__(
        self,
        *,
        min_interval_seconds: float = 0.5,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must not be negative")
        self._interval = min_interval_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").casefold()
        if not host:
            raise ValueError("rate-limited URL lacks a hostname")
        with self._lock:
            now = self._clock()
            next_allowed = self._next_allowed.get(host, now)
            delay = max(0.0, next_allowed - now)
            if delay:
                self._sleeper(delay)
            self._next_allowed[host] = max(now, next_allowed) + self._interval


class NoopRateLimiter:
    def wait(self, url: str) -> None:
        del url


__all__ = ["HostRateLimiter", "NoopRateLimiter", "RateLimiter"]
