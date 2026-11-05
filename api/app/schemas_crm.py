"""M3b §5 — CRM (Bitrix24 / amoCRM) admin sozlamalari va 1C namunalari (`web/src/api/types.ts` bilan aynan)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CrmProvider = Literal["bitrix24", "amocrm"]
CRM_USER_ID_PATTERN = r"^[0-9]{1,20}$"


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


class CrmStatusOut(BaseModel):
    state: Literal["ok", "error", "disabled"]
    last_ok_at: datetime | None
    last_error: str | None
    unmapped_extensions: list[str]


class CrmUserMapEntryOut(BaseModel):
    extension: str
    crm_user_id: str | None
    crm_user_name: str | None
    source: Literal["auto", "manual"]


class UnknownInnerOut(BaseModel):
    user_id: str
    user_name: str
    inner_phone: str


class SyncConflictOut(BaseModel):
    inner_phone: str
    user_names: list[str]


class CrmSyncReportOut(BaseModel):
    last_at: datetime | None
    users_total: int
    mapped: int
    unknown_inner: list[UnknownInnerOut]
    conflicts: list[SyncConflictOut]


class BitrixConfigOut(BaseModel):
    has_webhook_url: bool
    create_lead: bool
    popup_max_delay_s: int
    default_user_id: str | None
    application_token_set: bool
    hook_token: str
    # M-CRM §1/§2/§3 — InformUnity «CRM manzili» + yozuv yuklash + foydalanuvchi sinxroni.
    route_to_responsible: bool
    responsible_ring_s: int
    set_caller_name: bool
    upload_records: bool
    auto_sync_users: bool
    portal_host: str | None
    portal_cloud: bool
    sync: CrmSyncReportOut | None = None
    # Bitrix OAuth (bitrix-oauth-shartnoma.md §2/§3) — vebhuk rejimida hammasi `None`/`False`.
    auth_mode: Literal["oauth", "webhook"] | None = None
    domain: str | None = None
    member_id: str | None = None
    connected: bool = False


class AmoConfigOut(BaseModel):
    base_url: str
    token_set: bool
    unsorted_for_unknown: bool
    default_user_id: str | None


class CrmConfigResult(BaseModel):
    enabled: bool
    config: BitrixConfigOut | AmoConfigOut
    status: CrmStatusOut
    user_map: list[CrmUserMapEntryOut]
    updated_at: datetime


class _CrmPayload(BaseModel):
    enabled: bool
    default_user_id: str | None = Field(default=None, pattern=CRM_USER_ID_PATTERN)
    updated_at: datetime

    @field_validator("default_user_id", mode="before")
    @classmethod
    def _blank_user(cls, value: object) -> object:
        return _blank_to_none(value)


class UpdateBitrixPayload(_CrmPayload):
    """`webhook_url`/`application_token` — sir: berilmasa (yoki bo'sh) eskisi saqlanadi."""
    webhook_url: str | None = Field(default=None, max_length=500)
    create_lead: bool = True
    popup_max_delay_s: int = Field(default=20, ge=0, le=600)
    application_token: str | None = Field(default=None, max_length=200)
    route_to_responsible: bool = False
    responsible_ring_s: int = Field(default=20, ge=5, le=120)
    set_caller_name: bool = True
    upload_records: bool = True
    auto_sync_users: bool = True


class UpdateAmoPayload(_CrmPayload):
    """`token` — sir: berilmasa (yoki bo'sh) eskisi saqlanadi."""
    base_url: str = Field(default="", max_length=300)
    token: str | None = Field(default=None, max_length=4000)
    unsorted_for_unknown: bool = True


class CrmUserMapEntryIn(BaseModel):
    extension: str = Field(pattern=r"^[0-9*#]{1,16}$")
    crm_user_id: str | None = Field(default=None, pattern=CRM_USER_ID_PATTERN)

    @field_validator("crm_user_id", mode="before")
    @classmethod
    def _blank_user(cls, value: object) -> object:
        return _blank_to_none(value)


class UpdateCrmUserMapPayload(BaseModel):
    entries: list[CrmUserMapEntryIn] = Field(max_length=1000)


class CrmTestResult(BaseModel):
    ok: bool
    message: str
    users_loaded: int | None


class CrmUserItem(BaseModel):
    id: str
    name: str
    inner_phone: str | None


class CrmUsersOut(BaseModel):
    items: list[CrmUserItem]


class OneCSample(BaseModel):
    name: str
    title: str


# ------------------------------------------------------------ Bitrix OAuth (bitrix-oauth-shartnoma.md §2)
class BitrixConnectIn(BaseModel):
    domain: str = Field(min_length=1, max_length=200)


class BitrixConnectOut(BaseModel):
    authorize_url: str


class BitrixSetupOut(BaseModel):
    lines: int
    default_line: bool
    event_bound: bool
    users_synced: int
    warnings: list[str]


class BitrixSetupResultOut(BaseModel):
    """`POST .../bitrix24/setup` javobi (shartnoma §2: `{setup:{...}}`)."""
    setup: BitrixSetupOut


class BitrixConnectPollOut(BaseModel):
    status: Literal["pending", "error", "connected"]
    code: str | None = None
    message: str | None = None
    setup: BitrixSetupOut | None = None


class BitrixDisconnectOut(BaseModel):
    ok: bool


class BitrixLicenseOut(BaseModel):
    connected: bool
    license: dict | None = None
    error: str | None = None
