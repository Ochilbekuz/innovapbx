"""M5b (replica/m5b-contract.md) — Follow Me va QR orqali sozlash sxemalari.
Frontend `web/src/api/types.ts` (`FollowMe`, `QrProvisioning`) bilan AYNAN mos."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FollowMeStrategy = Literal["ring_all", "sequential"]
FOLLOW_ME_MAX_NUMBERS = 6
FOLLOW_ME_RING_MIN = 5
FOLLOW_ME_RING_MAX = 120


class FollowMe(BaseModel):
    enabled: bool = False
    numbers: list[str] = Field(default_factory=list, max_length=FOLLOW_ME_MAX_NUMBERS)
    strategy: FollowMeStrategy = "ring_all"
    include_extension: bool = True
    ring_seconds: int = Field(default=20, ge=FOLLOW_ME_RING_MIN, le=FOLLOW_ME_RING_MAX)
    confirm: bool = True


def follow_me_default() -> dict:
    """Yangi ichki raqam / import uchun — har safar yangi dict (ro'yxat umumiy bo'lmasin)."""
    return FollowMe().model_dump()


class FollowMePayload(FollowMe):
    """PUT: to'liq obyekt; `updated_at` — optimistik qulf (ixtiyoriy, `check_not_stale`)."""
    updated_at: datetime | None = None


class FollowMeOut(BaseModel):
    extension_id: str
    number: str
    follow_me: FollowMe
    updated_at: datetime


class QrProvisioningOut(BaseModel):
    url: str
    expires_at: datetime
    transport: Literal["udp", "tcp", "tls"]
