"""Zaxira jadvali — vaqt hisoblash sof funksiyalari (m4b-contract.md §0).

Fon vazifasi (`backup_scheduler.run_forever`) har daqiqa `is_due()` ni chaqiradi —
bu modul DB/fayl bilan ISHLAMAYDI, faqat "hozir ishga tushirish kerakmi" savoliga
javob beradi. Server o'chiq bo'lib bir slot o'tkazib yuborilsa — ishga tushgach
BIR marta (catch-up): `last_run_at` oxirgi rejalashtirilgan zaxiranikidan eski
bo'lsa, eng so'nggi o'tgan slot uchun yana zaxira so'raladi (faqat BITTASI, chunki
har safar faqat "eng so'nggi o'tgan slot" bilan solishtiriladi)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_FREQUENCIES = ("daily", "weekly")


@dataclass(frozen=True)
class Schedule:
    enabled: bool
    frequency: str  # "daily" | "weekly"
    weekday: int  # 0=Dushanba..6=Yakshanba — faqat "weekly" uchun
    time: str  # "HH:MM", tenant mahalliy vaqti
    tz_offset_minutes: int = 0  # mahalliy - UTC, daqiqada

    def __post_init__(self) -> None:
        if self.frequency not in _FREQUENCIES:
            raise ValueError(f"noma'lum frequency: {self.frequency}")


def _to_local(moment: datetime, tz_offset_minutes: int) -> datetime:
    return moment + timedelta(minutes=tz_offset_minutes)


def _to_utc(moment: datetime, tz_offset_minutes: int) -> datetime:
    return moment - timedelta(minutes=tz_offset_minutes)


def _slot_on_day(local_day: datetime, schedule: Schedule) -> datetime:
    hour, minute = (int(part) for part in schedule.time.split(":"))
    return local_day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def last_slot_at_or_before(now: datetime, schedule: Schedule) -> datetime | None:
    """`now` (UTC) paytiga eng yaqin, undan OLDIN yoki TENG kelgan rejalashtirilgan
    vaqt — natija UTC'da qaytariladi, `enabled=False` bo'lsa `None`."""
    if not schedule.enabled:
        return None
    local_now = _to_local(now, schedule.tz_offset_minutes)
    slot = _slot_on_day(local_now, schedule)
    if schedule.frequency == "weekly":
        days_back = (slot.weekday() - schedule.weekday) % 7
        slot -= timedelta(days=days_back)
    if slot > local_now:
        slot -= timedelta(weeks=1) if schedule.frequency == "weekly" else timedelta(days=1)
    return _to_utc(slot, schedule.tz_offset_minutes)


def is_due(now: datetime, schedule: Schedule, last_run_at: datetime | None) -> bool:
    """`last_run_at` — oxirgi rejalashtirilgan (`kind="scheduled"`) zaxira boshlangan
    payti. Hali hech qachon ishlamagan bo'lsa yoki eng so'nggi slotdan OLDIN bo'lsa —
    hozir ishga tushirish kerak (slotning o'zidan keyin — ishga tushganda yoki
    kech qolib bo'lsa ham — bir marta)."""
    slot = last_slot_at_or_before(now, schedule)
    if slot is None:
        return False
    return last_run_at is None or last_run_at < slot
