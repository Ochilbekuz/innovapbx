"""M2c §3 — toll-fraud ichki endpoint'lari — dialplan `CURL()` chaqiradi
(`app/services/compiler.py` `_toll_ext_check_lines`/`_toll_concurrent_lines`).
`internal.py`/`internal_conference.py` BILAN BIR XIL qolip (JWT yo'q, `token`
query parametri, doim 200, tana — oddiy matn).

`tenant=<code>` — bu ikki endpoint FAQAT shu loyihada qo'shilgan parametr
(m2c-contract.md matnida yo'q): `route_id`/`conference_id` kabi endpoint'lar
globaldagi UUID bilan ishlaydi, lekin ichki raqam NOMERI tenant'lar orasida
TAKRORLANISHI mumkin — `token` yagona global bo'lgani uchun tenant'ni
aniqlashtirish kerak. Compiler bu parametrni kompilyatsiya vaqtida ma'lum
`snapshot.tenant_code`dan URL'ga qo'shadi (xavfsizlik darajasi o'zgarmaydi —
token baribir SHART)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import check_internal_api_token
from app.db.models import Extension, SystemSettings, Tenant
from app.services.security_config import parse_toll_fraud
from app.services.toll_fraud import check_outbound, record_concurrent_limit

router = APIRouter(prefix="/internal/toll", tags=["internal"])

_DENY = Response(content="0", media_type="text/plain")
_ALLOW = Response(content="1", media_type="text/plain")


async def _tenant_id(session: AsyncSession, tenant_code: str) -> str | None:
    row = (await session.execute(select(Tenant.id).where(Tenant.code == tenant_code))).first()
    return row[0] if row else None


@router.get("/check")
async def toll_check(
    token: str, tenant: str, ext: str, number: str = "", intl: str = "0",
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200 (tana `"0"`/`"1"`). Token/tenant/ichki raqam topilmasa yoki
    funksiya o'chiq bo'lsa — RUXSAT (xato holatlarida ochiq, blok FAQAT
    haqiqiy limit oshganda) — token noto'g'ri bo'lsagina RAD (fail-closed)."""
    if not check_internal_api_token(token):
        return _DENY
    tenant_id = await _tenant_id(session, tenant)
    if tenant_id is None:
        return _DENY
    row = await session.get(SystemSettings, tenant_id)
    cfg = parse_toll_fraud(row.toll_fraud if row else None)
    if not cfg.enabled:
        return _ALLOW
    extension = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id, Extension.number == ext)
    )).scalar_one_or_none()
    if extension is None:
        return _ALLOW
    allowed = await check_outbound(
        session, tenant_id=tenant_id, extension=extension, number=number, intl=intl == "1", cfg=cfg,
    )
    return _ALLOW if allowed else _DENY


@router.get("/event")
async def toll_event(
    token: str, tenant: str, kind: str, ext: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    """Javobi dialplan tomonidan E'TIBORGA OLINMAYDI (m2c-contract.md §3) —
    shu sabab har doim `"0"` qaytaradi, lekin yozish ishi best-effort amalga
    oshiriladi (xatolar bu yerda yutiladi — CURL chaqiruvchi tomonni to'xtatib
    qo'ymasligi uchun)."""
    if not check_internal_api_token(token):
        return _DENY
    tenant_id = await _tenant_id(session, tenant)
    if tenant_id is None or kind != "concurrent_limit":
        return _DENY
    row = await session.get(SystemSettings, tenant_id)
    cfg = parse_toll_fraud(row.toll_fraud if row else None)
    await record_concurrent_limit(
        session, tenant_id=tenant_id, extension_number=ext or None, max_concurrent=cfg.max_concurrent_outbound,
    )
    return _DENY
