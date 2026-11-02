"""`state_now` hisoblash — tenant TZ'da «hozir ochiq/yopiq» (m1a-contract.md).

DIQQAT: bu compiler.py'dagi `GotoIfTime`'dan MUSTAQIL — ikkisi bir xil
qoidani ikki joyda (Asterisk dialplan ichida va Python/API javobida)
takrorlaydi, chunki biri Asterisk vaqtida ishlaydi, ikkinchisi API javobi
uchun darhol kerak (reload kutmasdan)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def compute_state_now(
    *, tz_name: str, override: str, ranges: list[tuple[list[int], str, str]],
    honor_holidays: bool, holidays_mmdd: set[tuple[int, int]],
) -> str:
    if override == "force_open":
        return "open"
    if override == "force_closed":
        return "closed"

    now = datetime.now(ZoneInfo(tz_name))
    if honor_holidays and (now.month, now.day) in holidays_mmdd:
        return "closed"

    weekday = now.isoweekday()  # 1=Dushanba .. 7=Yakshanba (shartnomaga mos)
    hm = now.strftime("%H:%M")
    for weekdays, start, end in ranges:
        if weekday in weekdays and start <= hm < end:
            return "open"
    return "closed"
