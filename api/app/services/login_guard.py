"""M12 C M5 — `/auth/login` uchun IP bo'yicha urinish cheklovi.

`prov_guard.py`dagi `FailureGuard` qayta ishlatiladi (`setup_guard.py` BILAN
BIR XIL qolip): bir IP 15 daqiqada 10 marta xato urinsa, shu IP 15 daqiqaga
bloklanadi (423 `locked`). Bu cheklov HISOB emas, IP bo'yicha — shuning uchun
qaysi login mavjud/yo'qligini oshkor qilmaydi va bitta anonim IP hisobni
abadiy qulflay olmaydi (hisob-darajadagi qulf `_register_failed_login`da
alohida, pastroq chegara bilan davom etadi)."""
from __future__ import annotations

from app.services.prov_guard import FailureGuard

LIMIT = 10
WINDOW_S = 900.0
BLOCK_S = 900.0

guard = FailureGuard(limit=LIMIT, window_s=WINDOW_S, block_s=BLOCK_S)
