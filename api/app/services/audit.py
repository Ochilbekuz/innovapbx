"""Audit jurnali — har yozuvchi amal `audit_log`ga yoziladi
(architecture.md: «Har yozuvchi so'rov: audit + qo'llash jarayoni»).

m1b-contract.md bo'lim 6: parol/PIN/sir maydonlari `diff` ichida `"***"` bo'lishi
SHART — hech qachon ochiq matnda audit jurnaliga (yoki javobga) chiqmasin."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

MASK = "***"

# m1b-contract.md bo'lim 6: `audit_log.action` FAQAT shu 8 umumiy fe'ldan
# biri bo'lishi SHART (`web/src/api/types.ts` `AuditAction` — qattiq literal
# union, frontend `ACTION_LABEL[action]`/`ACTION_TONE[action]` Record orqali
# ko'rsatadi — noma'lum qiymat UI'da jim tarzda bo'sh belgi bo'lib chiqadi).
# Routerlar ko'pincha ANIQROQ `"<entity>.<fe'l>"` shaklda yozadi (masalan
# "moh_class.create", "extension.rotate_secret") — bu aniqlik `entity`/`diff`
# ustunlarida saqlanib qoladi, shu sabab shu yerda XAVFSIZ umumiy fe'lga
# tushiriladi (DB'ga yozishdan OLDIN — yagona joy, har bir chaqiruv nuqtasini
# o'zgartirish shart emas).
_VALID_ACTIONS = {"create", "update", "delete", "login", "login_failed", "restore", "restart", "override"}
_ACTION_SUFFIX_ALIASES = {
    "rotate_secret": "update",
    "import_uz": "create",
    "reorder": "update",
    "add_member": "update",
}


def normalize_action(action: str) -> str:
    """`"entity.fe'l"` → faqat `fe'l` (agar contract ro'yxatida bo'lsa) yoki
    ma'lum alias; bo'lmasa xavfsiz standart — `"update"` (har qanday mutatsiya
    kamida shu toifaga tushadi)."""
    if "." not in action:
        return action
    _, _, suffix = action.rpartition(".")
    if suffix in _VALID_ACTIONS:
        return suffix
    return _ACTION_SUFFIX_ALIASES.get(suffix, "update")

# Nomi shu so'zlarni O'Z ICHIGA OLGAN (pastki registr) maydonlar — qiymati
# har doim MASK bilan almashtiriladi, `diff` strukturasi qanday bo'lishidan
# qat'i nazar (`{"old","new"}`, `{"from","to"}`, tekis qiymat).
# "token" — M1c: Telegram bot tokeni (`/settings/notify`).
_SECRET_MARKERS = ("password", "pin", "secret", "pin_hash", "password_enc", "token")


def _is_secret_field(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def mask_secrets(diff: dict[str, Any]) -> dict[str, Any]:
    """Har bir maydon nomini tekshiradi — sir bo'lsa, qiymati (ichki tuzilishi
    qanday bo'lishidan qat'i nazar) `"***"` bilan almashtiriladi."""
    masked: dict[str, Any] = {}
    for field_name, value in diff.items():
        if _is_secret_field(field_name):
            if isinstance(value, dict):
                masked[field_name] = {k: MASK for k in value}
            else:
                masked[field_name] = MASK
        else:
            masked[field_name] = value
    return masked


async def record_audit(
    session: AsyncSession, *, tenant_id: str, user_id: str | None, action: str, entity: str,
    entity_id: str | None = None, diff: dict[str, Any] | None = None, ip: str | None = None,
) -> None:
    session.add(AuditLog(
        tenant_id=tenant_id, user_id=user_id, action=normalize_action(action), entity=entity,
        entity_id=entity_id, diff=mask_secrets(diff or {}), ip=ip,
    ))
