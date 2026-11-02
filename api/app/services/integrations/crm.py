"""CRM yetkazuvchilari umumiy qismi (m3b-contract.md §5) — Bitrix24 va amoCRM uchun BIR XIL qoidalar.

Lug'at:
  obuna (subscription) — `integration_subscriptions` qatori, kind `bitrix24|amocrm`, tenant'da bittadan;
                         ochiq sozlamalar `config`, sirlar `secret_enc` (JSON, faqat bazada).
  xarita (user map)    — ichki raqam → CRM foydalanuvchi ID (`crm_user_map`); topilmasa `default_user_id`.
  bog'lanish (link)    — qo'ng'iroq `linkedid` ↔ CRM kartasi ID (`crm_call_links`, Bitrix `CALL_ID`).
  tashqi qo'ng'iroq    — `direction` inbound|outbound; ichki (internal) CRM'ga HECH QACHON yuborilmaydi.

HTTP xato tasnifi (VoxBridge ADR-003 saboqlari): 2xx — ok; 429 — rate-limit (urinish sanalmaydi);
401/403 — autentifikatsiya (vaqtinchalik: admin tokenni tuzatgach navbat davom etadi); 5xx/tarmoq —
vaqtinchalik; qolgan 4xx — doimiy. Xato matnida URL/sir BO'LMAYDI (httpx xatosi URL'ni o'z ichiga oladi).
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrmCallLink, CrmUserMap
from app.services.integrations.providers import DeliveryResult

CrmProvider = Literal["bitrix24", "amocrm"]
PROVIDERS: tuple[CrmProvider, ...] = ("bitrix24", "amocrm")
EXTERNAL_DIRECTIONS = frozenset({"inbound", "outbound"})
DEFAULT_RETRY_AFTER_S = 2.0
ERROR_LIMIT = 300
LINK_RETENTION_DAYS = 30  # Bitrix finish/amo note qo'ng'iroqdan keyin daqiqalarda keladi — 30 kun yetarli


class CrmCallError(Exception):
    """CRM so'rovi muvaffaqiyatsiz — `result` dispetcherga shu holicha qaytadi."""

    def __init__(self, result: DeliveryResult) -> None:
        super().__init__(result.error)
        self.result = result


def failure(error: str, *, status: int | None = None, permanent: bool = False,
            retry_after_s: float | None = None) -> CrmCallError:
    return CrmCallError(DeliveryResult(ok=False, status_code=status, error=error[:ERROR_LIMIT],
                                       permanent=permanent, retry_after_s=retry_after_s))


# ------------------------------------------------------------ sirlar
def load_secrets(raw: str | None) -> dict[str, str]:
    """`secret_enc` ochilgan matni (JSON obyekt) → {nom: qiymat}; buzuq/bo'sh → {}."""
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items() if isinstance(v, str) and v}


def dump_secrets(values: Mapping[str, str]) -> str:
    return json.dumps({k: v for k, v in sorted(values.items()) if v}, separators=(",", ":"))


# ------------------------------------------------------------ rate limit
class RateLimiter:
    """Kalit (obuna) bo'yicha so'rovlar orasida kamida `1/rps` s. Slot `await` dan OLDIN band qilinadi —
    bir vaqtdagi chaqiruvlar (dispetcher + `/test`) ham navbatga turadi."""

    def __init__(self, rps: float, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Any] = asyncio.sleep) -> None:
        self._interval = 1.0 / rps
        self._clock, self._sleep = clock, sleep
        self._next: dict[str, float] = {}

    async def wait(self, key: str) -> None:
        now = self._clock()
        slot = max(now, self._next.get(key, now))
        self._next[key] = slot + self._interval
        if slot > now:
            await self._sleep(slot - now)


# ------------------------------------------------------------ HTTP
def retry_after(headers: Mapping[str, str], default: float = DEFAULT_RETRY_AFTER_S) -> float:
    try:
        return max(1.0, float(headers.get("retry-after", "")))
    except ValueError:
        return default


