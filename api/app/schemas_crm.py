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


class BitrixConfigOut(BaseModel):
    has_webhook_url: bool
    create_lead: bool
    popup_max_delay_s: int
    default_user_id: str | None
    application_token_set: bool
    hook_token: str


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


class OneCSample(BaseModel):
    name: str
    title: str
