"""Bitrix24 yetkazuvchisi (m3b-contract.md §5) — kiruvchi webhook `https://<portal>/rest/<user>/<code>/`.

Xaritalash:
  call.ringing  → bog'lanish yo'q: `telephony.externalcall.register` (TYPE 2 kiruvchi / 1 chiquvchi, SHOW=1,
                  kechikkan bo'lsa `> popup_max_delay_s` → SHOW=0), `CALL_ID` → `crm_call_links`;
                  bog'lanish bor (keyingi jiringlagan raqam) → `telephony.externalcall.show`.
  call.answered → javob bermagan, karta ko'rsatilgan foydalanuvchilarga `telephony.externalcall.hide`.
  call.ended    → (register yetkazilmagan bo'lsa avval register SHOW=0) `telephony.externalcall.finish`
                  USER_ID = answered_by / oxirgi jiringlagan / default, DURATION = billsec,
                  STATUS_CODE 200/304/486/603, RECORD_URL = birinchi yozuv havolasi.
Tartib — dispetcher kafolati: `(obuna, call)` bo'yicha QAT'IY ketma-ket (register finish'dan oldin).
Rate limit: 2 so'rov/s obunaga (mijoz tomonida; `QUERY_LIMIT_EXCEEDED` — urinish sanalmaydi).
Webhook URL — sir: xato matnida hech qachon bo'lmaydi.
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.db.models import CrmCallLink
from app.services.integrations import crm, ssrf
from app.services.integrations.crm import CrmCallError, CrmUserInfo, HttpTarget, UserMap
from app.services.integrations.providers import DeliveryContext, DeliveryResult, register_provider

KIND = "bitrix24"
RPS = 2.0
DEFAULT_POPUP_MAX_DELAY_S = 20
USER_PAGES_MAX = 40
_WEBHOOK_PATH = re.compile(r"^/rest/[0-9]+/[A-Za-z0-9_]+/?$")
STATUS_CODES = {"answered": "200", "missed": "304", "busy": "486"}
RATE_CODES = frozenset({"QUERY_LIMIT_EXCEEDED", "OVERLOAD_LIMIT", "OPERATION_TIME_LIMIT"})
AUTH_CODES = frozenset({"EXPIRED_TOKEN", "INVALID_TOKEN", "INVALID_CREDENTIALS", "NO_AUTH_FOUND",
                        "AUTHORIZATION_ERROR", "INVALID_GRANT", "INSUFFICIENT_SCOPE", "ACCESS_DENIED"})

LIMITER = crm.RateLimiter(RPS)


# ------------------------------------------------------------ sof qoidalar
class InvalidWebhookUrl(ValueError):
    pass


def normalize_webhook_url(raw: str) -> str:
    """`http(s)://<portal>/rest/<user>/<code>/` — oxiriga `/`; boshqa shakl → `InvalidWebhookUrl`."""
    url = raw.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment \
            or not _WEBHOOK_PATH.match(parts.path):
        raise InvalidWebhookUrl(raw)
    return url if url.endswith("/") else url + "/"


def status_code(status: str | None) -> str:
    """answered 200, missed 304 (javobsiz), busy 486 (band), qolgani 603 (rad/amalga oshmadi)."""
    return STATUS_CODES.get(status or "", "603")


def bitrix_time(value: datetime) -> str:
    """ISO-8601, ofset HAR DOIM raqamli (VoxBridge: Bitrix «Z» ni emas, `+00:00` ni kutadi)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def is_late(occurred_at: datetime | None, now: datetime, max_delay_s: int) -> bool:
    return occurred_at is not None and (now - occurred_at).total_seconds() > max_delay_s


def register_params(call: Mapping[str, Any], *, user_id: str, create_lead: bool, show: bool,
                    started_at: datetime) -> dict[str, str]:
    params = {
        "USER_ID": user_id, "PHONE_NUMBER": crm.external_number(call),
        "TYPE": "2" if call.get("direction") == "inbound" else "1",
        "CALL_START_DATE": bitrix_time(started_at), "CRM_CREATE": "1" if create_lead else "0",
        "SHOW": "1" if show else "0", "EXTERNAL_CALL_ID": str(call.get("id") or ""),
    }
    if call.get("did"):
        params["LINE_NUMBER"] = str(call["did"])
    return params


def finish_params(call: Mapping[str, Any], *, call_id: str, user_id: str) -> dict[str, str]:
    params = {"CALL_ID": call_id, "USER_ID": user_id, "DURATION": str(int(call.get("billsec") or 0)),
              "STATUS_CODE": status_code(call.get("status")), "ADD_TO_CHAT": "1"}
    record_url = crm.first_recording_url(call)
    if record_url:
        params["RECORD_URL"] = record_url
    return params


