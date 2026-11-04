"""M12 A2 — DISA ichki PIN tekshiruv endpoint'i (dialplan `CURL()` chaqiradi,
`app/services/compiler.py::_disa_dest_lines`). `internal_pinset.py` BILAN BIR
XIL qolip (JWT yo'q, `token` query parametri, javob doim HTTP 200/oddiy matn).

Javob protokoli: `"1"` (mos keldi yoki PIN talab qilinmaydi) yoki `"0"` (mos
kelmadi/token xato/qator topilmadi/o'chirilgan) — fail-CLOSED (toll-fraud
xavfi tufayli `internal_day_night.py::day_night_state`dan FARQLI, bu yerda
noma'lum holatda HAR DOIM rad etiladi)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import settings
from app.core.security import check_internal_api_token
from app.db.models import Disa, SecurityEvent
from app.services.pin_hmac import pin_matches

router = APIRouter(prefix="/internal/disa", tags=["internal"])

_ALLOW = Response(content="1", media_type="text/plain")
_DENY = Response(content="0", media_type="text/plain")


@router.get("/{row_id}/pin-check")
async def disa_pin_check(
    row_id: str, token: str, pin: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    if not check_internal_api_token(token):
        return _DENY
    row = await session.get(Disa, row_id)
    if row is None or not row.enabled:
        return _DENY
    if row.pin_hmac is None:
        return _ALLOW if row.allow_no_pin else _DENY
    secret = settings.require_secret_key()
    if pin_matches(secret, pin, row.pin_hmac):
        return _ALLOW
    session.add(SecurityEvent(tenant_id=row.tenant_id, kind="disa_pin_fail", details={"disa_id": row_id}))
    await session.commit()
    return _DENY
