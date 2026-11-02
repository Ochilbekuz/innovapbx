"""M2a §5 — qora ro'yxat sxemalari (m2a-contract.md)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BlacklistEntryOut(BaseModel):
    number: str
    reason: str | None
    created_at: datetime


class BlacklistList(BaseModel):
    items: list[BlacklistEntryOut]


class CreateBlacklistPayload(BaseModel):
    number: str
    reason: str | None = None


class BlacklistCreated(BaseModel):
    item: BlacklistEntryOut
