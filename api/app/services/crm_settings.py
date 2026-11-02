"""CRM sozlamalari (m3b-contract.md §5) — obuna qatori, sirlar, foydalanuvchi xaritasi, holat, ulanish testi.

Saqlash: `integration_subscriptions` (kind bitrix24|amocrm, tenant'da BITTA qator — birinchi o'qishda yaratiladi,
`enabled=false`). Ochiq sozlamalar `config` da, sirlar `secret_enc` da (JSON; javobda faqat `has_*`/`*_set`).
Yoqilgan qator outbox obunasi: `emit_event` unga ham yetkazish yaratadi (`events` — yetkazuvchi kerak qilganlari).
"""
from __future__ import annotations

import secrets as pysecrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import CrmUser, CrmUserMap, Extension, IntegrationSubscription
from app.schemas_crm import (
    AmoConfigOut,
    BitrixConfigOut,
    CrmConfigResult,
    CrmStatusOut,
    CrmTestResult,
    CrmUserMapEntryIn,
    CrmUserMapEntryOut,
)
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.integrations import amocrm, bitrix24, crm
from app.services.integrations.crm import CrmCallError, CrmUserInfo

NAMES = {"bitrix24": "Bitrix24", "amocrm": "amoCRM"}
EVENTS = {"bitrix24": ["call.answered", "call.ended", "call.ringing"], "amocrm": ["call.ended"]}


def default_config(provider: str) -> dict[str, Any]:
    if provider == "bitrix24":
        return {"create_lead": True, "popup_max_delay_s": bitrix24.DEFAULT_POPUP_MAX_DELAY_S,
                "default_user_id": None, "hook_token": new_hook_token()}
    return {"base_url": "", "unsorted_for_unknown": True, "default_user_id": None}


def new_hook_token() -> str:
    return pysecrets.token_urlsafe(18)


def is_configured(provider: str, config: Mapping[str, Any], secrets: Mapping[str, str]) -> bool:
    if provider == "bitrix24":
        return bool(secrets.get("webhook_url"))
    return bool(config.get("base_url")) and bool(secrets.get("token"))


# ------------------------------------------------------------ obuna qatori
async def ensure_subscription(session: AsyncSession, tenant_id: str, provider: str) -> IntegrationSubscription:
    """Idempotent: yo'q bo'lsa `enabled=false` qator (UNIQUE (tenant, kind) — parallel so'rov ham bitta)."""
    await session.execute(pg_insert(IntegrationSubscription).values(
        tenant_id=tenant_id, kind=provider, name=NAMES[provider], config=default_config(provider),
        events=EVENTS[provider], include_internal=False, enabled=False,
    ).on_conflict_do_nothing())
    return (await session.execute(select(IntegrationSubscription).where(
        IntegrationSubscription.tenant_id == tenant_id, IntegrationSubscription.kind == provider,
    ))).scalar_one()


async def read_secrets(session: AsyncSession, sub: IntegrationSubscription) -> dict[str, str]:
    return crm.load_secrets(await decrypt_secret(session, sub.secret_enc)) if sub.secret_enc else {}


# ------------------------------------------------------------ javob
def config_out(provider: str, config: Mapping[str, Any], secrets: Mapping[str, str]) -> BitrixConfigOut | AmoConfigOut:
    """Sirlar HECH QACHON — faqat borligi."""
    if provider == "bitrix24":
        return BitrixConfigOut(
            has_webhook_url=bool(secrets.get("webhook_url")), create_lead=bool(config.get("create_lead", True)),
            popup_max_delay_s=int(config.get("popup_max_delay_s", bitrix24.DEFAULT_POPUP_MAX_DELAY_S)),
            default_user_id=config.get("default_user_id"),
            application_token_set=bool(secrets.get("application_token")), hook_token=str(config.get("hook_token", "")))
    return AmoConfigOut(base_url=str(config.get("base_url") or ""), token_set=bool(secrets.get("token")),
                        unsorted_for_unknown=bool(config.get("unsorted_for_unknown", True)),
                        default_user_id=config.get("default_user_id"))


def status_out(sub: IntegrationSubscription, unmapped: list[str]) -> CrmStatusOut:
    if not sub.enabled:
        return CrmStatusOut(state="disabled", last_ok_at=sub.last_success_at,
                            last_error=sub.disabled_reason or sub.last_error, unmapped_extensions=[])
    return CrmStatusOut(state="error" if sub.last_error else "ok", last_ok_at=sub.last_success_at,
                        last_error=sub.last_error, unmapped_extensions=unmapped)


