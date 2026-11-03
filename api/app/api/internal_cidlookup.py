"""M9 B2 — CID Lookup ichki endpoint'i (dialplan `CURL()` chaqiradi,
`app/services/compiler.py::_cid_lookup_lines`). `internal.py`dagi qolip BILAN
BIR XIL (JWT yo'q, `token` query parametri, javob doim 200/matn).

Javob — ism (CALLERID(name) uchun tayyor, sanitarizatsiya qilingan) yoki BO'SH
SATR (topilmadi/xato/vaqt tugadi — dialplan CALLERID(name)ni o'ZGARTIRMAYDI)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import check_internal_api_token
from app.db.models import CidLookupSource
from app.services.cid_lookup import lookup_name

router = APIRouter(prefix="/internal/cid-lookup", tags=["internal"])

_EMPTY = Response(content="", media_type="text/plain")


@router.get("")
async def cid_lookup(
    token: str, source_id: str, num: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200 qaytaradi (tanasi ism yoki bo'sh satr) — xato/topilmadi
    holatlarida ham bo'sh satr (fail-closed FAQAT token uchun)."""
    if not check_internal_api_token(token):
        return _EMPTY
    if not num:
        return _EMPTY
    source = (await session.execute(
        select(CidLookupSource).where(CidLookupSource.id == source_id)
    )).scalar_one_or_none()
    if source is None:
        return _EMPTY

    name = await lookup_name(session, str(source.tenant_id), source, num)
    return Response(content=name or "", media_type="text/plain")
