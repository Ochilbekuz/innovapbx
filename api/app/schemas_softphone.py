"""M3a §2 — brauzer softfoni (`GET /api/v1/me/softphone`) javob modeli."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SoftphoneSip(BaseModel):
    uri: str
    auth_user: str
    password: str
    realm: str


class SoftphoneOut(BaseModel):
    number: str
    display_name: str
    ws_path: str
    ticket: str
    ticket_expires_at: datetime
    sip: SoftphoneSip
    # STUN/TURN — M3a'da bo'sh (shartnoma: sozlamalar UI keyin).
    ice_servers: list[dict] = Field(default_factory=list)
