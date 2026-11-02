"""M4a §3 — `GET/PATCH /settings/provisioning`, `POST /settings/provisioning/rotate-token` (admin).

`admin_password` faqat yoziladi (pgcrypto, javobda `has_admin_password`); `null`/`""` → o'chiriladi, berilmasa —
eskisi qoladi. Token almashtirilsa eski URL DARHOL 404 (`/prov/` har so'rovda bazadan o'qiydi).
`system_settings.updated_at` — butun qator uchun bitta optimistik qulf (boshqa sozlama bo'limlari bilan umumiy).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.api.v1.settings import get_settings_row
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import SystemSettings, User
from app.schemas_devices import ProvExtraOut, ProvisioningOut, RotateTokenPayload, UpdateProvisioningPayload
from app.services import prov_settings as ps
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret

router = APIRouter(prefix="/settings/provisioning", tags=["settings"])


def provisioning_base(row: SystemSettings, request: Request) -> str:
    """`integrations.public_base_url` → aks holda so'rov sxemasi + (`X-Forwarded-Host` | `Host`)."""
    base = str((row.integrations or {}).get("public_base_url") or "").rstrip("/")
    if base:
        return base
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    return f"{request.url.scheme}://{host.split(',')[0].strip()}"


def provisioning_out(row: SystemSettings, request: Request) -> ProvisioningOut:
    cfg = ps.ProvSettings.from_raw(row.provisioning)
    url = f"{provisioning_base(row, request)}/prov/{cfg.prov_token}/"
    return ProvisioningOut(
        url=url, dhcp_option_66=url, has_admin_password=bool(cfg.admin_password_enc),
        allowed_networks=list(cfg.allowed_networks), language=cfg.language, timezone=cfg.timezone,
        ntp_server=cfg.ntp_server, sip_transport=cfg.sip_transport, sip_server_host=cfg.sip_server_host,
        extra=ProvExtraOut(**cfg.extra), updated_at=row.updated_at,
    )


def _validated(field: str, check, *args):
    try:
        return check(*args)
    except ps.ProvSettingsError as exc:
        raise ApiError(422, "validation_error", exc.message, field=exc.field or field) from exc


def plain_changes(payload: UpdateProvisioningPayload) -> dict:
    """Sirsiz maydonlar → `provisioning` jsonb kalitlari (validatsiyadan o'tgan)."""
    fields = payload.model_fields_set
    changes: dict = {}
    if payload.allowed_networks is not None:
        changes["allowed_networks"] = list(_validated("allowed_networks", ps.validate_networks,
                                                      payload.allowed_networks))
    for name in ("language", "sip_transport"):
        if getattr(payload, name) is not None:
            changes[name] = getattr(payload, name)
    if payload.timezone is not None:
        changes["timezone"] = _validated("timezone", ps.validate_timezone, payload.timezone)
    if payload.ntp_server is not None:
        changes["ntp_server"] = _validated("ntp_server", ps.validate_host, "ntp_server", payload.ntp_server) \
            or ps.ProvSettings.ntp_server
    if "sip_server_host" in fields:
        changes["sip_server_host"] = _validated("sip_server_host", ps.validate_host, "sip_server_host",
                                                payload.sip_server_host)
    return changes


def extra_changes(payload: UpdateProvisioningPayload, current: dict[str, str]) -> dict[str, str] | None:
    if payload.extra is None:
        return None
    given = payload.extra.model_dump(exclude_unset=True)
    merged = dict(current)
    for vendor, value in given.items():
        merged[vendor] = _validated(f"extra.{vendor}", ps.validate_extra, vendor, value or "")
    return merged


async def _save(session: AsyncSession, user: User, row: SystemSettings, raw: dict, diff: dict) -> None:
    row.provisioning = raw
    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                       action="settings_provisioning.update", entity="settings", entity_id=str(user.tenant_id),
                       diff=diff)
    await session.commit()
    await session.refresh(row)


@router.get("", response_model=ProvisioningOut)
async def get_provisioning(request: Request, session: AsyncSession = Depends(get_session),
                           user: User = Depends(require_access)) -> ProvisioningOut:
    return provisioning_out(await get_settings_row(session, str(user.tenant_id)), request)


@router.patch("", response_model=ProvisioningOut)
async def update_provisioning(payload: UpdateProvisioningPayload, request: Request,
                              session: AsyncSession = Depends(get_session),
                              user: User = Depends(require_access)) -> ProvisioningOut:
    row = await get_settings_row(session, str(user.tenant_id))
    check_not_stale(row.updated_at, payload.updated_at)
    current = ps.ProvSettings.from_raw(row.provisioning)
    raw = current.to_raw()
    diff = plain_changes(payload)
    raw.update(diff)
    extra = extra_changes(payload, current.extra)
    if extra is not None:
        raw["extra"] = diff["extra"] = extra
    if "admin_password" in payload.model_fields_set:
        password = payload.admin_password or ""
        raw["admin_password_enc"] = await encrypt_secret(session, password) if password else None
        diff["admin_password"] = "set" if password else "cleared"
    if diff:
        await _save(session, user, row, raw, diff)
    return provisioning_out(row, request)


@router.post("/rotate-token", response_model=ProvisioningOut)
async def rotate_token(request: Request, payload: RotateTokenPayload | None = None,
                       session: AsyncSession = Depends(get_session),
                       user: User = Depends(require_access)) -> ProvisioningOut:
    row = await get_settings_row(session, str(user.tenant_id))
    if payload is not None and payload.updated_at is not None:
        check_not_stale(row.updated_at, payload.updated_at)
    raw = ps.ProvSettings.from_raw(row.provisioning).to_raw()
    raw["prov_token"] = ps.new_token()
    await _save(session, user, row, raw, {"prov_token": "rotated"})
    return provisioning_out(row, request)
