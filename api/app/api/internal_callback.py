"""M10 A1 — qayta chaqirish vidjeti ichki endpoint'i: dialplan `CURL()` chaqiradi
(`app/services/dialplan_callback.py`). `internal_campaigns.py` BILAN BIR XIL qolip
(JWT yo'q, `token` query parametri, doim 200, tana — oddiy matn).
`stage=operator` -> `callback_dialer.record_operator_result`;
`stage=customer` -> `callback_dialer.record_customer_result`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import settings
from app.services import callback_dialer

router = APIRouter(prefix="/internal/callback", tags=["internal"])


def _text(body: str) -> Response:
    return Response(content=body, media_type="text/plain")


def _check_token(token: str) -> bool:
    return bool(settings.internal_api_token) and token == settings.internal_api_token


@router.get("/result")
async def callback_result(token: str, request: str = "", stage: str = "", status: str = "",
                          linkedid: str = "", session: AsyncSession = Depends(get_session)) -> Response:
    """Hangup handler: `1` — yozildi, `0` — token/so'rov noto'g'ri yoki e'tiborsiz qoldirildi
    (masalan operator javob bergan — `stage=operator` holatda holat o'zgarmaydi, lekin baribir `1`)."""
    if not _check_token(token) or not request:
        return _text("0")
    if stage == "operator":
        saved = await callback_dialer.record_operator_result(session, request, status[:20])
    elif stage == "customer":
        saved = await callback_dialer.record_customer_result(session, request, status[:20], linkedid[:64])
    else:
        return _text("0")
    await session.commit()
    return _text("1" if saved else "0")
