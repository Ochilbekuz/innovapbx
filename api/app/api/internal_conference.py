"""Konferensiya PIN tekshiruvi — dialplan `[<code>-dest-<target_id>]` ichida
`CURL()` chaqiradi (m2a-contract.md §4, `services/compiler.py`:
`_conference_dest_lines`). `internal.py` (M1b chiquvchi marshrut PIN) bilan
AYNAN bir xil qolip (JWT yo'q, `token`, doim 200), lekin javob UCH xil bo'lishi
mumkin — `"admin"`/`"user"`/`"deny"` (qaysi ConfBridge profiliga qo'shish
kerakligini dialplan shu bilan hal qiladi, voicemail/outbound PIN'dagi
oddiy "0"/"1" YETARLI EMAS)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import settings
from app.db.models import Conference
from app.services.conference import pin_role

router = APIRouter(prefix="/internal/conferences", tags=["internal"])

_DENY = Response(content="deny", media_type="text/plain")


@router.get("/{conference_id}/pin-check")
async def conference_pin_check(
    conference_id: str, token: str, pin: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200 (tana — `"admin"`/`"user"`/`"deny"`). Token noto'g'ri bo'lsa
    DB'ga umuman murojaat qilinmaydi (`internal.py` bilan bir xil tezkor rad)."""
    if not settings.internal_api_token or token != settings.internal_api_token:
        return _DENY
    row = (await session.execute(
        select(Conference.pin_hash, Conference.admin_pin_hash).where(Conference.id == conference_id)
    )).first()
    if row is None:
        return _DENY
    role = pin_role(pin, row.pin_hash, row.admin_pin_hash)
    return Response(content=role, media_type="text/plain")
