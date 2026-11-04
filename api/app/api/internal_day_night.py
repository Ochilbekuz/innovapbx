"""M12 A1 — Kun/Tun rejimi ichki endpoint'lari (dialplan `CURL()` chaqiradi,
`app/services/compiler.py::_day_night_dest_lines`/`_day_night_toggle_lines`).
`internal_toll.py`/`internal_pinset.py` BILAN BIR XIL qolip (JWT yo'q, `token`
query parametri, javob doim HTTP 200/oddiy matn).

Holat (`mode`) astdb'da EMAS — PG (`day_night.mode`) yagona manba. `/state` —
FAQAT o'qiydi (CURL har qo'ng'iroqda, reload shart emas). `/toggle` — PIN
mos kelsa (yoki umuman yo'q bo'lsa) holatni ALMASHTIRADI va YANGI holatni
qaytaradi ("GET bilan yozish" — `internal_toll.py::toll_event` BILAN BIR XIL
qabul qilingan qolip, chunki Asterisk CURL() faqat GET qila oladi).

Javob protokoli:
- `/state`: `"day"` yoki `"night"` (topilmasa/o'chiq bo'lsa fail-safe `"day"`).
- `/toggle`: yangi holat (`"day"`/`"night"`) yoki `"0"` (token/PIN xato)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import settings
from app.core.security import check_internal_api_token
from app.db.models import DayNight, SecurityEvent
from app.services.pin_hmac import pin_matches

router = APIRouter(prefix="/internal/day-night", tags=["internal"])

_DAY = Response(content="day", media_type="text/plain")
_NIGHT = Response(content="night", media_type="text/plain")
_DENY = Response(content="0", media_type="text/plain")


def _mode_response(mode: str) -> Response:
    return _NIGHT if mode == "night" else _DAY


@router.get("/{row_id}/state")
async def day_night_state(row_id: str, token: str, session: AsyncSession = Depends(get_session)) -> Response:
    """Fail-safe: token xato/qator topilmadi bo'lsa ham — qo'ng'iroqni
    to'xtatib qo'ymaslik uchun kun rejimi qaytariladi (oddiy marshrut, PIN
    bilan himoyalanmaydi — `/toggle`dan FARQLI, bu yerda fail-closed shart
    emas)."""
    if not check_internal_api_token(token):
        return _DAY
    row = await session.get(DayNight, row_id)
    if row is None:
        return _DAY
    return _mode_response(row.mode)


@router.get("/{row_id}/toggle")
async def day_night_toggle(
    row_id: str, token: str, pin: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    """PIN qo'yilgan bo'lsa mos kelishi SHART (mos kelmasa `SecurityEvent`
    yoziladi — `internal_pinset.py::_deny_with_event` BILAN BIR XIL qolip)."""
    if not check_internal_api_token(token):
        return _DENY
    row = await session.get(DayNight, row_id)
    if row is None:
        return _DENY
    if row.pin_hmac is not None:
        secret = settings.require_secret_key()
        if not pin_matches(secret, pin, row.pin_hmac):
            session.add(SecurityEvent(
                tenant_id=row.tenant_id, kind="day_night_pin_fail", details={"day_night_id": row_id},
            ))
            await session.commit()
            return _DENY
    row.mode = "night" if row.mode == "day" else "day"
    await session.commit()
    return _mode_response(row.mode)
