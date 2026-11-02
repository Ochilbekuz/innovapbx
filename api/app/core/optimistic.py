"""Optimistik qulf — PATCH so'rovlarida `updated_at` solishtirish.
Barcha routerlar (extensions/trunks/inbound_routes) bir xil tekshiruvni
ishlatadi, shuning uchun bir joyga chiqarilgan (DRY)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.errors import ApiError

_STALE = ApiError(409, "stale", "Ma'lumot eskirgan — sahifani qayta yuklang")


def naive_utc(value: datetime) -> datetime:
    """Solishtirish uchun bazadan kelgan va so'rovdagi vaqtni bir shaklga keltiradi."""
    if value.tzinfo is None:
        return value.replace(microsecond=0)
    return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


def check_not_stale(current: datetime, expected: datetime) -> None:
    """`current != expected` bo'lsa 409 `stale` ko'taradi."""
    if naive_utc(current) != naive_utc(expected):
        raise _STALE
