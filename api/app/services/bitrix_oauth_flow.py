"""Bitrix24 OAuth ulash oqimi (`bitrix-oauth-shartnoma.md` §2/§3) — Innova backend bu yerda
markaziy brokerning (`bitrix_broker.py`) MIJOZI: `connect` (ulash boshlash) -> `poll` (natija) ->
`run_setup` (ilova sozlash: `app.info` -> liniyalar -> standart chiquvchi liniya -> `event.bind` ->
foydalanuvchi sinxroni) -> `disconnect`. Har mutatsiya audit qilinadi (`record_audit`); sirlar
(`ulanish_id`/`ulanish_sir`/`application_token`) hech qachon audit diff'da yoki javobda ochiq chiqmaydi.

Sozlash qadamlaridan birortasi (token olishdan TASHQARI) muvaffaqiyatsiz bo'lsa — BUTUN sozlash
TO'XTAMAYDI, faqat ogohlantirish (`warnings`) ro'yxatiga qo'shiladi (shartnoma §2 `connect/poll`)."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IntegrationSubscription
from app.services import crm_settings
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret
from app.services.integrations import bitrix24, bitrix_broker, crm
from app.services.integrations.crm import CrmCallError

MASK = "***"
_SECRET_FIELDS = ("ulanish_id", "ulanish_sir", "application_token", "pending_sessiya")
_LICENSE_CACHE_TTL_S = 300
_ALREADY_BINDED_MARKER = "already binded"


# ------------------------------------------------------------ saqlash (sir hech qachon tashqariga)
async def _save(session: AsyncSession, sub: IntegrationSubscription, *, config_patch: dict[str, Any] | None = None,
                secret_patch: dict[str, str] | None = None) -> dict[str, str]:
    secrets = {**await crm_settings.read_secrets(session, sub), **(secret_patch or {})}
    sub.config = {**(sub.config or {}), **(config_patch or {})}
    if secret_patch:
        sub.secret_enc = await encrypt_secret(session, crm.dump_secrets(secrets))
    return secrets


def _masked_secret_diff(secret_patch: dict[str, str]) -> dict[str, str]:
    return {k: MASK for k in secret_patch}


# ------------------------------------------------------------ connect (boshla)
def connect_error_detail(error: bitrix_broker.BrokerError) -> tuple[int, str, str]:
    """Broker xatosi -> `(http_status, code, message)` — router `ApiError`ga aylantiradi
    (shartnoma §2: `invalid_domain`, `app_not_installed`, `broker_unreachable`)."""
    if error.status is None:
        return 502, "broker_unreachable", error.message
    if error.status == 404:
        return 404, "app_not_installed", error.message
    if error.status == 400:
        return 400, "invalid_domain", error.message
    return 502, "broker_unreachable", error.message


async def connect(session: AsyncSession, sub: IntegrationSubscription, domain: str, *, user_id: str | None,
                  transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Broker `boshla` -> `authorize_url`; `sessiya` vaqtincha `pending_sessiya` sirida saqlanadi."""
    result = await bitrix_broker.boshla(domain, transport=transport)
    await _save(session, sub, config_patch={"domain": domain},
               secret_patch={"pending_sessiya": result.sessiya})
    await record_audit(session, tenant_id=str(sub.tenant_id), user_id=user_id, action="crm.bitrix24.connect",
                       entity="crm", entity_id=sub.kind, diff={"domain": domain})
    return result.authorize_url


# ------------------------------------------------------------ poll (natija)
@dataclass(frozen=True)
class SetupResult:
    lines: int
    default_line: bool
    event_bound: bool
    users_synced: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PollResult:
    status: str  # "pending" | "error" | "connected"
    code: str | None = None
    message: str | None = None
    setup: SetupResult | None = None


async def poll(session: AsyncSession, sub: IntegrationSubscription, *, user_id: str | None,
              transport: httpx.AsyncBaseTransport | None = None,
              public_base_url: str | None = None) -> PollResult:
    secrets = await crm_settings.read_secrets(session, sub)
    sessiya = secrets.get("pending_sessiya", "")
    if not sessiya:
        return PollResult(status="error", code="no_session", message="Ulash boshlanmagan")
    result = await bitrix_broker.natija(sessiya, transport=transport)
    if result.holat in ("kutilmoqda",):
        return PollResult(status="pending")
    if result.holat == "olingan":
        return PollResult(status="error", code="already_taken",
                          message="Ulash natijasi allaqachon olingan — qayta urinib ko'ring")
    if result.holat != "tayyor":
        return PollResult(status="error", code=result.xato or "xato", message=result.xabar or "Xato")
    secret_patch = {"ulanish_id": result.ulanish_id or "", "ulanish_sir": result.ulanish_sir or "",
                    "pending_sessiya": ""}
    if result.application_token:
        secret_patch["application_token"] = result.application_token
    config_patch = {"auth_mode": "oauth", "domain": result.domain or sub.config.get("domain"),
                    "member_id": result.member_id}
    await _save(session, sub, config_patch=config_patch, secret_patch=secret_patch)
    await record_audit(session, tenant_id=str(sub.tenant_id), user_id=user_id, action="crm.bitrix24.connect",
                       entity="crm", entity_id=sub.kind,
                       diff={**config_patch, "secrets": _masked_secret_diff(secret_patch)})
    setup = await run_setup(session, sub, user_id=user_id, transport=transport, public_base_url=public_base_url)
    return PollResult(status="connected", setup=setup)


