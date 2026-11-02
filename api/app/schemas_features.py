"""M2a §2–§3 — xususiyat kodlari va park ro'yxati sxemalari (m2a-contract.md).
`schemas.py` dan alohida: §4/§5 (konferensiya, qora ro'yxat) boshqa agent tomonidan qo'shiladi."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas import ApplyResult


class FeatureCodeOut(BaseModel):
    feature: str
    code: str
    default_code: str
    enabled: bool


class FeatureCodeList(BaseModel):
    items: list[FeatureCodeOut]


class UpdateFeatureCodePayload(BaseModel):
    # Format router'da tekshiriladi — 422 `bad_code` (`field="code"`), kontrakt xato kodi bilan.
    code: str | None = None
    enabled: bool | None = None


class FeatureCodeMutated(BaseModel):
    item: FeatureCodeOut
    apply: ApplyResult


class ParkedCallOut(BaseModel):
    slot: str
    callerid: str
    parked_by: str
    since: str


class ParkingStatusOut(BaseModel):
    lot: str
    slots: str
    timeout_s: int
    parked: list[ParkedCallOut]