def http_failure(status: int, headers: Mapping[str, str], *, what: str) -> CrmCallError | None:
    """HTTP holati bo'yicha umumiy qaror; 2xx → `None` (muvaffaqiyat — tanani chaqiruvchi tekshiradi)."""
    if 200 <= status < 300:
        return None
    if status == 429:
        return failure(f"{what}: so'rovlar chegarasi (HTTP 429)", status=status, retry_after_s=retry_after(headers))
    if status in (401, 403):
        return failure(f"{what}: autentifikatsiya rad etildi (HTTP {status}) — token/webhook'ni tekshiring",
                       status=status)
    if status >= 500:
        return failure(f"{what}: server xatosi (HTTP {status})", status=status)
    return failure(f"{what}: so'rov rad etildi (HTTP {status})", status=status, permanent=True)


@dataclass(frozen=True)
class HttpTarget:
    """Bitta obuna uchun HTTP yo'nalishi: rate-limit kaliti va (testda) soxta transport."""
    limiter: RateLimiter
    key: str
    transport: httpx.AsyncBaseTransport | None = None


async def http_request(target: HttpTarget, method: str, url: str, *, what: str, **kwargs: Any) -> httpx.Response:
    """Redirect kuzatilmaydi; tarmoq xatosi — vaqtinchalik, matnda URL YO'Q (sir oqmasin)."""
    await target.limiter.wait(target.key)
    try:
        async with httpx.AsyncClient(timeout=settings.integration_http_timeout_s, follow_redirects=False,
                                     transport=target.transport) as client:
            return await client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise failure(f"{what}: tarmoq xatosi ({type(exc).__name__})") from exc


def json_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


# ------------------------------------------------------------ qo'ng'iroq maydonlari (§2 payload)
def is_external(call: Mapping[str, Any]) -> bool:
    return call.get("direction") in EXTERNAL_DIRECTIONS


def external_number(call: Mapping[str, Any]) -> str:
    """Mijoz raqami: kiruvchida `from`, chiquvchida `to`."""
    return str((call.get("from") if call.get("direction") == "inbound" else call.get("to")) or "")


def first_recording_url(call: Mapping[str, Any]) -> str | None:
    return next((r.get("url") for r in call.get("recordings") or [] if r.get("url")), None)


def parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------ xarita va bog'lanish
@dataclass(frozen=True)
class UserMap:
    by_extension: Mapping[str, str]
    default_user_id: str | None = None

    def user_for(self, *extensions: str | None) -> str | None:
        """Birinchi xaritadagi raqamning foydalanuvchisi; hech biri yo'q → `default_user_id`."""
        found = (self.by_extension.get(e) for e in extensions if e)
        return next((u for u in found if u), self.default_user_id)


async def load_user_map(session: AsyncSession, tenant_id: str, provider: str,
                        default_user_id: str | None) -> UserMap:
    rows = (await session.execute(select(CrmUserMap.extension, CrmUserMap.crm_user_id).where(
        CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == provider))).all()
    return UserMap({ext: uid for ext, uid in rows}, default_user_id or None)


async def purge_old_links(session: AsyncSession, now: datetime) -> int:
    """Eski bog'lanishlar (`crm_call_links`) — jadval cheksiz o'smasin; commit chaqiruvchida."""
    cutoff = now - timedelta(days=LINK_RETENTION_DAYS)
    result = await session.execute(delete(CrmCallLink).where(CrmCallLink.created_at < cutoff))
    return result.rowcount or 0


async def get_link(session: AsyncSession, tenant_id: str, provider: str, linkedid: str) -> CrmCallLink | None:
    return await session.get(CrmCallLink, (tenant_id, provider, linkedid))


@dataclass(frozen=True)
class CrmUserInfo:
    """`/test` yuklagan foydalanuvchi: Bitrix `UF_PHONE_INNER` — avto-xarita uchun."""
    id: str
    name: str
    inner_phone: str | None = None
