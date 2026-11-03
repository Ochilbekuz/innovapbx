"""M9 B1 — PIN to'plami ichki tekshiruv endpoint'i (dialplan `CURL()` chaqiradi,
`app/services/compiler.py::_route_pin_set_lines`). `internal.py`dagi yagona PIN
(`pin-check`) BILAN BIR XIL qolip (JWT yo'q, `token` query parametri, javob
doim 200/matn) — farqi: HMAC ro'yxat solishtiruvi va javobda ixtiyoriy
`label` (`CDR(accountcode)` uchun).

Javob protokoli: `"0"` (mos kelmadi) yoki `"1:<label>"` (mos keldi; `label`
bo'sh satr bo'lishi mumkin — `record_in_cdr=false` bo'lsa).

Qo'pol kuch himoyasi: `rate_limit.py::SlidingWindowLimiter`, kalit —
`route_id:caller` (bitta chaqiruvchi bir marshrutga ketma-ket urinishi
cheklanadi; boshqa chaqiruvchilar/marshrutlar bir-biriga ta'sir qilmaydi).
Chegaradan oshgan va noto'g'ri PIN urinishlari `security_events`ga yoziladi."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session
from app.core.config import settings
from app.core.security import check_internal_api_token
from app.db.models import OutboundRoute, PinSet, SecurityEvent
from app.services.pin_hmac import pin_matches
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/internal/outbound-routes", tags=["internal"])

_DENY = Response(content="0", media_type="text/plain")

_ATTEMPT_LIMIT = 5
_ATTEMPT_WINDOW_S = 60.0
_limiter = SlidingWindowLimiter()


def _match_response(label: str | None) -> Response:
    return Response(content=f"1:{label or ''}", media_type="text/plain")


def _find_matched_label(pin_set: PinSet, pin: str, secret: str) -> str | None:
    for item in pin_set.pins:
        if pin_matches(secret, pin, item.pin_hmac):
            return item.label
    return None


async def _deny_with_event(session: AsyncSession, *, tenant_id: str, kind: str, details: dict) -> Response:
    """Rad javobidan oldin `SecurityEvent` yozib commit qiladi (dryer —
    ikkita bir xil blok shu funksiyaga birlashtirilgan)."""
    session.add(SecurityEvent(tenant_id=tenant_id, kind=kind, details=details))
    await session.commit()
    return _DENY


@router.get("/{route_id}/pin-set-check")
async def pin_set_check(
    route_id: str, token: str, pin: str, caller: str = "unknown",
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200 qaytaradi — xato/topilmadi/limit holatlarida ham RAD ("0"),
    Asterisk `CURL()` HTTP status kodini emas, tana matnini o'qiydi."""
    if not check_internal_api_token(token):
        return _DENY
    route = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.id == route_id)
    )).scalar_one_or_none()
    if route is None or route.pin_set_id is None:
        return _DENY

    limiter_key = f"{route_id}:{caller}"
    if not _limiter.allow(limiter_key, limit=_ATTEMPT_LIMIT, window_s=_ATTEMPT_WINDOW_S):
        return await _deny_with_event(
            session, tenant_id=route.tenant_id, kind="pinset_rate_limited",
            details={"route_id": route_id, "caller": caller},
        )

    pin_set = (await session.execute(
        select(PinSet).where(PinSet.id == route.pin_set_id).options(selectinload(PinSet.pins))
    )).scalar_one_or_none()
    if pin_set is None:
        return _DENY

    secret = settings.require_secret_key()
    matched_label = _find_matched_label(pin_set, pin, secret)
    if matched_label is None:
        return await _deny_with_event(
            session, tenant_id=route.tenant_id, kind="pinset_fail",
            details={"route_id": route_id, "caller": caller, "pin_set_id": str(pin_set.id)},
        )

    return _match_response(matched_label if pin_set.record_in_cdr else None)