# ------------------------------------------------------------ setup (app.info -> liniyalar -> event.bind -> sync)
def _is_already_binded(error: CrmCallError) -> bool:
    return _ALREADY_BINDED_MARKER in (error.result.error or "").lower()


def event_handler_url(public_base_url: str, hook_token: str) -> str:
    return f"{public_base_url.rstrip('/')}/api/public/v1/crm/bitrix24/{hook_token}/call"


async def _app_id(client: bitrix24.BitrixClient, warnings: list[str]) -> str:
    try:
        info = await client.call("app.info", {})
    except CrmCallError:
        warnings.append("default_line_failed")
        return ""
    return str((info or {}).get("ID") or "")


async def _default_line(client: bitrix24.BitrixClient, app_id: str, warnings: list[str]) -> bool:
    if not app_id:
        return False
    line_id = f"REST_APP:{app_id}"
    try:
        await client.call("voximplant.line.outgoing.set", {"LINE_ID": line_id})
        current = await client.call("voximplant.line.outgoing.get", {})
    except CrmCallError:
        warnings.append("default_line_failed")
        return False
    if line_id not in str(current):
        warnings.append("default_line_failed")
        return False
    return True


async def _bind_event(client: bitrix24.BitrixClient, public_base_url: str | None, hook_token: str,
                      warnings: list[str]) -> bool:
    if not public_base_url:
        warnings.append("public_url_missing")
        return False
    try:
        await client.call("event.bind", {"EVENT": "ONEXTERNALCALLSTART",
                                         "HANDLER": event_handler_url(public_base_url, hook_token)})
        return True
    except CrmCallError as exc:
        if _is_already_binded(exc):
            return True
        warnings.append("event_bind_failed")
        return False


async def _sync_lines(session: AsyncSession, sub: IntegrationSubscription, client: bitrix24.BitrixClient,
                      warnings: list[str]) -> int:
    try:
        dids = await crm_settings.tenant_dids(session, str(sub.tenant_id))
        return await bitrix24.ensure_lines(client, dids, create_lead=bool((sub.config or {}).get("create_lead", True)))
    except Exception:  # noqa: BLE001 — liniyalar MUHIM EMAS, sozlash davom etadi
        warnings.append("lines_failed")
        return 0


async def _sync_users(session: AsyncSession, sub: IntegrationSubscription, client: bitrix24.BitrixClient,
                      warnings: list[str]) -> int:
    try:
        users = await client.users()
    except CrmCallError:
        warnings.append("users_failed")
        return 0
    await crm_settings.store_users(session, str(sub.tenant_id), sub.kind, users)
    return await crm_settings.refresh_auto_map(session, str(sub.tenant_id), sub.kind, users)


async def _remember_application_token(session: AsyncSession, sub: IntegrationSubscription,
                                     secrets: dict[str, str], application_token: str | None) -> None:
    """Lokal ilovada ONAPPINSTALL «Переустановить»dan keyin keladi — token `natija`da bo'lmaydi,
    brokerning `/token` javobida keyinroq paydo bo'ladi. Yangi/o'zgargan bo'lsa saqlaymiz."""
    if application_token and secrets.get("application_token") != application_token:
        await _save(session, sub, secret_patch={"application_token": application_token})