@dataclass(frozen=True)
class MapRow:
    crm_user_id: str
    source: str


def merge_user_map(extensions: Iterable[tuple[str, bool]], rows: Mapping[str, MapRow],
                   names: Mapping[str, str]) -> tuple[list[CrmUserMapEntryOut], list[str]]:
    """Har ichki raqam bitta qator (xaritasizi ham — UI tahrirlay olsin); `unmapped` — yoqilgan, xaritasiz."""
    entries: list[CrmUserMapEntryOut] = []
    unmapped: list[str] = []
    for number, enabled in extensions:
        row = rows.get(number)
        uid = row.crm_user_id if row else None
        entries.append(CrmUserMapEntryOut(extension=number, crm_user_id=uid, crm_user_name=names.get(uid or ""),
                                          source="manual" if row and row.source == "manual" else "auto"))
        if enabled and uid is None:
            unmapped.append(number)
    return entries, unmapped


async def user_map(session: AsyncSession, tenant_id: str, provider: str) -> tuple[list[CrmUserMapEntryOut], list[str]]:
    extensions = (await session.execute(select(Extension.number, Extension.enabled).where(
        Extension.tenant_id == tenant_id).order_by(Extension.number))).all()
    rows = (await session.execute(select(CrmUserMap.extension, CrmUserMap.crm_user_id, CrmUserMap.source).where(
        CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == provider))).all()
    names = (await session.execute(select(CrmUser.crm_user_id, CrmUser.name).where(
        CrmUser.tenant_id == tenant_id, CrmUser.provider == provider))).all()
    return merge_user_map([(n, bool(e)) for n, e in extensions], {x: MapRow(u, s) for x, u, s in rows},
                          {u: n for u, n in names})


async def crm_view(session: AsyncSession, sub: IntegrationSubscription) -> CrmConfigResult:
    secrets = await read_secrets(session, sub)
    entries, unmapped = await user_map(session, str(sub.tenant_id), sub.kind)
    return CrmConfigResult(enabled=sub.enabled, config=config_out(sub.kind, sub.config or {}, secrets),
                           status=status_out(sub, unmapped), user_map=entries, updated_at=sub.updated_at)


# ------------------------------------------------------------ PUT
@dataclass(frozen=True)
class Changes:
    """Tekshirilgan o'zgarishlar: `config` — ochiq, `secrets` — faqat berilganlari (bo'sh → eskisi qoladi)."""
    enabled: bool
    config: dict[str, Any]
    secrets: dict[str, str] = field(default_factory=dict)

    def audit_diff(self) -> dict[str, Any]:
        return {"enabled": self.enabled, **self.config, **{k: "***" for k in self.secrets}}


async def apply_changes(session: AsyncSession, sub: IntegrationSubscription, changes: Changes) -> None:
    secrets = {**await read_secrets(session, sub), **changes.secrets}
    config = {**(sub.config or {}), **changes.config}
    if changes.enabled and not is_configured(sub.kind, config, secrets):
        raise ApiError(422, "not_configured", "Yoqishdan oldin ulanish ma'lumotlarini kiriting",
                       field="webhook_url" if sub.kind == "bitrix24" else "base_url")
    sub.config = config
    if changes.secrets:
        sub.secret_enc = await encrypt_secret(session, crm.dump_secrets(secrets))
    if changes.enabled and not sub.enabled:  # qayta yoqish — avto-o'chirish sababi va xato hisobi tozalanadi
        sub.disabled_reason, sub.failing_since = None, None
    sub.enabled = changes.enabled


# ------------------------------------------------------------ foydalanuvchilar va xarita
def auto_map(users: Iterable[CrmUserInfo], extensions: set[str], manual: set[str]) -> dict[str, str]:
    """Bitrix `UF_PHONE_INNER` = ichki raqam → avto; qo'lda kiritilgan raqamga tegilmaydi; birinchisi yutadi."""
    found: dict[str, str] = {}
    for user in users:
        inner = user.inner_phone
        if inner and inner in extensions and inner not in manual and inner not in found:
            found[inner] = user.id
    return found


