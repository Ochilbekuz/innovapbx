"""M4a §3 — `/devices` va `/settings/provisioning` namunalari (payload YASSI, vaqt UTC ISO)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Vendor = Literal["yealink", "grandstream", "fanvil"]
KeyType = Literal["blf", "speed_dial", "line", "park", "dnd", "none"]
DeviceStatus = Literal["never", "provisioned", "registered", "stale_config"]
Language = Literal["uz", "ru", "en"]
SipTransport = Literal["udp", "tcp", "tls"]
ProvReason = Literal["ok", "unknown_mac", "bad_token", "network_denied", "rate_limited", "legacy_binary", "not_found"]

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def single_line(value: str | None) -> str | None:
    """Config qatoriga tushadigan matn: `\\r`/`\\n` (va boshqa boshqaruv belgilari) — 422 (qator in'ektsiyasi)."""
    if value is not None and _CONTROL.search(value):
        raise ValueError("Qator ko'chirish va boshqaruv belgilari taqiqlangan")
    return value


Line = Annotated[str, AfterValidator(single_line)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ tugmalar
class DeviceKeyIn(_Strict):
    idx: int = Field(ge=1, le=60)
    type: KeyType
    value: Line = Field(default="", max_length=64)
    label: Line = Field(default="", max_length=32)


class DeviceKeyOut(BaseModel):
    idx: int
    type: KeyType
    value: str
    label: str


class PutKeysPayload(_Strict):
    keys: list[DeviceKeyIn] = Field(max_length=60)
    updated_at: datetime | None = None


# ------------------------------------------------------------------ apparat
class CreateDevicePayload(_Strict):
    mac: str = Field(min_length=12, max_length=17)
    vendor: Vendor
    model: Line = Field(min_length=1, max_length=32)
    extension_id: str
    label: Line | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1000)
    enabled: bool = True
    keys: list[DeviceKeyIn] = Field(default_factory=list, max_length=60)


class UpdateDevicePayload(_Strict):
    updated_at: datetime
    mac: str | None = Field(default=None, min_length=12, max_length=17)
    vendor: Vendor | None = None
    model: Line | None = Field(default=None, min_length=1, max_length=32)
    extension_id: str | None = None
    label: Line | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None


class DeviceExtensionOut(BaseModel):
    id: str
    number: str
    name: str


class DeviceOut(BaseModel):
    id: str
    mac: str
    vendor: Vendor
    model: str
    label: str | None
    extension: DeviceExtensionOut
    enabled: bool
    status: DeviceStatus
    provisioned_at: datetime | None
    last_seen_at: datetime | None
    last_ip: str | None
    firmware: str | None
    user_agent: str | None
    registered: bool
    keys_count: int
    keys: list[DeviceKeyOut]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DeviceList(BaseModel):
    items: list[DeviceOut]


class DeviceItem(BaseModel):
    item: DeviceOut


class DeviceConfigOut(BaseModel):
    filename: str
    content_type: str
    content: str


class ResyncResult(BaseModel):
    ok: bool
    endpoint: str


# ------------------------------------------------------------------ topilganlar / modellar / jurnal
class DiscoveredOut(BaseModel):
    mac: str
    vendor: Vendor | None
    model: str | None
    ip: str | None
    user_agent: str | None
    firmware: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    requests: int
    supported: bool


class DiscoveredList(BaseModel):
    items: list[DiscoveredOut]


class AssignDiscoveredPayload(_Strict):
    extension_id: str
    model: Line | None = Field(default=None, min_length=1, max_length=32)
    vendor: Vendor | None = None
    label: Line | None = Field(default=None, max_length=64)


class PhoneModelOut(BaseModel):
    vendor: Vendor
    model: str
    keys: int
    family: str


class PhoneModelList(BaseModel):
    items: list[PhoneModelOut]


class ProvisionRequestOut(BaseModel):
    id: int
    at: datetime
    ip: str | None
    mac: str | None
    vendor: str | None
    path: str
    status_code: int
    reason: ProvReason
    user_agent: str | None


class ProvisionRequestList(BaseModel):
    items: list[ProvisionRequestOut]


# ------------------------------------------------------------------ sozlamalar
class ProvExtraIn(_Strict):
    yealink: str | None = Field(default=None, max_length=20000)
    grandstream: str | None = Field(default=None, max_length=20000)
    fanvil: str | None = Field(default=None, max_length=20000)


class ProvExtraOut(BaseModel):
    yealink: str
    grandstream: str
    fanvil: str


class ProvisioningOut(BaseModel):
    url: str
    dhcp_option_66: str
    has_admin_password: bool
    allowed_networks: list[str]
    language: Language
    timezone: str
    ntp_server: str
    sip_transport: SipTransport
    sip_server_host: str | None
    extra: ProvExtraOut
    updated_at: datetime


class UpdateProvisioningPayload(_Strict):
    updated_at: datetime
    allowed_networks: list[str] | None = None
    language: Language | None = None
    timezone: Line | None = Field(default=None, max_length=64)
    ntp_server: Line | None = Field(default=None, max_length=253)
    sip_transport: SipTransport | None = None
    sip_server_host: Line | None = Field(default=None, max_length=253)
    admin_password: Line | None = Field(default=None, max_length=64)
    extra: ProvExtraIn | None = None


class RotateTokenPayload(_Strict):
    updated_at: datetime | None = None
