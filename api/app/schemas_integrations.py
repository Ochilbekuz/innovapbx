"""M3b — integratsiyalar (webhook, API kalit, yetkazish jurnali), yozuv/integratsiya sozlamalari, ochiq API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WebhookEvent = Literal["call.ringing", "call.answered", "call.ended"]
DeliveryStatus = Literal["pending", "delivered", "dead"]
ApiKeyScope = Literal["calls:read", "recordings:read", "calls:originate", "extensions:read"]


# ------------------------------------------------------------ webhook'lar
class WebhookOut(BaseModel):
    id: str
    name: str
    url: str
    events: list[str]
    include_internal: bool
    enabled: bool
    has_secret: bool
    disabled_reason: str | None
    failing_since: datetime | None
    last_success_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateWebhookPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2000)
    events: list[WebhookEvent] = Field(min_length=1)
    include_internal: bool = False
    enabled: bool = True


class UpdateWebhookPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    events: list[WebhookEvent] | None = Field(default=None, min_length=1)
    include_internal: bool | None = None
    enabled: bool | None = None
    updated_at: datetime


class WebhookCreated(BaseModel):
    item: WebhookOut
    secret: str


class WebhookMutated(BaseModel):
    item: WebhookOut


class WebhookSecret(BaseModel):
    secret: str


class WebhookTestResult(BaseModel):
    queued: bool
    delivery_id: str | None


class DeliveryOut(BaseModel):
    id: str
    event_id: str
    event_type: str
    call_id: str | None
    status: DeliveryStatus
    attempts: int
    next_attempt_at: datetime | None
    last_attempt_at: datetime | None
    last_status_code: int | None
    last_error: str | None
    response_body: str | None
    delivered_at: datetime | None
    created_at: datetime
    # S15 (web) nomlari — xuddi shu qiymatlar.
    http_status: int | None
    next_retry_at: datetime | None


# ------------------------------------------------------------ API kalitlar
class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class CreateApiKeyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[ApiKeyScope] = Field(min_length=1)
    expires_at: datetime | None = None


class ApiKeyCreated(BaseModel):
    item: ApiKeyOut
    key: str


# ------------------------------------------------------------ sozlamalar
class IntegrationSettingsOut(BaseModel):
    public_base_url: str
    recording_link_ttl_s: int
    updated_at: datetime


class UpdateIntegrationSettingsPayload(BaseModel):
    public_base_url: str | None = Field(default=None, max_length=500)
    recording_link_ttl_s: int | None = Field(default=None, ge=60, le=90 * 24 * 3600)
    updated_at: datetime


class RecordingSettingsOut(BaseModel):
    external_only: bool
    retention_days: int
    format: str
    updated_at: datetime


class UpdateRecordingSettingsPayload(BaseModel):
    external_only: bool | None = None
    retention_days: int | None = Field(default=None, ge=7, le=3650)
    updated_at: datetime


# ------------------------------------------------------------ ochiq API
class PublicExtensionOut(BaseModel):
    number: str
    name: str
    enabled: bool
    status: str


class OriginatePayload(BaseModel):
    extension: str = Field(min_length=1, max_length=10)
    to: str = Field(min_length=1, max_length=200)  # ≤ 32 va belgilar — router (422 `invalid_number`)
    external_id: str | None = Field(default=None, max_length=64)


class OriginateAccepted(BaseModel):
    request_id: str