async def run_setup(session: AsyncSession, sub: IntegrationSubscription, *, user_id: str | None,
                    transport: httpx.AsyncBaseTransport | None = None,
                    public_base_url: str | None = None) -> SetupResult:
    """Tartib ANIQ (shartnoma §2): token -> `app.info` -> liniyalar -> standart liniya ->
    `event.bind` -> foydalanuvchi sinxroni. Token olinmasa — doimiy xato (to'xtaydi); qolgan
    HAR bir qadam mustaqil — xatosi faqat `warnings`ga qo'shiladi."""
    secrets = await crm_settings.read_secrets(session, sub)
    settings = bitrix24.BitrixSettings.parse(sub.config or {}, secrets)
    if settings.auth_mode != "oauth" or not settings.ulanish_id:
        raise crm.failure("not_configured: OAuth ulanish yo'q", permanent=True)
    try:  # token olinmasa — BUTUN sozlash to'xtaydi (shartnoma §2); qolgan qadamlar mustaqil
        token = await bitrix_broker.get_token(settings.ulanish_id, settings.ulanish_sir, transport=transport)
    except bitrix_broker.BrokerError as exc:
        raise bitrix_broker.to_crm_failure(exc) from exc
    await _remember_application_token(session, sub, secrets, token.application_token)
    client = bitrix24.PROVIDER.client_for(str(sub.id), settings)
    warnings: list[str] = []
    app_id = await _app_id(client, warnings)
    lines = await _sync_lines(session, sub, client, warnings)
    default_line = await _default_line(client, app_id, warnings)
    event_bound = await _bind_event(client, public_base_url, str((sub.config or {}).get("hook_token", "")), warnings)
    users_synced = await _sync_users(session, sub, client, warnings)
    result = SetupResult(lines=lines, default_line=default_line, event_bound=event_bound,
                         users_synced=users_synced, warnings=warnings)
    await record_audit(session, tenant_id=str(sub.tenant_id), user_id=user_id, action="crm.bitrix24.setup",
                       entity="crm", entity_id=sub.kind,
                       diff={"lines": lines, "default_line": default_line, "event_bound": event_bound,
                             "users_synced": users_synced, "warnings": warnings})
    return result


# ------------------------------------------------------------ disconnect (uzish)
async def disconnect(session: AsyncSession, sub: IntegrationSubscription, *, user_id: str | None,
                     transport: httpx.AsyncBaseTransport | None = None,
                     public_base_url: str | None = None) -> None:
    """Best-effort `event.unbind` + broker `uzish`; sirlar tozalanadi, `auth_mode` `None` bo'ladi.
    OAuth ulanmagan bo'lsa — hech narsa yozilmaydi (idempotent no-op)."""
    secrets = await crm_settings.read_secrets(session, sub)
    settings = bitrix24.BitrixSettings.parse(sub.config or {}, secrets)
    if settings.auth_mode != "oauth" or not settings.ulanish_id:
        return
    if public_base_url:
        try:
            client = bitrix24.PROVIDER.client_for(str(sub.id), settings)
            hook_token = str((sub.config or {}).get("hook_token", ""))
            await client.call("event.unbind", {"EVENT": "ONEXTERNALCALLSTART",
                                               "HANDLER": event_handler_url(public_base_url, hook_token)})
        except CrmCallError:
            pass  # best-effort — uzishni to'xtatmaydi
    await bitrix_broker.uzish(settings.ulanish_id, settings.ulanish_sir, transport=transport)
    remaining = {k: v for k, v in secrets.items() if k not in _SECRET_FIELDS}
    sub.config = {**(sub.config or {}), "auth_mode": None, "domain": None, "member_id": None}
    sub.secret_enc = await encrypt_secret(session, crm.dump_secrets(remaining))
    await record_audit(session, tenant_id=str(sub.tenant_id), user_id=user_id, action="crm.bitrix24.disconnect",
                       entity="crm", entity_id=sub.kind,
                       diff={"auth_mode": None, "secrets": {k: MASK for k in _SECRET_FIELDS}})


# ------------------------------------------------------------ litsenziya (5 daq kesh)
Clock = Callable[[], float]
_license_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def reset_license_cache() -> None:
    """Faqat testlar uchun — keshi sinovlar orasida sizmasin."""
    _license_cache.clear()


async def license_info(session: AsyncSession, sub: IntegrationSubscription, *,
                       transport: httpx.AsyncBaseTransport | None = None,
                       clock: Clock = time.monotonic) -> dict[str, Any]:
    secrets = await crm_settings.read_secrets(session, sub)
    ulanish_id = secrets.get("ulanish_id", "")
    if not ulanish_id:
        return {"connected": False, "license": None, "error": None}
    now = clock()
    cached = _license_cache.get(ulanish_id)
    if cached is not None and now - cached[0] < _LICENSE_CACHE_TTL_S:
        return {"connected": True, "license": cached[1], "error": None}
    try:
        body = await bitrix_broker.litsenziya(ulanish_id, secrets.get("ulanish_sir", ""), transport=transport)
    except bitrix_broker.BrokerError as exc:
        return {"connected": True, "license": None, "error": exc.message}
    _license_cache[ulanish_id] = (now, body)
    return {"connected": True, "license": body, "error": None}
