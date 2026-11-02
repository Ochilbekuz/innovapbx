"""Ovozli pochta PIN tekshiruvi — dialplan `[<code>-vm-main]` `CURL()`
chaqiradi (m1c-contract.md §2). `internal.py` (M1b chiquvchi marshrut PIN)
bilan AYNAN bir xil qolip: JWT yo'q, `token` (`INTERNAL_API_TOKEN`), javob doim
200 + matn `"1"`/`"0"`, token noto'g'ri bo'lsa DB'ga murojaat yo'q."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.internal import _ALLOW, _DENY
from app.core.config import settings
from app.core.security import verify_password
from app.db.models import Tenant, VoicemailBox

router = APIRouter(prefix="/internal/voicemail", tags=["internal"])


@router.get("/pin-check")
async def voicemail_pin_check(
    token: str, context: str = "", mailbox: str = "", pin: str = "",
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not settings.internal_api_token or token != settings.internal_api_token:
        return _DENY
    if not (mailbox.isdigit() and pin.isdigit() and context):
        return _DENY
    pin_hash = (await session.execute(
        select(VoicemailBox.pin_hash).join(Tenant, Tenant.id == VoicemailBox.tenant_id)
        .where(Tenant.code == context, VoicemailBox.mailbox == mailbox)
    )).scalar_one_or_none()
    if pin_hash is None:
        return _DENY
    return _ALLOW if verify_password(pin, pin_hash) else _DENY
