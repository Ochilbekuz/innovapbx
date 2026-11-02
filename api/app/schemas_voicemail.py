"""M1c §2 — ovozli pochta va bildirishnoma sozlamalari sxemalari
(m1c-contract.md). `schemas.py` dan alohida: u fayl boshqa M1c ishlari bilan
parallel tahrirlanadi."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas import ApplyResult

_PIN = r"^\d{4,8}$"
_MAILBOX = r"^[0-9]{2,10}$"
_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_CHAT_ID = r"^(-?[0-9]{1,20}|@[A-Za-z0-9_]{5,32})$"

SmtpTls = Literal["none", "starttls", "tls"]
NotifyChannel = Literal["email", "telegram"]


class VoicemailExtensionRef(BaseModel):
    id: str
    number: str
    name: str


class VoicemailGreetingRef(BaseModel):
    id: str
    name: str


class VoicemailCounts(BaseModel):
    new: int
    old: int


class VoicemailBoxOut(BaseModel):
    id: str
    mailbox: str
    extension: VoicemailExtensionRef | None
    email: str | None
    email_notify: bool
    telegram_notify: bool
    telegram_chat_id: str | None
    attach_audio: bool
    greeting: VoicemailGreetingRef | None
    has_pin: bool
    counts: VoicemailCounts
    updated_at: datetime


class _BoxFields(BaseModel):
    email: str | None = Field(default=None, pattern=_EMAIL, max_length=254)
    email_notify: bool | None = None
    telegram_notify: bool | None = None
    telegram_chat_id: str | None = Field(default=None, pattern=_CHAT_ID)
    attach_audio: bool | None = None
    greeting_audio_id: str | None = None


class CreateVoicemailBoxPayload(_BoxFields):
    extension_id: str | None = None
    mailbox: str | None = Field(default=None, pattern=_MAILBOX)
    pin: str = Field(pattern=_PIN)

    @model_validator(mode="after")
    def _one_owner(self) -> CreateVoicemailBoxPayload:
        if (self.extension_id is None) == (self.mailbox is None):
            raise ValueError("extension_id yoki mailbox — aynan bittasi berilishi kerak")
        return self


class UpdateVoicemailBoxPayload(_BoxFields):
    """`null` qiymat va BERILMAGAN maydon farqlanadi (`model_fields_set`):
    `email: null` — tozalash, maydon yo'q — o'zgarmaydi."""
    pin: str | None = Field(default=None, pattern=_PIN)
    updated_at: datetime


class VoicemailBoxMutated(BaseModel):
    item: VoicemailBoxOut
    apply: ApplyResult


class VoicemailMessageOut(BaseModel):
    id: str
    folder: Literal["inbox", "old"]
    callerid: str
    duration_s: int
    received_at: datetime
    heard: bool


class NotifySettingsOut(BaseModel):
    smtp_host: str | None
    smtp_port: int
    smtp_tls: SmtpTls
    smtp_user: str | None
    has_smtp_password: bool
    from_email: str | None
    has_telegram_token: bool
    telegram_api_base: str
    updated_at: datetime | None


class UpdateNotifySettingsPayload(BaseModel):
    """Parol/token: berilmasa o'zgarmaydi, `""` — o'chiriladi."""
    smtp_host: str | None = Field(default=None, max_length=253)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_tls: SmtpTls | None = None
    smtp_user: str | None = Field(default=None, max_length=254)
    smtp_password: str | None = Field(default=None, max_length=512)
    from_email: str | None = Field(default=None, pattern=_EMAIL, max_length=254)
    telegram_token: str | None = Field(default=None, max_length=256)
    telegram_api_base: str | None = Field(default=None, pattern=r"^https?://[^\s]+$", max_length=256)
    updated_at: datetime | None = None


class NotifyTestPayload(BaseModel):
    channel: NotifyChannel
    to: str = Field(min_length=1, max_length=254)


class NotifyTestResult(BaseModel):
    ok: bool