def envelope_failure(code: str, description: str, *, what: str) -> CrmCallError | None:
    """Hujjatlashtirilgan Bitrix xato kodi → qaror; noma'lum kod → `None` (HTTP holati hal qiladi)."""
    text = f"{what}: {code} {description}".strip()
    if code in RATE_CODES:
        return crm.failure(text, retry_after_s=crm.DEFAULT_RETRY_AFTER_S)
    if code in AUTH_CODES:
        return crm.failure(text)
    return None


def classify(status: int, headers: Mapping[str, str], body: Any, *, what: str) -> CrmCallError | None:
    """Konvert kodi faqat ANIQLASHTIRADI: noma'lum kod 5xx ni doimiy xatoga aylantirmaydi (VoxBridge 02-crm-5xx)."""
    envelope = body if isinstance(body, dict) else {}
    code = str(envelope.get("error") or "").upper()
    description = str(envelope.get("error_description") or "")[:200]
    known = envelope_failure(code, description, what=what) if code else None
    if known is not None:
        return known
    by_http = crm.http_failure(status, headers, what=what)
    if by_http is not None or not code:
        return by_http
    return crm.failure(f"{what}: {code} {description}".strip(), status=status, permanent=True)


def user_info(raw: Mapping[str, Any]) -> CrmUserInfo:
    name = " ".join(str(raw.get(k) or "").strip() for k in ("NAME", "LAST_NAME")).strip()
    inner = str(raw.get("UF_PHONE_INNER") or "").strip() or None
    return CrmUserInfo(id=str(raw.get("ID")), name=name or str(raw.get("EMAIL") or raw.get("ID")), inner_phone=inner)


# ------------------------------------------------------------ REST mijoz
class BitrixClient:
    def __init__(self, webhook_url: str, target: HttpTarget) -> None:
        self._base = webhook_url.rstrip("/") + "/"
        self._target = target

    async def call(self, method: str, params: Mapping[str, str]) -> Any:
        """Form-encoded POST `<webhook>/<method>.json`; muvaffaqiyat → `result` maydoni."""
        resp = await crm.http_request(self._target, "POST", f"{self._base}{method}.json", what=method,
                                      data=dict(params))
        body = crm.json_body(resp)
        error = classify(resp.status_code, resp.headers, body, what=method)
        if error is not None:
            raise error
        return body.get("result") if isinstance(body, dict) else None

    async def users(self) -> list[CrmUserInfo]:
        """`user.get` sahifalab (50 tadan, `next`), ko'pi bilan `USER_PAGES_MAX` sahifa."""
        found: list[CrmUserInfo] = []
        start: int | None = 0
        for _ in range(USER_PAGES_MAX):
            body = await self._page(start)
            found.extend(user_info(u) for u in body.get("result") or [] if isinstance(u, dict))
            start = body.get("next")
            if start is None:
                break
        return found

    async def _page(self, start: int | None) -> dict:
        resp = await crm.http_request(self._target, "POST", f"{self._base}user.get.json", what="user.get",
                                      data={"start": str(start or 0)})
        body = crm.json_body(resp)
        error = classify(resp.status_code, resp.headers, body, what="user.get")
        if error is not None:
            raise error
        return body if isinstance(body, dict) else {}


# ------------------------------------------------------------ sozlamalar va oqim
@dataclass(frozen=True)
class BitrixSettings:
    webhook_url: str
    create_lead: bool
    popup_max_delay_s: int
    default_user_id: str | None

    @classmethod
    def parse(cls, config: Mapping[str, Any], secrets: Mapping[str, str]) -> BitrixSettings:
        return cls(webhook_url=secrets.get("webhook_url", ""), create_lead=bool(config.get("create_lead", True)),
                   popup_max_delay_s=int(config.get("popup_max_delay_s") or DEFAULT_POPUP_MAX_DELAY_S),
                   default_user_id=config.get("default_user_id") or None)


