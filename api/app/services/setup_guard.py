"""1.0.4 — o'rnatish kodi noto'g'ri urinishlari cheklovi.

`prov_guard.py`dagi `FailureGuard` qayta ishlatiladi (bir xil jarayon-ichi
qolip), faqat bu yerga xos pastroq limit: 15 daqiqada 5 ta xato urinish ->
IP 15 daqiqa bloklanadi.
"""
from __future__ import annotations

from app.services.prov_guard import FailureGuard

LIMIT = 5
WINDOW_S = 900.0
BLOCK_S = 900.0

guard = FailureGuard(limit=LIMIT, window_s=WINDOW_S, block_s=BLOCK_S)
