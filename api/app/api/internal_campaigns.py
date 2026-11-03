"""M6 §3 — kampaniya ichki endpoint'lari: dialplan `CURL()` chaqiradi (`app/services/dialplan_campaign.py`).
`internal_toll.py` BILAN BIR XIL qolip (JWT yo'q, `token` query parametri, doim 200, tana — oddiy matn).
`attempt` — global bigserial id, token yagona global; tenant aniqlashtirish shart emas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import check_internal_api_token
from app.services.campaign_dialer import record_key, record_result

router = APIRouter(prefix="/internal/campaigns", tags=["internal"])


def _text(body: str) -> Response:
    return Response(content=body, media_type="text/plain")


def _attempt_id(token: str, attempt: str) -> int | None:
    if not check_internal_api_token(token) or not attempt.isdigit():
        return None
    return int(attempt)


@router.get("/result")
async def campaign_result(token: str, attempt: str = "", status: str = "", answered: str = "",
                          session: AsyncSession = Depends(get_session)) -> Response:
    """Hangup handler: `1` — yozildi, `0` — token/attempt noto'g'ri yoki allaqachon yopilgan."""
    attempt_id = _attempt_id(token, attempt)
    if attempt_id is None:
        return _text("0")
    saved = await record_result(session, attempt_id, status[:20], answered[:12])
    await session.commit()
    return _text("1" if saved else "0")


@router.get("/key")
async def campaign_key(token: str, attempt: str = "", key: str = "",
                       session: AsyncSession = Depends(get_session)) -> Response:
    """Mijoz tugmasi → `connect` | `optout` | `none`."""
    attempt_id = _attempt_id(token, attempt)
    if attempt_id is None:
        return _text("none")
    action = await record_key(session, attempt_id, key)
    await session.commit()
    return _text(action)
