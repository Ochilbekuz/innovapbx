"""Bitrix24 OAuth broker mijozi (`bitrix-oauth-shartnoma.md` §1) — markaziy `lic.uzmik.uz`
("litsenziya" ilovasi). `client_secret` FAQAT brokerda — bu modul HECH QACHON uni ko'rmaydi.

Bu yerda FAQAT broker bilan JSON HTTP gaplashuv: `boshla` (ulash boshlanishi),
`natija` (so'rovni so'rash), `token` (kirish tokeni, keshlangan), `litsenziya`,
`uzish` (uzish). Xatolar: HTTP kod + `{"xato","xabar"}` — `BrokerError` orqali
ko'tariladi; `to_crm_failure()` CRM yetkazuvchisi tushunadigan `CrmCallError`ga aylantiradi.

Token keshi: jarayon ichida, `ulanish_id` bo'yicha, `expires_at - 120s` gacha;
yangilash paytida ikki parallel so'rov bir xil `refresh_token`ni ALMASHTIRMASIN
uchun `ulanish_id` bo'yicha qulf (asyncio.Lock)."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.services.integrations import crm

_TOKEN_SAFETY_MARGIN_S = 120
Clock = Callable[[], datetime]


class BrokerError(Exception):
    """Broker `{"xato","xabar"}` konverti; `status` — HTTP holati (None — tarmoq xatosi)."""

    def __init__(self, code: str, message: str, *, status: int | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status


def to_crm_failure(error: BrokerError) -> crm.CrmCallError:
    """Broker xatosi → CRM yetkazuvchisi tiliga: tarmoq → vaqtinchalik, 402 → litsenziya
    (doimiy — qayta urinish foydasiz, admin to'lov/sinovni yangilashi kerak), qolgani → doimiy."""
    if error.status is None:
        return crm.failure(f"broker_unreachable: {error.message}", retry_after_s=crm.DEFAULT_RETRY_AFTER_S)
    if error.status == 402:
        return crm.failure("license_expired", permanent=True)
    return crm.failure(f"broker:{error.code}", permanent=True)


async def _post(path: str, payload: Mapping[str, Any], *,
                transport: httpx.AsyncBaseTransport | None = None) -> tuple[int, dict[str, Any]]:
    url = settings.bitrix_broker_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=settings.integration_http_timeout_s,
                                     transport=transport) as client:
            resp = await client.post(url, json=dict(payload))
    except httpx.HTTPError as exc:
        raise BrokerError("broker_unreachable", f"Broker bilan bog'lanib bo'lmadi ({type(exc).__name__})") from exc
    try:
        body = resp.json()
    except ValueError as exc:
        raise BrokerError("broker_unreachable", "Broker noto'g'ri javob qaytardi",
                          status=resp.status_code) from exc
    if not isinstance(body, dict):
        raise BrokerError("broker_unreachable", "Broker noto'g'ri javob qaytardi", status=resp.status_code)
    return resp.status_code, body


def _require_innova_id() -> str:
    if not settings.innova_id:
        raise BrokerError("broker_misconfigured", "INNOVA_ID muhit o'zgaruvchisi berilmagan")
    return settings.innova_id


# ------------------------------------------------------------ boshla / natija
@dataclass(frozen=True)
class StartResult:
    sessiya: str
    authorize_url: str


async def boshla(domain: str, *, transport: httpx.AsyncBaseTransport | None = None) -> StartResult:
    status, body = await _post("/api/v1/bitrix/boshla", {"domain": domain, "innova_id": _require_innova_id()},
                               transport=transport)
    if status != 200:
        raise BrokerError(str(body.get("xato") or "xato"), str(body.get("xabar") or "Xato"), status=status)
    return StartResult(sessiya=str(body.get("sessiya") or ""), authorize_url=str(body.get("authorize_url") or ""))


@dataclass(frozen=True)
class NatijaResult:
    """`holat`: `kutilmoqda|xato|tayyor|olingan`; `tayyor`dagina ulanish sirlari to'ldiriladi."""
    holat: str
    xato: str | None = None
    xabar: str | None = None
    ulanish_id: str | None = None
    ulanish_sir: str | None = None
    member_id: str | None = None
    domain: str | None = None
    application_token: str | None = None


def _parse_natija(status: int, body: Mapping[str, Any]) -> NatijaResult:
    if status == 404:
        return NatijaResult(holat="xato", xato="sessiya_yoq", xabar=str(body.get("xabar") or "Sessiya topilmadi"))
    holat = str(body.get("holat") or "xato")
    if holat == "xato":
        return NatijaResult(holat="xato", xato=str(body.get("xato") or ""), xabar=str(body.get("xabar") or ""))
    if holat == "tayyor":
        return NatijaResult(holat="tayyor", ulanish_id=str(body.get("ulanish_id") or ""),
                            ulanish_sir=str(body.get("ulanish_sir") or ""), member_id=str(body.get("member_id") or ""),
                            domain=str(body.get("domain") or ""), application_token=body.get("application_token"))
    return NatijaResult(holat=holat)  # kutilmoqda | olingan


