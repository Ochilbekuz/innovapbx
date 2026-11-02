"""amoCRM / Kommo yetkazuvchisi (m3b-contract.md §5) — `base_url` `https://<sub>.amocrm.ru`, uzoq muddatli token.

Faqat `call.ended` (tashqi): `POST /api/v4/calls` — direction, uniq=linkedid, duration=billsec, source, link
(birinchi yozuv havolasi), phone, call_result, call_status (4 suhbat bo'ldi / 6 javob yo'q / 7 band),
responsible_user_id (xarita → default), created_at. Kontakt topilmasa (javobda `_embedded.errors`, `calls` bo'sh
yoki 400/404) va `unsorted_for_unknown` → `POST /api/v4/leads/unsorted/sip` (`source_uid` = linkedid).
401 → status `error` (vaqtinchalik — token tuzatilgach navbat davom etadi); 429/5xx → qayta urinish.
Rate limit: 6 so'rov/s obunaga. Foydalanuvchilar `GET /api/v4/users` (xarita faqat qo'lda).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.services.integrations import crm, ssrf
from app.services.integrations.crm import CrmCallError, CrmUserInfo, HttpTarget
from app.services.integrations.providers import DeliveryContext, DeliveryResult, register_provider

KIND = "amocrm"
RPS = 6.0
SOURCE = "Innova PBX"
SERVICE_CODE = "innova_pbx"
USER_PAGES_MAX = 20
CALL_STATUS = {"answered": 4, "missed": 6, "busy": 7}
CALL_RESULT = {4: "Suhbat bo'ldi", 6: "Javob yo'q", 7: "Band"}
LIMITER = crm.RateLimiter(RPS)


# ------------------------------------------------------------ sof qoidalar
class InvalidBaseUrl(ValueError):
    pass


def normalize_base_url(raw: str) -> str:
    """`http(s)://host[:port]` (yo'l, so'rov, login yo'q); oxirgi `/` olib tashlanadi."""
    url = raw.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.path or parts.query \
            or parts.fragment or parts.username or parts.password:
        raise InvalidBaseUrl(raw)
    return url


def call_status(status: str | None) -> int:
    return CALL_STATUS.get(status or "", 6)


def _unix(raw: str | None) -> int:
    value = crm.parse_time(raw)
    return int(value.timestamp()) if value else int(datetime.now(timezone.utc).timestamp())


def call_body(call: Mapping[str, Any], *, responsible_user_id: str | None) -> dict[str, Any]:
    status = call_status(call.get("status"))
    body: dict[str, Any] = {
        "direction": "inbound" if call.get("direction") == "inbound" else "outbound",
        "uniq": str(call.get("id") or ""), "duration": int(call.get("billsec") or 0), "source": SOURCE,
        "phone": crm.external_number(call), "call_result": CALL_RESULT[status], "call_status": status,
        "created_at": _unix(call.get("started_at")),
    }
    link = crm.first_recording_url(call)
    if link:
        body["link"] = link
    if responsible_user_id:
        body["responsible_user_id"] = int(responsible_user_id)
    return body


def unsorted_body(call: Mapping[str, Any]) -> dict[str, Any]:
    phone = crm.external_number(call)
    linkedid = str(call.get("id") or "")
    metadata: dict[str, Any] = {
        "is_call_event_needed": True, "uniq": linkedid, "duration": int(call.get("billsec") or 0),
        "service_code": SERVICE_CODE, "from": phone, "phone": phone, "called_at": _unix(call.get("started_at")),
    }
    link = crm.first_recording_url(call)
    if link:
        metadata["link"] = link
    return {"source_uid": linkedid, "source_name": SOURCE, "created_at": metadata["called_at"],
            "metadata": metadata, "_embedded": {"contacts": [{"name": phone}]}}


def contact_missing(status: int, body: Any) -> bool:
    """Kontakt topilmadi: 404, yoki 2xx/400 + `_embedded.errors` bor va `_embedded.calls` bo'sh."""
    if status == 404:
        return True
    embedded = body.get("_embedded") if isinstance(body, dict) else None
    if status not in (200, 400) or not isinstance(embedded, dict):
        return False
    return bool(embedded.get("errors")) and not embedded.get("calls")


def user_info(raw: Mapping[str, Any]) -> CrmUserInfo:
    return CrmUserInfo(id=str(raw.get("id")), name=str(raw.get("name") or raw.get("email") or raw.get("id")))


# ------------------------------------------------------------ REST mijoz
class AmoClient:
    def __init__(self, base_url: str, token: str, target: HttpTarget) -> None:
        self._base, self._target = base_url.rstrip("/"), target
        self._headers = {"Authorization": f"Bearer {token}", "User-Agent": "InnovaPBX-CRM/1"}

    async def request(self, method: str, path: str, *, what: str, **kwargs: Any) -> tuple[int, Any]:
        """Transport/429/401/5xx → `CrmCallError`; qolgan javob (2xx/4xx) chaqiruvchiga — u tanani biladi."""
        resp = await crm.http_request(self._target, method, f"{self._base}{path}", what=what,
                                      headers=self._headers, **kwargs)
        error = crm.http_failure(resp.status_code, resp.headers, what=what)
        if error is not None and not error.result.permanent:
            raise error
        return resp.status_code, crm.json_body(resp)

    async def users(self) -> list[CrmUserInfo]:
        found: list[CrmUserInfo] = []
        for page in range(1, USER_PAGES_MAX + 1):
            status, body = await self.request("GET", "/api/v4/users", what="GET /api/v4/users",
                                              params={"limit": "250", "page": str(page)})
            raise_unless_ok(status, "GET /api/v4/users")
            users, more = users_page(body)
            found.extend(users)
            if not more:
                break
        return found


def users_page(body: Any) -> tuple[list[CrmUserInfo], bool]:
    """`GET /api/v4/users` sahifasi → (foydalanuvchilar, keyingi sahifa bormi)."""
    page = body if isinstance(body, dict) else {}
    users = (page.get("_embedded") or {}).get("users") or []
    return [user_info(u) for u in users if isinstance(u, dict)], bool((page.get("_links") or {}).get("next"))


def raise_unless_ok(status: int, what: str) -> None:
    if not 200 <= status < 300:
        raise crm.failure(f"{what}: so'rov rad etildi (HTTP {status})", status=status, permanent=True)


# ------------------------------------------------------------ yetkazuvchi
@dataclass(frozen=True)
class AmoSettings:
    base_url: str
    token: str
    unsorted_for_unknown: bool
    default_user_id: str | None

    @classmethod
    def parse(cls, config: Mapping[str, Any], secrets: Mapping[str, str]) -> AmoSettings:
        return cls(base_url=str(config.get("base_url") or ""), token=secrets.get("token", ""),
                   unsorted_for_unknown=bool(config.get("unsorted_for_unknown", True)),
                   default_user_id=config.get("default_user_id") or None)


async def log_call(client: AmoClient, call: Mapping[str, Any], *, responsible: str | None, unsorted: bool) -> str:
    status, body = await client.request("POST", "/api/v4/calls", what="POST /api/v4/calls",
                                        json=[call_body(call, responsible_user_id=responsible)])
    if not contact_missing(status, body):
        raise_unless_ok(status, "POST /api/v4/calls")
        return "calls"
    if not unsorted:
        return "skipped:contact_not_found"
    status, _ = await client.request("POST", "/api/v4/leads/unsorted/sip", what="POST /api/v4/leads/unsorted/sip",
                                     json=[unsorted_body(call)])
    raise_unless_ok(status, "POST /api/v4/leads/unsorted/sip")
    return "unsorted"


class AmoCrmProvider:
    def __init__(self, *, url_check: Callable[[str], None] = ssrf.check_url_default,
                 transport: httpx.AsyncBaseTransport | None = None, limiter: crm.RateLimiter = LIMITER) -> None:
        self._url_check, self._transport, self._limiter = url_check, transport, limiter

    def client(self, subscription_id: str, config: AmoSettings) -> AmoClient:
        if not config.base_url or not config.token:
            raise crm.failure("not_configured: base_url yoki token yo'q", permanent=True)
        try:
            self._url_check(config.base_url)
        except ssrf.UrlForbidden as exc:
            raise crm.failure(f"url_forbidden:{exc.reason}", permanent=True) from exc
        return AmoClient(config.base_url, config.token, HttpTarget(self._limiter, subscription_id, self._transport))

    async def deliver(self, ctx: DeliveryContext) -> DeliveryResult:
        call = ctx.event.payload.get("call") or {}
        if ctx.event.type != "call.ended" or not crm.is_external(call):
            return DeliveryResult(ok=True, response_body="skipped")
        sub = ctx.subscription
        config = AmoSettings.parse(sub.config, crm.load_secrets(sub.secret))
        try:
            client = self.client(sub.id, config)
            users = await crm.load_user_map(ctx.session, sub.tenant_id, KIND, config.default_user_id)
            responsible = users.user_for(call.get("answered_by"), call.get("extension"))
            summary = await log_call(client, call, responsible=responsible, unsorted=config.unsorted_for_unknown)
        except CrmCallError as exc:
            return exc.result
        return DeliveryResult(ok=True, status_code=200, response_body=summary)


PROVIDER = AmoCrmProvider()
register_provider(KIND, PROVIDER)
