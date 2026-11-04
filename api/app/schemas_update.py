"""Pydantic modellari — m11-update-contract.md bo'lim 4 («Paneldan yangilash»)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UpdateState = Literal["idle", "checking", "updating", "done", "failed"]
UpdatePhase = Literal["backup", "code", "install"]
UpdatePending = Literal["check", "update"]
UpdateError = Literal[
    "no_source", "fetch_failed", "git_dirty", "backup_failed",
    "install_failed", "interrupted", "bad_request",
]


class ChangelogEntryOut(BaseModel):
    version: str
    date: str | None
    body: str


class SystemUpdateOut(BaseModel):
    agent: bool
    current: str | None
    latest: str | None
    available: bool
    state: UpdateState
    phase: UpdatePhase | None
    pending: UpdatePending | None
    checked_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error: UpdateError | None
    backup: str | None
    changelog: list[ChangelogEntryOut]


class SystemUpdateStartIn(BaseModel):
    # m11-update-contract.md bo'lim 4: versiya formati.
    version: str = Field(pattern=r"^[0-9A-Za-z._-]{1,32}$")


class SystemUpdateLogOut(BaseModel):
    offset: int
    size: int
    text: str
