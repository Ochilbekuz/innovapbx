"""M2a §4 — konferensiya sxemalari (m2a-contract.md). PIN hech qachon ochiq
javobda qaytmaydi — faqat `has_pin`/`has_admin_pin` (xuddi `VoicemailBox` kabi)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas import ApplyResult

_PIN_PATTERN = r"^[0-9]{4,8}$"


class ConferenceLive(BaseModel):
    members: int


class ConferenceOut(BaseModel):
    id: str
    name: str
    number: str | None
    has_pin: bool
    has_admin_pin: bool
    record: bool
    max_members: int | None
    target_id: str
    updated_at: datetime
    live: ConferenceLive


class CreateConferencePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    pin: str | None = Field(default=None, pattern=_PIN_PATTERN)
    admin_pin: str | None = Field(default=None, pattern=_PIN_PATTERN)
    record: bool = False
    max_members: int | None = Field(default=None, ge=2, le=100)


class UpdateConferencePayload(BaseModel):
    name: str | None = None
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    pin: str | None = Field(default=None, pattern=_PIN_PATTERN)
    admin_pin: str | None = Field(default=None, pattern=_PIN_PATTERN)
    record: bool | None = None
    max_members: int | None = Field(default=None, ge=2, le=100)
    updated_at: datetime


class ConferenceMutated(BaseModel):
    item: ConferenceOut
    apply: ApplyResult
