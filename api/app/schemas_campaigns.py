"""M6 kampaniyalar sxemalari (m6-contract.md §2)."""
from __future__ import annotations

from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CampaignMode = Literal["message", "connect"]
CampaignStatus = Literal["draft", "running", "paused", "completed", "stopped"]
ContactStatus = Literal["pending", "dialing", "retry", "done", "failed", "skipped"]


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class CampaignFields(BaseModel):
    """To'liq (birlashtirilgan) kampaniya sozlamasi — POST va PATCH natijasi shu bilan tekshiriladi."""
    name: str = Field(min_length=1, max_length=80)
    mode: CampaignMode
    audio_id: str | None = None
    target_number: str | None = Field(default=None, pattern=r"^[0-9]{2,15}$")
    dtmf_connect: bool = False
    dtmf_optout: bool = False
    callerid: str | None = Field(default=None, pattern=r"^[0-9]{3,15}$")
    max_concurrent: int = Field(default=2, ge=1, le=30)
    max_attempts: int = Field(default=3, ge=1, le=5)
    retry_delay_s: int = Field(default=600, ge=60, le=86400)
    ring_seconds: int = Field(default=25, ge=10, le=30)
    window_start: time = time(9, 0)
    window_end: time = time(20, 0)
    days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6], min_length=1, max_length=7)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("bo'sh nom")
        return value

    @field_validator("audio_id", "target_number", "callerid", mode="before")
    @classmethod
    def _blank(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class CreateCampaignPayload(CampaignFields):
    pass


class UpdateCampaignPayload(BaseModel):
    updated_at: datetime
    name: str | None = None
    mode: CampaignMode | None = None
    audio_id: str | None = None
    target_number: str | None = None
    dtmf_connect: bool | None = None
    dtmf_optout: bool | None = None
    callerid: str | None = None
    max_concurrent: int | None = None
    max_attempts: int | None = None
    retry_delay_s: int | None = None
    ring_seconds: int | None = None
    window_start: time | None = None
    window_end: time | None = None
    days: list[int] | None = None


class CampaignStats(BaseModel):
    total: int = 0
    pending: int = 0
    dialing: int = 0
    retry: int = 0
    done: int = 0
    failed: int = 0
    skipped: int = 0
    connected: int = 0
    optout: int = 0


class CampaignOut(CampaignFields):
    id: str
    status: CampaignStatus
    audio_name: str | None = None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    stats: CampaignStats


class CampaignList(BaseModel):
    items: list[CampaignOut]


class CampaignMutated(BaseModel):
    item: CampaignOut


class ImportContactsPayload(BaseModel):
    csv: str = Field(max_length=1_000_000)
    replace: bool = False


class ImportInvalidRow(BaseModel):
    line: int
    value: str


class ImportContactsResult(BaseModel):
    added: int
    duplicates: int
    skipped: int
    invalid_count: int
    invalid: list[ImportInvalidRow]
    item: CampaignOut


class ContactOut(BaseModel):
    id: int
    number: str
    name: str | None
    status: ContactStatus
    result: str | None
    attempts: int
    billsec: int | None
    key: str | None
    next_attempt_at: datetime | None
    last_attempt_at: datetime | None


class ContactList(BaseModel):
    items: list[ContactOut]
    total: int
