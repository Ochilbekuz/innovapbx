"""M4a §0 (4-qatlam) — provizioning IP xato limiti: `window_s` ichida `limit` ta 404/403 → IP `block_s` davomida 403.

Jarayon ichidagi holat (API bitta uvicorn jarayoni — `rate_limit.py` bilan bir xil asos); restartda nolga tushadi.
Xotira chegaralangan: `max_ips` dan oshsa, eng eski (bloklanmagan) IP'lar tashlanadi.
"""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

FAIL_LIMIT = 20
FAIL_WINDOW_S = 600.0
BLOCK_S = 1800.0
MAX_IPS = 10_000


class FailureGuard:
    def __init__(self, clock: Callable[[], float] = time.monotonic, *, limit: int = FAIL_LIMIT,
                 window_s: float = FAIL_WINDOW_S, block_s: float = BLOCK_S, max_ips: int = MAX_IPS) -> None:
        self._clock = clock
        self._limit, self._window_s, self._block_s, self._max_ips = limit, window_s, block_s, max_ips
        self._failures: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window_s(self) -> float:
        return self._window_s

    def is_blocked(self, ip: str) -> bool:
        until = self._blocked_until.get(ip)
        if until is None:
            return False
        if self._clock() < until:
            return True
        del self._blocked_until[ip]
        return False

    def record_failure(self, ip: str) -> bool:
        """Xatoni qayd etadi; shu xato bilan IP YANGI bloklangan bo'lsa `True` (alert faqat bir marta)."""
        now = self._clock()
        hits = self._failures.setdefault(ip, deque())
        while hits and now - hits[0] >= self._window_s:
            hits.popleft()
        hits.append(now)
        self._trim()
        if len(hits) < self._limit:
            return False
        self._failures.pop(ip, None)
        self._blocked_until[ip] = now + self._block_s
        return True

    def _trim(self) -> None:
        while len(self._failures) > self._max_ips:
            del self._failures[next(iter(self._failures))]

    def reset(self) -> None:
        self._failures.clear()
        self._blocked_until.clear()


guard = FailureGuard()