async def store_users(session: AsyncSession, tenant_id: str, provider: str, users: list[CrmUserInfo]) -> None:
    await session.execute(delete(CrmUser).where(CrmUser.tenant_id == tenant_id, CrmUser.provider == provider))
    unique = {u.id: u for u in users if u.id}
    if unique:
        await session.execute(pg_insert(CrmUser).values([
            {"tenant_id": tenant_id, "provider": provider, "crm_user_id": u.id, "name": u.name[:200],
             "inner_phone": u.inner_phone} for u in unique.values()]))


async def refresh_auto_map(session: AsyncSession, tenant_id: str, provider: str, users: list[CrmUserInfo]) -> int:
    numbers = set((await session.execute(select(Extension.number).where(
        Extension.tenant_id == tenant_id))).scalars().all())
    manual = set((await session.execute(select(CrmUserMap.extension).where(
        CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == provider,
        CrmUserMap.source == "manual"))).scalars().all())
    await session.execute(delete(CrmUserMap).where(CrmUserMap.tenant_id == tenant_id,
                                                   CrmUserMap.provider == provider, CrmUserMap.source == "auto"))
    mapped = auto_map(users, numbers, manual)
    if mapped:
        await session.execute(pg_insert(CrmUserMap).values([
            {"tenant_id": tenant_id, "provider": provider, "extension": ext, "crm_user_id": uid, "source": "auto"}
            for ext, uid in mapped.items()]))
    return len(mapped)


async def fetch_users(sub: IntegrationSubscription, secrets: Mapping[str, str]) -> list[CrmUserInfo]:
    if sub.kind == "bitrix24":
        return await bitrix24.PROVIDER.client(str(sub.id), secrets.get("webhook_url", "")).users()
    config = amocrm.AmoSettings.parse(sub.config or {}, secrets)
    return await amocrm.PROVIDER.client(str(sub.id), config).users()


async def test_connection(session: AsyncSession, sub: IntegrationSubscription) -> CrmTestResult:
    """Ulanish + foydalanuvchilarni yuklash (Bitrix'da avto-xarita). Natija obuna holatiga yoziladi."""
    secrets = await read_secrets(session, sub)
    if not is_configured(sub.kind, sub.config or {}, secrets):
        raise ApiError(422, "not_configured", "Avval ulanish ma'lumotlarini saqlang")
    try:
        users = await fetch_users(sub, secrets)
    except CrmCallError as exc:
        sub.last_error = exc.result.error
        return CrmTestResult(ok=False, message=exc.result.error or "Ulanish xatosi", users_loaded=None)
    await store_users(session, str(sub.tenant_id), sub.kind, users)
    auto = await refresh_auto_map(session, str(sub.tenant_id), sub.kind, users) if sub.kind == "bitrix24" else 0
    sub.last_error, sub.last_success_at = None, datetime.now(timezone.utc)
    return CrmTestResult(ok=True, message=f"Ulanish muvaffaqiyatli — {len(users)} ta foydalanuvchi yuklandi"
                                          f" (avto-xarita: {auto})", users_loaded=len(users))


async def update_user_map(session: AsyncSession, tenant_id: str, provider: str,
                          entries: list[CrmUserMapEntryIn]) -> None:
    """Qo'lda: `crm_user_id` → `manual` qator; `null` → qator o'chadi (raqam xaritasiz / avto-xaritaga ochiq)."""
    wanted = {e.extension for e in entries}
    known = set((await session.execute(select(Extension.number).where(
        Extension.tenant_id == tenant_id, Extension.number.in_(wanted)))).scalars().all())
    missing = sorted(wanted - known)
    if missing:
        raise ApiError(422, "unknown_extension", f"Ichki raqam topilmadi: {', '.join(missing)}", field="entries",
                       details={"extensions": missing})
    for entry in entries:
        await _save_entry(session, tenant_id, provider, entry)


async def _save_entry(session: AsyncSession, tenant_id: str, provider: str, entry: CrmUserMapEntryIn) -> None:
    key = (CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == provider, CrmUserMap.extension == entry.extension)
    if entry.crm_user_id is None:
        await session.execute(delete(CrmUserMap).where(*key))
        return
    stmt = pg_insert(CrmUserMap).values(tenant_id=tenant_id, provider=provider, extension=entry.extension,
                                        crm_user_id=entry.crm_user_id, source="manual")
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["tenant_id", "provider", "extension"],
        set_={"crm_user_id": stmt.excluded.crm_user_id, "source": "manual", "updated_at": datetime.now(timezone.utc)}))
