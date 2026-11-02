"""M3b §1/§2 — `GET/PATCH /settings/integrations` (yozuv havolalari uchun ochiq manzil, TTL) va
`GET/PATCH /settings/recording` (saqlash muddati, `external_only`). `settings_alerts` qolipi:
`updated_at` bilan optimistik qulf (409), audit, dialplan apply SHART EMAS (realtime view)."""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.api.v1.settings import get_settings_row
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import SystemSettings, User
from app.schemas_integrations import (
    IntegrationSettingsOut,
    RecordingSettingsOut,
    UpdateIntegrationSettingsPayload,
    UpdateRecordingSettingsPayload,
)
from app.services.audit import record_audit
from app.services.recordings import DEFAULT_LINK_TTL_S

router = APIRouter(prefix="/settings", tags=["settings"])


def normalize_base_url(raw: str | None) -> str:
    """Bo'sh → "" (havola `null`). Aks holda `http(s)://host[:port][/yo'l]`, so'rov/fragmentsiz, oxirgi `/`siz."""
    value = (raw or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment \
            or parts.username or parts.password:
        raise ApiError(422, "bad_value", "Manzil http(s)://host[:port] ko'rinishida bo'lsin", field="public_base_url")
    return value.rstrip("/")


def integration_settings_out(row: SystemSettings) -> IntegrationSettingsOut:
    cfg = row.integrations or {}
    return IntegrationSettingsOut(public_base_url=str(cfg.get("public_base_url") or ""),
                                  recording_link_ttl_s=int(cfg.get("recording_link_ttl_s") or DEFAULT_LINK_TTL_S),
                                  updated_at=row.updated_at)


def recording_settings_out(row: SystemSettings) -> RecordingSettingsOut:
    cfg = row.recording or {}
    return RecordingSettingsOut(external_only=bool(cfg.get("external_only")), format=str(cfg.get("format") or "wav"),
                                retention_days=int(row.recording_retention_days or 365), updated_at=row.updated_at)


async def _save(session: AsyncSession, user: User, row: SystemSettings, action: str, diff: dict) -> None:
    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                       entity="settings", entity_id=str(user.tenant_id), diff=diff)
    await session.commit()
    await session.refresh(row)


@router.get("/integrations", response_model=IntegrationSettingsOut)
async def get_integration_settings(session: AsyncSession = Depends(get_session),
                                   user: User = Depends(require_admin)) -> IntegrationSettingsOut:
    return integration_settings_out(await get_settings_row(session, str(user.tenant_id)))


@router.patch("/integrations", response_model=IntegrationSettingsOut)
async def update_integration_settings(payload: UpdateIntegrationSettingsPayload,
                                      session: AsyncSession = Depends(get_session),
                                      user: User = Depends(require_admin)) -> IntegrationSettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    check_not_stale(row.updated_at, payload.updated_at)
    changes: dict = {}
    if "public_base_url" in payload.model_fields_set:
        changes["public_base_url"] = normalize_base_url(payload.public_base_url)
    if payload.recording_link_ttl_s is not None:
        changes["recording_link_ttl_s"] = payload.recording_link_ttl_s
    if changes:
        row.integrations = {**(row.integrations or {}), **changes}
    await _save(session, user, row, "settings_integrations.update", changes)
    return integration_settings_out(row)


@router.get("/recording", response_model=RecordingSettingsOut)
async def get_recording_settings(session: AsyncSession = Depends(get_session),
                                 user: User = Depends(require_admin)) -> RecordingSettingsOut:
    return recording_settings_out(await get_settings_row(session, str(user.tenant_id)))


@router.patch("/recording", response_model=RecordingSettingsOut)
async def update_recording_settings(payload: UpdateRecordingSettingsPayload,
                                    session: AsyncSession = Depends(get_session),
                                    user: User = Depends(require_admin)) -> RecordingSettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    check_not_stale(row.updated_at, payload.updated_at)
    changes: dict = {}
    if payload.external_only is not None:
        changes["external_only"] = payload.external_only
        row.recording = {**(row.recording or {}), "external_only": payload.external_only}
    if payload.retention_days is not None:
        changes["retention_days"] = payload.retention_days
        row.recording_retention_days = payload.retention_days
    await _save(session, user, row, "settings_recording.update", changes)
    return recording_settings_out(row)