async def natija(sessiya: str, *, transport: httpx.AsyncBaseTransport | None = None) -> NatijaResult:
    status, body = await _post("/api/v1/bitrix/natija", {"sessiya": sessiya}, transport=transport)
    return _parse_natija(status, body)


# ------------------------------------------------------------ token (kesh + qulf)
@dataclass(frozen=True)
class BrokerToken:
    access_token: str
    client_endpoint: str
    expires_at: datetime
    member_id: str
    domain: str
    application_token: str | None
    license: dict[str, Any]


def _parse_expires_at(raw: str) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _parse_token(body: Mapping[str, Any]) -> BrokerToken:
    return BrokerToken(access_token=str(body.get("access_token") or ""),
                       client_endpoint=str(body.get("client_endpoint") or ""),
                       expires_at=_parse_expires_at(str(body.get("expires_at") or "")),
                       member_id=str(body.get("member_id") or ""), domain=str(body.get("domain") or ""),
                       application_token=body.get("application_token"),
                       license=body.get("litsenziya") if isinstance(body.get("litsenziya"), dict) else {})


def _is_fresh(token: BrokerToken, now: datetime) -> bool:
    return (token.expires_at - now).total_seconds() > _TOKEN_SAFETY_MARGIN_S


class _TokenCache:
    """Jarayon ichida — modul darajasida BITTA nusxa (`_cache`), testlar
    `reset()` bilan izolyatsiya qiladi (pytest ishlar orasida sizmasin)."""

    def __init__(self) -> None:
        self._tokens: dict[str, BrokerToken] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def reset(self) -> None:
        self._tokens.clear()
        self._locks.clear()

    def get(self, ulanish_id: str) -> BrokerToken | None:
        return self._tokens.get(ulanish_id)

    def put(self, ulanish_id: str, token: BrokerToken) -> None:
        self._tokens[ulanish_id] = token

    def lock(self, ulanish_id: str) -> asyncio.Lock:
        found = self._locks.get(ulanish_id)
        if found is None:
            found = asyncio.Lock()
            self._locks[ulanish_id] = found
        return found


_cache = _TokenCache()


async def get_token(ulanish_id: str, ulanish_sir: str, *, transport: httpx.AsyncBaseTransport | None = None,
                    force: bool = False, clock: Clock = lambda: datetime.now(timezone.utc)) -> BrokerToken:
    """Kesh (`expires_at - 120s` gacha) + `ulanish_id` bo'yicha qulf (refresh_token
    HAR yangilashda almashadi — ikki parallel so'rov bir-birini sindirmasin)."""
    cached = _cache.get(ulanish_id)
    if not force and cached is not None and _is_fresh(cached, clock()):
        return cached
    async with _cache.lock(ulanish_id):
        cached = _cache.get(ulanish_id)
        if not force and cached is not None and _is_fresh(cached, clock()):
            return cached
        status, body = await _post("/api/v1/bitrix/token", {"ulanish_id": ulanish_id, "ulanish_sir": ulanish_sir},
                                   transport=transport)
        if status != 200:
            raise BrokerError(str(body.get("xato") or "xato"), str(body.get("xabar") or "Token xatosi"),
                              status=status)
        token = _parse_token(body)
        _cache.put(ulanish_id, token)
        return token


def reset_token_cache() -> None:
    """Faqat testlar uchun — modullar orasida keshi sizmasin."""
    _cache.reset()


# ------------------------------------------------------------ litsenziya / uzish
async def litsenziya(ulanish_id: str, ulanish_sir: str, *,
                     transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    status, body = await _post("/api/v1/bitrix/litsenziya", {"ulanish_id": ulanish_id, "ulanish_sir": ulanish_sir},
                               transport=transport)
    if status != 200:
        raise BrokerError(str(body.get("xato") or "xato"), str(body.get("xabar") or "Litsenziya xatosi"),
                          status=status)
    return body


async def uzish(ulanish_id: str, ulanish_sir: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bool:
    """Best-effort: broker ERISHIB bo'lmasa HAM `disconnect()` davom etadi — shu
    sabab xato ko'tarilmaydi, faqat muvaffaqiyat/muvaffaqiyatsizlik qaytadi."""
    try:
        status, body = await _post("/api/v1/bitrix/uzish", {"ulanish_id": ulanish_id, "ulanish_sir": ulanish_sir},
                                   transport=transport)
    except BrokerError:
        return False
    return status == 200 and bool(body.get("ok"))
