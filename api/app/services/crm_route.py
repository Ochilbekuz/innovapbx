"""M-CRM §3 — InformUnity «qo'ng'iroq qiluvchilar uchun CRM manzili»: raqamdan
mas'ul menejer/ism topish.

Oqim: `telephony.externalCall.searchCrmEntities` (CONTACT > COMPANY > LEAD,
tartib KAFOLATLANMAGAN — shu sabab o'zimiz saralaymiz) -> `ASSIGNED_BY_ID` ->
teskari `crm_user_map` (faqat YOQILGAN ichki raqam) -> kengaytma.

FAIL-OPEN: har qanday xato/vaqt tugashi (`TIMEOUT_S`) -> BO'SH natija — qo'ng'iroq
oddiy `Goto(dest)` yo'li bilan davom etadi (dialplan hech narsa SINMAYDI).
Kesh (`TTLCache`, 60s) — `cid_lookup.py` bilan BIR XIL qolip (dryer), lekin
alohida nusxa (CRM so'rovlari o'z maydonida). Tezlik cheklovi — BITRIX24
dispetcher navbatini (`bitrix24.LIMITER`) BLOKLAMASIN uchun MUSTAQIL kalit/limiter.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrmUserMap, Extension, IntegrationSubscription
from app.services.cid_lookup import TTLCache, sanitize_name
from app.services.integrations import crm
from app.services.integrations.bitrix24 import BitrixClient
from app.services.integrations.crm import CrmCallError, HttpTarget

TIMEOUT_S = 2.0
CACHE_TTL_S = 60
LIMITER = crm.RateLimiter(2.0)  # bitrix24.LIMITER bilan ULASHILMAYDI — navbatni bloklamasin.

cache = TTLCache(max_items=5000)

_ENTITY_PRIORITY = {"CONTACT": 0, "COMPANY": 1, "LEAD": 2}


@dataclass(frozen=True)
class RouteResult:
    extension: str | None = None
    name: str | None = None


def format_result(result: RouteResult) -> str:
    """`"<ext>|<ism>"` — ichki endpoint (`internal_crmroute.py`) javobi BILAN BIR XIL format."""
    return f"{result.extension or ''}|{result.name or ''}"


def _decode(raw: str) -> RouteResult:
    ext, _, name = raw.partition("|")
    return RouteResult(ext or None, name or None)


def pick_entity(rows: list[Any]) -> dict[str, Any] | None:
    """`searchCrmEntities` tartibi KAFOLATLANMAGAN — ustunlik CONTACT > COMPANY > LEAD."""
    candidates = [r for r in rows if isinstance(r, dict) and r.get("CRM_ENTITY_TYPE")]
    if not candidates:
        return None
    return min(candidates, key=lambda r: _ENTITY_PRIORITY.get(str(r.get("CRM_ENTITY_TYPE")).upper(), 99))


async def search_entity(client: BitrixClient, number: str) -> dict[str, Any] | None:
    result = await client.call("telephony.externalCall.searchCrmEntities", {"PHONE_NUMBER": number})
    return pick_entity(result if isinstance(result, list) else [])


async def extension_for_user(session: AsyncSession, tenant_id: str, provider: str, crm_user_id: str) -> str | None:
    """Teskari xarita: CRM foydalanuvchisi -> YOQILGAN ichki raqam (o'chirilgan ext -> yo'naltirilmaydi)."""
    return (await session.execute(
        select(CrmUserMap.extension).join(
            Extension, (Extension.tenant_id == CrmUserMap.tenant_id) & (Extension.number == CrmUserMap.extension))
        .where(CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == provider,
               CrmUserMap.crm_user_id == crm_user_id, Extension.enabled.is_(True))
    )).scalar_one_or_none()


async def enabled_subscription(session: AsyncSession, tenant_id: str) -> IntegrationSubscription | None:
    return (await session.execute(select(IntegrationSubscription).where(
        IntegrationSubscription.tenant_id == tenant_id, IntegrationSubscription.kind == "bitrix24",
        IntegrationSubscription.enabled.is_(True)))).scalar_one_or_none()


async def _lookup(session: AsyncSession, sub: IntegrationSubscription, webhook_url: str, number: str,
                  *, transport: Any = None) -> RouteResult:
    client = BitrixClient(webhook_url, HttpTarget(LIMITER, f"crmroute:{sub.id}", transport))
    entity = await search_entity(client, number)
    if entity is None:
        return RouteResult()
    name = sanitize_name(str(entity.get("NAME") or "")).replace("|", "") or None
    assigned = str(entity.get("ASSIGNED_BY_ID") or "") or None
    ext = await extension_for_user(session, str(sub.tenant_id), sub.kind, assigned) if assigned else None
    return RouteResult(ext, name)


async def route_for_number(session: AsyncSession, sub: IntegrationSubscription, webhook_url: str, number: str,
                           *, transport: Any = None, clock: Any = time.monotonic) -> RouteResult:
    """TTLCache (60s) + umumiy `TIMEOUT_S` muddat + FAIL-OPEN (xato -> bo'sh natija)."""
    key = (str(sub.id), number)
    hit, cached = cache.get(key)
    if hit and cached is not None:
        return _decode(cached)
    try:
        result = await asyncio.wait_for(_lookup(session, sub, webhook_url, number, transport=transport), TIMEOUT_S)
    except (CrmCallError, TimeoutError, asyncio.TimeoutError, Exception):  # noqa: BLE001 — fail-open shart
        result = RouteResult()
    cache.set(key, format_result(result), CACHE_TTL_S)
    return result
