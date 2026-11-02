"""Pydantic modellari — M2c §1 (sozlamalar), §3 (toll-fraud), §4 (ogohlantirishlar).
Umumiy `ApplyResult`/`Paged` kabi modellar `app/schemas.py`dan qayta ishlatiladi (DRY)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas import ApplyResult


class SipGuardOut(BaseModel):
    enabled: bool
    max_failures: int
    window_s: int
    ban_s: int
    trusted_nets: list[str]
    trust_lan: bool = True


class TollFraudOut(BaseModel):
    enabled: bool
    max_concurrent_outbound: int
    ext_max_per_hour: int
    ext_international_per_day: int


class SecuritySettingsOut(BaseModel):
    sip_guard: SipGuardOut
    toll_fraud: TollFraudOut
    updated_at: datetime


class UpdateSipGuardItem(BaseModel):
    enabled: bool | None = None
    max_failures: int | None = None
    window_s: int | None = None
    ban_s: int | None = None
    trusted_nets: list[str] | None = None
    trust_lan: bool | None = None


class UpdateTollFraudItem(BaseModel):
    enabled: bool | None = None
    max_concurrent_outbound: int | None = None
    ext_max_per_hour: int | None = None
    ext_international_per_day: int | None = None


class UpdateSecuritySettingsPayload(BaseModel):
    sip_guard: UpdateSipGuardItem | None = None
    toll_fraud: UpdateTollFraudItem | None = None
    updated_at: datetime


class SecuritySettingsMutated(BaseModel):
    item: SecuritySettingsOut
    apply: ApplyResult


class SecurityEventOut(BaseModel):
    id: int
    at: datetime
    kind: str
    ip: str | None
    extension: str | None
    details: dict[str, Any]
    # M3a §0: `ws` — WebRTC (nginx) hodisasi (`ws_auth_failed`); eski hodisalar null.
    transport: str | None = None


class SecurityEventList(BaseModel):
    items: list[SecurityEventOut]


class TollBlockOut(BaseModel):
    extension_id: str
    number: str
    name: str
    blocked_at: datetime
    reason: str | None


class TollBlockList(BaseModel):
    items: list[TollBlockOut]


class TollUnblockItem(BaseModel):
    extension_id: str
    number: str


class TollUnblockResult(BaseModel):
    item: TollUnblockItem


class AlertSettingsOut(BaseModel):
    chat_ids: list[str]
    dedup_s: int
    events: dict[str, bool]
    has_telegram_token: bool
    updated_at: datetime


class UpdateAlertSettingsPayload(BaseModel):
    chat_ids: list[str] | None = None
    dedup_s: int | None = None
    events: dict[str, bool] | None = None
    updated_at: datetime


class AlertTestResult(BaseModel):
    sent: int


class AlertLogOut(BaseModel):
    id: int
    at: datetime
    kind: str
    key: str
    text: str
    status: str
    error: str | None
    sent_at: datetime | None


class AlertLogList(BaseModel):
    items: list[AlertLogOut]


# ------------------------------------------------------------ M2c §2 — ban'lar/statistika


class IpBanOut(BaseModel):
    id: str
    ip: str
    reason: str
    failures: int
    note: str | None
    created_at: datetime
    expires_at: datetime | None
    created_by: str | None


class IpBanList(BaseModel):
    items: list[IpBanOut]


class CreateIpBanPayload(BaseModel):
    ip: str
    note: str | None = None
    ban_s: int | None = None


class CreateIpBanResult(BaseModel):
    item: IpBanOut
    apply: ApplyResult


class DeleteIpBanResult(BaseModel):
    apply: ApplyResult


class StatsHourOut(BaseModel):
    hour: datetime
    failures: int
    blocked: int


class StatsTopIpOut(BaseModel):
    ip: str
    failures: int
    last_at: datetime
    banned: bool


class StatsTotalsOut(BaseModel):
    failures: int
    blocked: int
    bans_active: int
    bans_period: int


class SecurityStatsOut(BaseModel):
    hours: list[StatsHourOut]
    top_ips: list[StatsTopIpOut]
    totals: StatsTotalsOut