@dataclass
class Flow:
    """Bitta yetkazish: mijoz, xarita, bog'lanish ombori (`ctx.session`, commit — dispetcherda)."""
    client: BitrixClient
    ctx: DeliveryContext
    settings: BitrixSettings
    users: UserMap
    now: datetime

    @property
    def call(self) -> dict[str, Any]:
        return self.ctx.event.payload.get("call") or {}

    async def link(self) -> CrmCallLink | None:
        return await crm.get_link(self.ctx.session, self.ctx.subscription.tenant_id, KIND, str(self.call["id"]))

    async def register(self, user_id: str, *, show: bool, started_at: datetime) -> CrmCallLink:
        params = register_params(self.call, user_id=user_id, create_lead=self.settings.create_lead, show=show,
                                 started_at=started_at)
        result = await self.client.call("telephony.externalcall.register", params)
        call_id = str((result or {}).get("CALL_ID") or "") if isinstance(result, dict) else ""
        if not call_id:
            raise crm.failure("telephony.externalcall.register: CALL_ID qaytmadi", permanent=True)
        link = CrmCallLink(tenant_id=self.ctx.subscription.tenant_id, provider=KIND, linkedid=str(self.call["id"]),
                           external_call_id=call_id, origin="pbx", user_id=user_id,
                           shown_users=[user_id] if show else [])
        self.ctx.session.add(link)
        return link


async def on_ringing(flow: Flow) -> str:
    user = flow.users.user_for(flow.call.get("extension"))
    occurred_at = crm.parse_time(flow.ctx.event.payload.get("occurred_at")) or flow.now
    late = is_late(occurred_at, flow.now, flow.settings.popup_max_delay_s)
    link = await flow.link()
    if user is None:
        return "skipped:no_user"
    if link is None:
        link = await flow.register(user, show=not late, started_at=occurred_at)
        return f"register:{link.external_call_id}"
    if late or user in (link.shown_users or []):
        return "skipped:shown"
    await flow.client.call("telephony.externalcall.show", {"CALL_ID": link.external_call_id, "USER_ID": user})
    link.shown_users = [*(link.shown_users or []), user]
    return f"show:{user}"


async def on_answered(flow: Flow) -> str:
    link = await flow.link()
    if link is None:
        return "skipped:no_link"
    answerer = flow.users.by_extension.get(flow.call.get("extension") or "")
    others = [u for u in link.shown_users or [] if u != answerer]
    for user in others:
        await flow.client.call("telephony.externalcall.hide", {"CALL_ID": link.external_call_id, "USER_ID": user})
    return f"hide:{','.join(others)}"


async def on_ended(flow: Flow) -> str:
    call = flow.call
    link = await flow.link()
    user = flow.users.user_for(call.get("answered_by"), call.get("extension")) or (link.user_id if link else None)
    if user is None:
        return "skipped:no_user"
    if link is None:
        started_at = crm.parse_time(call.get("started_at")) or flow.now
        link = await flow.register(user, show=False, started_at=started_at)
    await flow.client.call("telephony.externalcall.finish", finish_params(call, call_id=link.external_call_id,
                                                                          user_id=user))
    return f"finish:{link.external_call_id}"


HANDLERS: dict[str, Callable[[Flow], Awaitable[str]]] = {
    "call.ringing": on_ringing, "call.answered": on_answered, "call.ended": on_ended,
}


# ------------------------------------------------------------ yetkazuvchi
class Bitrix24Provider:
    def __init__(self, *, url_check: Callable[[str], None] = ssrf.check_url_default,
                 transport: httpx.AsyncBaseTransport | None = None, limiter: crm.RateLimiter = LIMITER,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._url_check, self._transport, self._limiter, self._clock = url_check, transport, limiter, clock

    def client(self, subscription_id: str, webhook_url: str) -> BitrixClient:
        """Ruxsat etilgan URL uchun mijoz (SSRF har yuborishda — DNS rebinding); taqiq → doimiy xato."""
        try:
            self._url_check(webhook_url)
        except ssrf.UrlForbidden as exc:
            raise crm.failure(f"url_forbidden:{exc.reason}", permanent=True) from exc
        return BitrixClient(webhook_url, HttpTarget(self._limiter, subscription_id, self._transport))

    async def deliver(self, ctx: DeliveryContext) -> DeliveryResult:
        handler = HANDLERS.get(ctx.event.type)
        if handler is None or not crm.is_external(ctx.event.payload.get("call") or {}):
            return DeliveryResult(ok=True, response_body="skipped")
        sub = ctx.subscription
        config = BitrixSettings.parse(sub.config, crm.load_secrets(sub.secret))
        try:
            if not config.webhook_url:
                raise crm.failure("not_configured: webhook URL yo'q", permanent=True)
            users = await crm.load_user_map(ctx.session, sub.tenant_id, KIND, config.default_user_id)
            flow = Flow(self.client(sub.id, config.webhook_url), ctx, config, users, self._clock())
            summary = await handler(flow)
        except CrmCallError as exc:
            return exc.result
        return DeliveryResult(ok=True, status_code=200, response_body=summary)


PROVIDER = Bitrix24Provider()
register_provider(KIND, PROVIDER)
