"""Jarayon ichidagi siljuvchi oyna chastota cheklovchisi (M3a §2: `/me/softphone` 30/daq
foydalanuvchiga). API bitta uvicorn jarayonida ishlaydi (api/Dockerfile CMD) — umumiy
holat shart emas; jarayon qayta ishga tushsa hisob nolga tushadi (xavfsiz tomonga emas,
lekin bu cheklov suiiste'molni sekinlatish uchun, autentifikatsiya emas)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_s: float = 60.0) -> bool:
        """Oxirgi `window_s` ichida `limit`dan kam bo'lsa — qayd etib `True`."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= window_s:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True
