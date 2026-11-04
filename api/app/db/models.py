"""SQLAlchemy 2 ORM modellari — faqat M0 uchun kerakli jadvallar.

Jadval shakli `replica/schema.sql` dan (yagona manba — ustun nomi/turi u bilan
mos kelishi SHART, chunki Asterisk realtime view'lari ham xuddi shu
jadvallarni o'qiydi). Bu yerda ORM FAQAT API ishlatadigan quyi to'plam:
tenants, roles, users, refresh_tokens, audit_log, call_targets, dial_numbers,
extensions, trunks, trunk_health, inbound_routes, config_revisions, cdr.
"""
from __future__ import annotations

from datetime import date as dt_date, datetime, time as dt_time

from sqlalchemy import BigInteger, Date, LargeBinary, FetchedValue, ForeignKey, Index, Integer, String, Text, Time, cast, text
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, INET, JSONB, MACADDR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.base import Base
from app.schemas_follow_me import follow_me_default


def _uuid_pk() -> Mapped[str]:
    return mapped_column(UUID(as_uuid=False), primary_key=True,
                          server_default=text("gen_random_uuid()"))


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = _uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Tashkent")
    language: Mapped[str] = mapped_column(Text, default="uz")
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_system: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_tenant_username", "tenant_id", "username", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M10 B2 — 2FA (TOTP, RFC 6238). `totp_enabled_at` NULL = o'chirilgan.
    # `totp_last_step` — oxirgi qabul qilingan qadam (takror himoyasi).
    # `totp_recovery_hashes` — 10 ta bir martalik tiklash kodi (bcrypt hash).
    totp_enabled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    totp_recovery_hashes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                ForeignKey("roles.id", ondelete="RESTRICT"))
    # FK DBda `0001_schema.sql`da bor (on delete set null) — shu yerda ham
    # aniq yozilgan, operator portali (/me) uchun extension o'chirilsa NULL bo'ladi.
    extension_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="SET NULL"), nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL = tenant tili
    is_active: Mapped[bool] = mapped_column(default=True)
    must_change_password: Mapped[bool] = mapped_column(default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    role: Mapped[Role] = relationship(lazy="joined")
    tenant: Mapped[Tenant] = relationship(lazy="joined")
    extension: Mapped[Extension | None] = relationship(lazy="joined", foreign_keys=[extension_id])


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(Text)
    # `text`, QAT'IY `UUID` EMAS: entity_id istalgan entitya id'siga ishora
    # qilishi mumkin, ba'zilari UUID emas (masalan `config_revisions.id`
    # bigint) -- UUID ustunga noUUID qiymat yozish asyncpg DataError/500
    # bilan yiqilardi (restore ishlab chiqarishda umuman ishlamasligi
    # sababi edi, m1b-proof.sh ssenariy 6 orqali topilgan, 2026-10-28).
    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CallTarget(Base):
    __tablename__ = "call_targets"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DialNumber(Base):
    __tablename__ = "dial_numbers"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    number: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"))


class Extension(Base):
    __tablename__ = "extensions"
    __table_args__ = (Index("ix_extensions_tenant_number", "tenant_id", "number", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    number: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    callerid_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    outbound_callerid: Mapped[str | None] = mapped_column(Text, nullable=True)
    sip_password_enc: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    max_contacts: Mapped[int] = mapped_column(Integer, default=3)
    codecs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=lambda: ["ulaw", "alaw", "g722", "opus"])
    webrtc: Mapped[bool] = mapped_column(default=False)
    # M3c §1 — `recording` (nomi o'zgarmaydi, FreePBX import/public/fake API) KIRUVCHI
    # siyosat; `recording_out` — CHIQUVCHI (0028, boshlang'ich qiymat = `recording`).
    recording: Mapped[str] = mapped_column(Text, default="always")
    recording_out: Mapped[str] = mapped_column(Text, default="always")
    ring_seconds: Mapped[int] = mapped_column(Integer, default=25)
    dnd: Mapped[bool] = mapped_column(default=False)
    forward_always: Mapped[str | None] = mapped_column(Text, nullable=True)
    forward_busy: Mapped[str | None] = mapped_column(Text, nullable=True)
    pickup_group: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_answer_target_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"), nullable=True)
    follow_me: Mapped[dict] = mapped_column(
        JSONB, default=follow_me_default)
    outbound_allowed: Mapped[bool] = mapped_column(default=True)
    # M2c §3 toll-fraud — admin `outbound_allowed`dan ALOHIDA (avtomatik blok).
    toll_blocked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    toll_block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    toll_unblocked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    department: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M9 A5 — o'chirilsa va holat INUSE/BUSY/RINGINUSE bo'lsa, ikkinchi kiruvchi
    # qo'ng'iroq band deb yuboriladi (`dialplan_features.py::_call_waiting_check_lines`).
    call_waiting: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class FeatureCodeDefault(Base):
    """M2a §2: funksiya kodlarining standarti (seed/reset/`default_code` manbai)."""
    __tablename__ = "feature_code_defaults"

    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class FeatureCode(Base):
    """M2a §2: tenant funksiya kodi (masalan `dnd_toggle` → `*76`)."""
    __tablename__ = "feature_codes"

    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                           ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (Index("ix_audio_files_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, default="uz")
    source: Mapped[str] = mapped_column(Text)
    tts_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MohClass(Base):
    __tablename__ = "moh_classes"
    __table_args__ = (Index("ix_moh_classes_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    shuffle: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    files: Mapped[list["MohClassFile"]] = relationship(
        back_populates="moh_class", cascade="all, delete-orphan", order_by="MohClassFile.position")


class MohClassFile(Base):
    __tablename__ = "moh_class_files"

    moh_class_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("moh_classes.id", ondelete="CASCADE"), primary_key=True)
    audio_file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="RESTRICT"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)

    moh_class: Mapped[MohClass] = relationship(back_populates="files")
    audio_file: Mapped["AudioFile"] = relationship(lazy="joined")


class TimeGroup(Base):
    __tablename__ = "time_groups"
    __table_args__ = (Index("ix_time_groups_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    ranges: Mapped[list["TimeRange"]] = relationship(
        back_populates="time_group", cascade="all, delete-orphan", order_by="TimeRange.id")


class TimeRange(Base):
    __tablename__ = "time_ranges"

    id: Mapped[str] = _uuid_pk()
    time_group_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("time_groups.id", ondelete="CASCADE"))
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    start_time: Mapped[dt_time] = mapped_column(Time)
    end_time: Mapped[dt_time] = mapped_column(Time)

    time_group: Mapped[TimeGroup] = relationship(back_populates="ranges")


class Holiday(Base):
    __tablename__ = "holidays"
    __table_args__ = (Index("ix_holidays_tenant_day", "tenant_id", "day", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    day: Mapped[dt_date] = mapped_column(Date)
    recurring_yearly: Mapped[bool] = mapped_column(default=False)


class TimeCondition(Base):
    __tablename__ = "time_conditions"
    __table_args__ = (Index("ix_time_conditions_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    time_group_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("time_groups.id", ondelete="RESTRICT"))
    honor_holidays: Mapped[bool] = mapped_column(default=True)
    open_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    closed_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    override: Mapped[str] = mapped_column(Text, default="auto")
    toggle_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    time_group: Mapped[TimeGroup] = relationship(lazy="joined")


class Announcement(Base):
    """Xabar o'ynab, keyin boshqa manzilga o'tkazadi (`alembic/sql/0001_schema.sql`
    dagi jadval — M5a'gacha ORM klassi yo'q edi, chunki hech bir API uni yozmagan)."""
    __tablename__ = "announcements"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    audio_file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="RESTRICT"))
    next_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    # M9 A1 (0031) — `allow_skip`: Background+WaitExten(1) (istalgan raqam ⇒ keyingi
    # manzilga o'tadi), aks holda Playback (o'tkazib bo'lmaydi). `repeat_key` — bu
    # raqam bosilsa xabar qaytadan o'ynaladi. `answer` — avval Answer() qilinsinmi.
    allow_skip: Mapped[bool] = mapped_column(default=False)
    repeat_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MiscDestination(Base):
    """M9 A2 (0031) — "Boshqa manzil": oddiy ichki terish kabi `dial`ga Goto
    qiladi (toll-fraud/PIN BYPASS qilinmaydi — `compiler.py::_misc_dest_lines`)."""
    __tablename__ = "misc_destinations"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    dial: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MiscApplication(Base):
    """M9 A2 (0031) — "Boshqa ilova": ichki raqamlar `code`ni terib `target_id`ga
    yetadi (feature kodlari/dial_numbers bilan kod to'qnashuvi — `feature_codes.py`)."""
    __tablename__ = "misc_applications"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ParkingSettings(Base):
    """M9 A3 (0031) — tenant bo'yicha YAGONA qator (`system_settings` namunasi),
    sehrgar (`POST /setup`) to'ldiradi. `##700`/`*70` shu yerdagi raqamlardan
    foydalanadi (`dialplan_features.py::ParkingSettingsData`)."""
    __tablename__ = "parking_settings"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    lot_number: Mapped[str] = mapped_column(Text, default="700")
    first_slot: Mapped[int] = mapped_column(Integer, default=701)
    slot_count: Mapped[int] = mapped_column(Integer, default=20)
    timeout_s: Mapped[int] = mapped_column(Integer, default=60)
    on_timeout: Mapped[str] = mapped_column(Text, default="origin")
    timeout_target_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="SET NULL"), nullable=True)
    moh_class_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("moh_classes.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class PageGroup(Base):
    """M9 A4 (0031) — Paging/Intercom guruhi (`Page()` ilovasi, `number`ni terish)."""
    __tablename__ = "page_groups"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    number: Mapped[str] = mapped_column(Text)
    duplex: Mapped[bool] = mapped_column(default=False)
    skip_busy: Mapped[bool] = mapped_column(default=True)
    beep: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    members: Mapped[list["PageGroupMember"]] = relationship(
        order_by="PageGroupMember.extension_id", cascade="all, delete-orphan")


class PageGroupMember(Base):
    __tablename__ = "page_group_members"

    page_group_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("page_groups.id", ondelete="CASCADE"), primary_key=True)
    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), primary_key=True)

    extension: Mapped["Extension"] = relationship()


class Ivr(Base):
    __tablename__ = "ivrs"
    __table_args__ = (Index("ix_ivrs_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    greeting_audio_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="RESTRICT"))
    invalid_audio_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="RESTRICT"), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=7)
    repeats: Mapped[int] = mapped_column(Integer, default=2)
    direct_dial: Mapped[bool] = mapped_column(default=False)
    timeout_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    invalid_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    options: Mapped[list["IvrOption"]] = relationship(
        back_populates="ivr", cascade="all, delete-orphan", order_by="IvrOption.digit")


class IvrOption(Base):
    __tablename__ = "ivr_options"

    ivr_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ivrs.id", ondelete="CASCADE"), primary_key=True)
    digit: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))

    ivr: Mapped[Ivr] = relationship(back_populates="options")


class RingGroup(Base):
    __tablename__ = "ring_groups"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    strategy: Mapped[str] = mapped_column(Text, default="ringall")
    ring_seconds: Mapped[int] = mapped_column(Integer, default=20)
    no_answer_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    callerid_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    members: Mapped[list["RingGroupMember"]] = relationship(
        back_populates="ring_group", cascade="all, delete-orphan", order_by="RingGroupMember.position")


class RingGroupMember(Base):
    __tablename__ = "ring_group_members"

    ring_group_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ring_groups.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    extension_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), nullable=True)
    external_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    ring_group: Mapped[RingGroup] = relationship(back_populates="members")
    extension: Mapped[Extension | None] = relationship(lazy="joined")


class Queue(Base):
    __tablename__ = "queues"
    __table_args__ = (Index("ix_queues_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    strategy: Mapped[str] = mapped_column(Text, default="rrmemory")
    moh_class_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("moh_classes.id", ondelete="SET NULL"), nullable=True)
    agent_ring_seconds: Mapped[int] = mapped_column(Integer, default=15)
    retry_seconds: Mapped[int] = mapped_column(Integer, default=5)
    wrapup_seconds: Mapped[int] = mapped_column(Integer, default=0)
    max_wait_seconds: Mapped[int] = mapped_column(Integer, default=300)
    max_callers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    announce_position: Mapped[bool] = mapped_column(default=True)
    announce_frequency_seconds: Mapped[int] = mapped_column(Integer, default=60)
    sla_seconds: Mapped[int] = mapped_column(Integer, default=20)
    join_empty: Mapped[bool] = mapped_column(default=False)
    record: Mapped[bool] = mapped_column(default=True)
    timeout_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    members: Mapped[list["QueueMember"]] = relationship(
        back_populates="queue", cascade="all, delete-orphan")
    moh_class: Mapped[MohClass | None] = relationship(lazy="joined")


class QueueMember(Base):
    __tablename__ = "queue_members"

    queue_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("queues.id", ondelete="CASCADE"), primary_key=True)
    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), primary_key=True)
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    # M2b §0/§1: agent holati — yagona manba shu yerda (PG), Asterisk
    # `asterisk_agent_state`/`asterisk_queue_members` view orqali o'qiydi/yozadi.
    dynamic: Mapped[bool] = mapped_column(default=False)
    logged_in: Mapped[bool] = mapped_column(default=False)
    paused: Mapped[bool] = mapped_column(default=False)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    queue: Mapped[Queue] = relationship(back_populates="members")
    extension: Mapped[Extension] = relationship(lazy="joined")


class AgentEvent(Base):
    """M2b §0/§1: har login/logout/pause/unpause — manbadan qat'i nazar
    (`queue_members_log_agent_event` trigger, 0015_m2b_agent_state.sql).
    Analitika (§5, keyingi agent) login/pauza vaqtini shundan hisoblaydi."""
    __tablename__ = "agent_events"
    __table_args__ = (
        Index("ix_agent_events_tenant_at", "tenant_id", "at"),
        Index("ix_agent_events_extension_at", "extension_id", "at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"))
    queue_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("queues.id", ondelete="CASCADE"), nullable=True)
    event: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Trunk(Base):
    __tablename__ = "trunks"
    __table_args__ = (Index("ix_trunks_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    auth_mode: Mapped[str] = mapped_column(Text)
    host: Mapped[str] = mapped_column(Text)
    port: Mapped[int] = mapped_column(Integer, default=5060)
    transport: Mapped[str] = mapped_column(Text, default="udp")
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_ips: Mapped[list[str]] = mapped_column(ARRAY(CIDR), default=list)
    codecs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=lambda: ["alaw", "ulaw"])
    max_channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outbound_callerid: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class TrunkHealth(Base):
    __tablename__ = "trunk_health"

    trunk_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trunks.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[str] = mapped_column(Text, default="unknown")
    registration: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualify_rtt_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_outbound_ok_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class InboundRoute(Base):
    __tablename__ = "inbound_routes"
    __table_args__ = (
        Index("ix_inbound_routes_tenant_did_cid", "tenant_id", "did", "callerid_pattern", unique=True),
    )

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    did: Mapped[str] = mapped_column(Text, default="")
    callerid_pattern: Mapped[str] = mapped_column(Text, default="")
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    callerid_name_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M9 B3 (0032): SIP Alert-Info (masalan, ichki qo'ng'iroq ohangi) — qiymat
    # faqat dialplan o'zgaruvchisiga qo'yiladi, sarlavhani A agent gosub'i qo'shadi.
    alert_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M9 B2 (0032): CID Lookup manbai — bo'sh/mavjud ism bo'lmasa shu manba so'raladi.
    cid_lookup_source_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("cid_lookup_sources.id", ondelete="SET NULL"), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    cid_lookup_source: Mapped["CidLookupSource | None"] = relationship()


class OutboundRoute(Base):
    __tablename__ = "outbound_routes"
    __table_args__ = (
        Index("ix_outbound_routes_tenant_name", "tenant_id", "name", unique=True),
        Index("ix_outbound_routes_tenant_priority", "tenant_id", "priority", unique=True),
    )

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer)
    callerid: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_extension_callerid: Mapped[bool] = mapped_column(default=False)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M9 B1 (0032): PIN to'plami — yagona pin_hash BILAN BIR QATORDA ishlaydi
    # (ikkisidan birortasi mos kelsa yetarli).
    pin_set_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pin_sets.id", ondelete="RESTRICT"), nullable=True)
    international: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    patterns: Mapped[list["OutboundRoutePattern"]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="OutboundRoutePattern.id")
    route_trunks: Mapped[list["OutboundRouteTrunk"]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="OutboundRouteTrunk.position")
    extension_links: Mapped[list["ExtensionOutboundRoute"]] = relationship(
        back_populates="route", cascade="all, delete-orphan")
    pin_set: Mapped["PinSet | None"] = relationship()


class OutboundRoutePattern(Base):
    __tablename__ = "outbound_route_patterns"

    id: Mapped[str] = _uuid_pk()
    route_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outbound_routes.id", ondelete="CASCADE"))
    strip_prefix: Mapped[str] = mapped_column(Text, default="")
    pattern: Mapped[str] = mapped_column(Text)
    add_prefix: Mapped[str] = mapped_column(Text, default="")
    callerid_match: Mapped[str] = mapped_column(Text, default="")

    route: Mapped[OutboundRoute] = relationship(back_populates="patterns")


class OutboundRouteTrunk(Base):
    __tablename__ = "outbound_route_trunks"

    route_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outbound_routes.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    trunk_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trunks.id", ondelete="RESTRICT"))

    route: Mapped[OutboundRoute] = relationship(back_populates="route_trunks")
    trunk: Mapped["Trunk"] = relationship(lazy="joined")


class ExtensionOutboundRoute(Base):
    __tablename__ = "extension_outbound_routes"

    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), primary_key=True)
    route_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outbound_routes.id", ondelete="CASCADE"), primary_key=True)

    route: Mapped[OutboundRoute] = relationship(back_populates="extension_links")
    extension: Mapped["Extension"] = relationship(lazy="joined")


class ConfigRevision(Base):
    __tablename__ = "config_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(Text)
    dialplan_sha256: Mapped[str] = mapped_column(Text)
    dialplan: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class SystemSettings(Base):
    """Tenant bo'yicha bitta qator — sehrgar (`POST /setup`) to'ldiradi."""
    __tablename__ = "system_settings"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    external_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    external_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_nets: Mapped[list[str]] = mapped_column(
        ARRAY(CIDR), default=lambda: ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
    sip_udp_port: Mapped[int] = mapped_column(Integer, default=5060)
    sip_tls_port: Mapped[int] = mapped_column(Integer, default=5061)
    rtp_start: Mapped[int] = mapped_column(Integer, default=10000)
    rtp_end: Mapped[int] = mapped_column(Integer, default=20000)
    recording_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    toll_fraud: Mapped[dict] = mapped_column(JSONB, default=dict)
    telegram: Mapped[dict] = mapped_column(JSONB, default=dict)
    sip_guard: Mapped[dict] = mapped_column(JSONB, default=dict)  # M2c — shakli `app/services/security_config.py`
    # M3b §1/§2 — shakli `app/services/recordings.py` / `app/services/integrations/settings.py`.
    recording: Mapped[dict] = mapped_column(JSONB, default=lambda: {"external_only": False, "format": "wav"})
    integrations: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {"public_base_url": "", "recording_link_ttl_s": 604800})
    # M4a §1 — shakli `app/services/prov_settings.py`; sukut (tasodifiy `prov_token`) bazada (0020).
    provisioning: Mapped[dict] = mapped_column(JSONB, server_default=FetchedValue())
    codecs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=lambda: ["alaw", "ulaw", "g722", "opus"])
    restart_required: Mapped[bool] = mapped_column(default=False)
    # M4b §1 — shakli `app/services/backup_settings.py`; sukut (0021) passphrase/jadval/nishonlar.
    backup: Mapped[dict] = mapped_column(JSONB, server_default=FetchedValue())
    # M10 B2 — 2FA siyosati: 'off' (sukut) / 'admins' / 'all'; DB `check` cheklovi 0034_m10b'da.
    require_2fa: Mapped[str] = mapped_column(Text, default="off")
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Backup(Base):
    """M4b §1 — `kind`: scheduled/manual/pre_restore/uploaded. `manifest` — INNOVABK1 sarlavhasi
    (sir YO'Q — parol/kalit shifrlangan arxiv ichida). `components` bo'sh bo'lishi mumkin
    (hali tekshirilmagan `uploaded` zaxira — `inspect` to'ldiradi)."""
    __tablename__ = "backups"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    components: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    step: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    copies: Mapped[list["BackupCopy"]] = relationship(
        "BackupCopy", cascade="all, delete-orphan", order_by="BackupCopy.target")


class BackupCopy(Base):
    """M4b §1 — bitta zaxira x bitta nishon (`local`/`s3`/`sftp`) — `(backup_id, target)` yagona."""
    __tablename__ = "backup_copies"

    id: Mapped[str] = _uuid_pk()
    backup_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("backups.id", ondelete="CASCADE"))
    target: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    remote_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RestoreJob(Base):
    """M4b §2 — ikki fazali tiklash jarayoni (`inspect` bu yerga yozmaydi — faqat `restore`)."""
    __tablename__ = "restore_jobs"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    backup_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("backups.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    step: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    force: Mapped[bool] = mapped_column(default=False)
    pre_restore_backup_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("backups.id", ondelete="SET NULL"), nullable=True)
    started_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Cdr(Base):
    __tablename__ = "cdr"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calldate: Mapped[datetime] = mapped_column(server_default=text("now()"))
    clid: Mapped[str | None] = mapped_column(Text, nullable=True)
    src: Mapped[str | None] = mapped_column(Text, nullable=True)
    dst: Mapped[str | None] = mapped_column(Text, nullable=True)
    dcontext: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str | None] = mapped_column(Text, nullable=True)
    dstchannel: Mapped[str | None] = mapped_column(Text, nullable=True)
    lastapp: Mapped[str | None] = mapped_column(Text, nullable=True)
    lastdata: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    billsec: Mapped[int] = mapped_column(Integer, default=0)
    disposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    amaflags: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accountcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    uniqueid: Mapped[str] = mapped_column(Text)
    linkedid: Mapped[str | None] = mapped_column(Text, nullable=True)
    userfield: Mapped[str | None] = mapped_column(Text, nullable=True)
    peeraccount: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recordingfile: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M9 B1 tuzatish (0032): PIN to'plami yorlig'i — `accountcode` (tenant kodi,
    # /calls va hisobotlar shu bo'yicha filtrlaydi) BILAN ARALASHTIRILMAYDI.
    pin_label: Mapped[str | None] = mapped_column(Text, nullable=True)


class QueueLog(Base):
    """Asterisk `app_queue` realtime yozuvi (`queue_log`, 0001_schema.sql) —
    tenant ustuni YO'Q (Asterisk o'zi yozadi); tenant ajratish `queuename`
    prefiksi (`<tenant_code>-q-<queue_uuid>`) orqali (m2b-contract.md §5)."""
    __tablename__ = "queue_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    time: Mapped[datetime] = mapped_column(server_default=text("now()"))
    callid: Mapped[str | None] = mapped_column(Text, nullable=True)
    queuename: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    event: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    data1: Mapped[str | None] = mapped_column(Text, nullable=True)
    data2: Mapped[str | None] = mapped_column(Text, nullable=True)
    data3: Mapped[str | None] = mapped_column(Text, nullable=True)
    data4: Mapped[str | None] = mapped_column(Text, nullable=True)
    data5: Mapped[str | None] = mapped_column(Text, nullable=True)


# ------------------------------------------------------------ M1c: ovozli pochta
class VoicemailBox(Base):
    """`voicemail_boxes` (0001 + 0010). `extension_id` NULL — umumiy quti.
    `pin_hash` — bcrypt; Asterisk fayliga PIN yozilmaydi (m1c-contract.md §2)."""
    __tablename__ = "voicemail_boxes"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    extension_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), unique=True, nullable=True)
    mailbox: Mapped[str] = mapped_column(Text)
    pin_hash: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_notify: Mapped[bool] = mapped_column(default=True)
    telegram_notify: Mapped[bool] = mapped_column(default=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attach_audio: Mapped[bool] = mapped_column(default=True)
    greeting_audio_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    extension: Mapped[Extension | None] = relationship(lazy="selectin")
    greeting: Mapped[AudioFile | None] = relationship(lazy="selectin")


class Conference(Base):
    """`conferences` (0001). `pin_hash`/`admin_pin_hash` — bcrypt; PIN hech qachon
    faylga/javobga/auditga ochiq yozilmaydi (m2a-contract.md §4) — `VoicemailBox`
    bilan BIR XIL qolip (`pin_hash` + `has_pin` DTO'da)."""
    __tablename__ = "conferences"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    record: Mapped[bool] = mapped_column(default=False)
    max_members: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Blacklist(Base):
    """`blacklist` (0001 + 0014) — qora ro'yxat (m2a-contract.md §5). Realtime
    (API yozadi, Asterisk `asterisk_blacklist` view'dan faqat o'qiydi — reload/apply
    shart emas). `number` — normalize_number() natijasi yoki maxsus 'anonymous'."""
    __tablename__ = "blacklist"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    number: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class NotifySettings(Base):
    """`notify_settings` (0010) — tenant bo'yicha bitta qator."""
    __tablename__ = "notify_settings"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    smtp_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_tls: Mapped[str] = mapped_column(Text, default="starttls")
    smtp_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_api_base: Mapped[str] = mapped_column(Text, default="https://api.telegram.org")
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class VoicemailNotification(Base):
    """`voicemail_notifications` (0010, `next_attempt_at` — 0030) — `unique
    (box_id, msg_id, channel)`; `status`: pending/sent/failed/dead."""
    __tablename__ = "voicemail_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    box_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("voicemail_boxes.id", ondelete="CASCADE"))
    msg_id: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


# ------------------------------------------------------------------ M2c (0016)
class IpBan(Base):
    """M2c §2 — faol ban: `lifted_at is null` (bitta IP uchun bittagina, qisman unique indeks)."""
    __tablename__ = "ip_bans"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    ip: Mapped[str] = mapped_column(INET)
    reason: Mapped[str] = mapped_column(Text)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    lifted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    lift_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SipAttackStat(Base):
    """M2c §2 — soat × IP agregat (hujum ostida har urinish alohida qator emas)."""
    __tablename__ = "sip_attack_stats"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    hour: Mapped[datetime] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(INET, primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    last_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    kind: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    extension_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="SET NULL"), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    # M3a §0 (0017): `ws` — WebRTC (nginx orqali) hodisasi; eski hodisalar NULL.
    transport: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutboundAttempt(Base):
    """M2c §3 — har `/internal/toll/check` chaqiruvi (`allowed` bilan)."""
    __tablename__ = "outbound_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"))
    number: Mapped[str] = mapped_column(Text)
    international: Mapped[bool] = mapped_column(default=False)
    allowed: Mapped[bool] = mapped_column()
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AlertLog(Base):
    """M2c §4 — ogohlantirish navbati + tarixi (`pending` → `alert_dispatch` yuboradi)."""
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    kind: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column("text", Text)  # ustun `text` — atribut nomi sqlalchemy `text()`ni soyalamasin
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)


# --------------------------------------------------------------------------- M3b (core)
class CallRecording(Base):
    """M3b §1 — MixMonitor fayli (`path` — `recordings_dir`ga nisbiy)."""
    __tablename__ = "call_recordings"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    linkedid: Mapped[str] = mapped_column(Text)
    uniqueid: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text, unique=True)
    extension: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column()
    duration_s: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CallEventState(Base):
    """M3b §0 — qo'ng'iroq hodisalari holati (bardoshlilik, kech hodisa filtri)."""
    __tablename__ = "call_event_state"

    linkedid: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    info: Mapped[dict] = mapped_column(JSONB, default=dict)
    ringing_sent: Mapped[bool] = mapped_column(default=False)
    answered_sent: Mapped[bool] = mapped_column(default=False)
    ended_sent: Mapped[bool] = mapped_column(default=False)
    last_hangup_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class IntegrationEvent(Base):
    """M3b §0/§2 — outbox hodisasi (yagona model, barcha yetkazuvchilar uchun)."""
    __tablename__ = "integration_events"

    id: Mapped[str] = _uuid_pk()
    seq: Mapped[int] = mapped_column(BigInteger, server_default=text("nextval('integration_events_seq_seq')"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(Text)
    call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class IntegrationSubscription(Base):
    """M3b §0/§3/§5 — umumiy obuna: `kind` (webhook|bitrix24|amocrm) + `config` + `secret_enc`."""
    __tablename__ = "integration_subscriptions"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=lambda: ["call.ringing", "call.answered", "call.ended"])
    include_internal: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failing_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class IntegrationDelivery(Base):
    """M3b §0 — bitta (obuna, hodisa) yetkazish urinishlari holati."""
    __tablename__ = "integration_deliveries"

    id: Mapped[str] = _uuid_pk()
    seq: Mapped[int] = mapped_column(BigInteger, server_default=text("nextval('integration_deliveries_seq_seq')"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    subscription_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("integration_subscriptions.id", ondelete="CASCADE"))
    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("integration_events.id", ondelete="CASCADE"))
    call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ApiKey(Base):
    """M3b §4 — `ipk_<prefix8>_<secret32>`; bazada faqat sha256 + prefix."""
    __tablename__ = "api_keys"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    prefix: Mapped[str] = mapped_column(Text, unique=True)
    key_hash: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ApiOriginateRequest(Base):
    """M3b §4 — `id` = AMI `ChannelId` = qo'ng'iroq `linkedid` (hodisalarda `call.origin`)."""
    __tablename__ = "api_originate_requests"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    api_key_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    extension: Mapped[str] = mapped_column(Text)
    to_number: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CrmUser(Base):
    """M3b §5 — CRM foydalanuvchilari keshi (`POST /integrations/crm/{provider}/test` yuklaydi)."""
    __tablename__ = "crm_users"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    crm_user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, default="")
    inner_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CrmUserMap(Base):
    """M3b §5 — ichki raqam → CRM foydalanuvchisi (`auto` | `manual`; qo'lda kiritilgani ustun)."""
    __tablename__ = "crm_user_map"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    extension: Mapped[str] = mapped_column(Text, primary_key=True)
    crm_user_id: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CrmCallLink(Base):
    """M3b §5 — qo'ng'iroq (`linkedid`) ↔ CRM kartasi (Bitrix `CALL_ID`); `origin='crm'` — click-to-call."""
    __tablename__ = "crm_call_links"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    linkedid: Mapped[str] = mapped_column(Text, primary_key=True)
    external_call_id: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text, default="pbx")
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    shown_users: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MacAddr(TypeDecorator):
    """`macaddr` ustuni: asyncpg dialekti MACADDR parametrini varchar sifatida yuboradi (`macaddr = varchar`
    operatori yo'q) — parametr SQL'da `CAST(... AS MACADDR)` bilan o'raladi (jonli topilgan, M4a)."""

    impl = MACADDR
    cache_ok = True

    def bind_expression(self, bindvalue):
        return cast(bindvalue, MACADDR)


class Device(Base):
    """M4a §1 — telefon apparati (0001 + 0020). `mac` — 12 kichik hex (`prov_catalog.normalize_mac`)."""
    __tablename__ = "devices"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    extension_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text, default="ip_phone")
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    mac: Mapped[str | None] = mapped_column(MacAddr, nullable=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provisioned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    firmware: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DeviceKey(Base):
    """M4a §1 — dastur tugmasi (BLF / tez terish / ...), apparatda `idx` 1..60."""
    __tablename__ = "device_keys"

    device_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[str] = mapped_column(Text, default="")


class DiscoveredDevice(Base):
    """M4a §1 — to'g'ri token bilan so'ragan, lekin ro'yxatda yo'q MAC (biriktirilganda o'chadi)."""
    __tablename__ = "discovered_devices"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    mac: Mapped[str] = mapped_column(MacAddr, primary_key=True)
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    firmware: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    requests: Mapped[int] = mapped_column(Integer, default=1)


class ProvisionRequest(Base):
    """M4a §0 (5-qatlam) — provizioning so'rovlari jurnali (30 kun). `path` da token maskalangan."""
    __tablename__ = "provision_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    mac: Mapped[str | None] = mapped_column(MacAddr, nullable=True)
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    path: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class QrProvisionToken(Base):
    """M5b §2 — QR orqali sozlash havolasi: ichki raqamga BITTA faol token, bazada faqat SHA-256 xeshi."""
    __tablename__ = "qr_provision_tokens"

    extension_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="CASCADE"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column()
    first_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MigrationJob(Base):
    """M5a §2 — FreePBX'dan ko'chirish ishi (yuklash yoki SSH). `plan`/`result`/`error` —
    strukturaviy JSON (sirlar YO'Q — `app/services/fpbx/plan.py` kafolatlaydi)."""
    __tablename__ = "migration_jobs"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    step: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bundle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    options: Mapped[dict] = mapped_column(JSONB, default=lambda: {"rotate_weak_secrets": False})
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pre_import_backup_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("backups.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MigrationItem(Base):
    """M5a §2 — import qilingan (yoki rejalashtirilgan) obyektning kelib chiqishi.
    `(tenant_id, kind, source_ref)` unikal — qayta import "already_imported" deb taniydi."""
    __tablename__ = "migration_items"
    __table_args__ = (
        Index("ix_migration_items_tenant_kind_ref", "tenant_id", "kind", "source_ref", unique=True),
    )

    id: Mapped[str] = _uuid_pk()
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("migration_jobs.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(Text)
    innova_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    innova_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Campaign(Base):
    """M6 (`campaigns`, 0025) — avtoinformator (`message`) / avtoterish (`connect`), m6-contract.md §1."""
    __tablename__ = "campaigns"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    audio_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("audio_files.id", ondelete="RESTRICT"), nullable=True)
    target_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    dtmf_connect: Mapped[bool] = mapped_column(default=False)
    dtmf_optout: Mapped[bool] = mapped_column(default=False)
    callerid: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=2)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_s: Mapped[int] = mapped_column(Integer, default=600)
    ring_seconds: Mapped[int] = mapped_column(Integer, default=25)
    window_start: Mapped[dt_time] = mapped_column(Time, default=dt_time(9, 0))
    window_end: Mapped[dt_time] = mapped_column(Time, default=dt_time(20, 0))
    days: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=lambda: [1, 2, 3, 4, 5, 6])
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CampaignContact(Base):
    __tablename__ = "campaign_contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("campaigns.id", ondelete="CASCADE"))
    number: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    billsec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CampaignAttempt(Base):
    __tablename__ = "campaign_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("campaigns.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("campaign_contacts.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    dial_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    billsec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key: Mapped[str | None] = mapped_column(Text, nullable=True)


class CampaignOptout(Base):
    __tablename__ = "campaign_optouts"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    number: Mapped[str] = mapped_column(Text, primary_key=True)
    campaign_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


# ------------------------------------------------------------ M9 Bo'lak B (0032)
class PinSet(Base):
    """B1: PIN to'plami — chiquvchi marshrutga ulanadi (`outbound_routes.pin_set_id`)."""
    __tablename__ = "pin_sets"
    __table_args__ = (Index("ix_pin_sets_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    record_in_cdr: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    pins: Mapped[list["PinSetPin"]] = relationship(
        back_populates="pin_set", cascade="all, delete-orphan", order_by="PinSetPin.id")


class PinSetPin(Base):
    """B1: to'plamdagi bitta PIN — ochiq matn saqlanmaydi, faqat HMAC-SHA256."""
    __tablename__ = "pin_set_pins"

    id: Mapped[str] = _uuid_pk()
    pin_set_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pin_sets.id", ondelete="CASCADE"))
    pin_hmac: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)

    pin_set: Mapped[PinSet] = relationship(back_populates="pins")


class PhonebookContact(Base):
    """B2: telefon kitobi kontakti."""
    __tablename__ = "phonebook_contacts"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    numbers: Mapped[list["PhonebookNumber"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", order_by="PhonebookNumber.id")


class PhonebookNumber(Base):
    """B2: kontaktning raqami (CID lookup shu jadvaldan `number_norm` bo'yicha qidiradi)."""
    __tablename__ = "phonebook_numbers"
    __table_args__ = (Index("ix_phonebook_numbers_tenant_number", "tenant_id", "number_norm"),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    contact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("phonebook_contacts.id", ondelete="CASCADE"))
    number_norm: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)

    contact: Mapped[PhonebookContact] = relationship(back_populates="numbers")


class CidLookupSource(Base):
    """B2: CID Lookup manbai — `phonebook` (ichki kitob), `crm` (hali amalga oshirilmagan,
    §0.4 "mavjud bo'lsa qayta ishlatish" qoidasi bo'yicha hujjatlashtirilgan) yoki `http`."""
    __tablename__ = "cid_lookup_sources"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    http_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=1500)
    cache_ttl_s: Mapped[int] = mapped_column(Integer, default=3600)
    enabled: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class QaChecklist(Base):
    """M10 B1 — sifat baholash varaqasi: nomlangan mezonlar to'plami. Ball
    hisobi sof funksiyada (`app/services/qa_scoring.py`); bu yerda faqat
    mezon ta'rifi (`kind`/`weight`/`critical`) saqlanadi."""
    __tablename__ = "qa_checklists"
    __table_args__ = (Index("ix_qa_checklists_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    criteria: Mapped[list["QaCriterion"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", order_by="QaCriterion.position")


class QaCriterion(Base):
    """M10 B1 — bitta mezon: `kind` 'yesno'/'scale5', `critical`=True bo'lsa
    muvaffaqiyatsizlik butun baholashni 0% qiladi (`qa_scoring.is_critical_fail`)."""
    __tablename__ = "qa_criteria"

    id: Mapped[str] = _uuid_pk()
    checklist_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("qa_checklists.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(default=1.0)
    critical: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    checklist: Mapped[QaChecklist] = relationship(back_populates="criteria")


class QaEvaluation(Base):
    """M10 B1 — bitta qo'ng'iroqning bitta baholashi: `answers` JSONB
    `{criterion_id: value}` (bool yoki 1..5 int), `score_pct` saqlanadi
    (qayta hisoblash — `qa_scoring.score_pct`, chiqishda keshlanadi, tahrirda
    qayta hisoblanadi) — snapshot sifatida mezon o'chirilsa/o'zgarsa ham
    tarixiy ball o'zgarmasin."""
    __tablename__ = "qa_evaluations"
    __table_args__ = (Index("ix_qa_evaluations_tenant_call", "tenant_id", "call_id"),)

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    checklist_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("qa_checklists.id", ondelete="RESTRICT"))
    call_id: Mapped[str] = mapped_column(Text)  # cdr.linkedid (CDR'da real FK yo'q)
    extension_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("extensions.id", ondelete="SET NULL"), nullable=True)
    evaluator_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_pct: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    checklist: Mapped[QaChecklist] = relationship()


class TotpChallenge(Base):
    """M10 B2 — ikki bosqichli login oraliq holati: `POST /auth/login`
    parolni tasdiqlagandan keyin shu yerga yoziladi, `token_hash`
    (`RefreshToken.token_hash` qolipi) `POST /auth/login/totp`da taqdim
    etiladi. `expires_at` — 5 daqiqa; `attempts` 5 dan oshsa bekor
    (`app/api/v1/auth.py`da tekshiriladi)."""
    __tablename__ = "totp_challenges"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime] = mapped_column()


# =============================================================== M10 Bo'lak A
class CallbackWidget(Base):
    """A1 — qayta chaqirish vidjeti (S17): sayt tashrifchisi raqamini qoldiradi,
    tizim avval operatorni (`target_id`), javob bersa mijozni teradi
    (`app/services/dialplan_callback.py`). `public_key` — ochiq, URL'da
    (`GET /widget/{public_key}.js`) — maxfiy EMAS, faqat vidjetni aniqlaydi."""
    __tablename__ = "callback_widgets"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    public_key: Mapped[str] = mapped_column(Text, unique=True)
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    allowed_origins: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    time_group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("time_groups.id", ondelete="SET NULL"), nullable=True)
    offhours_mode: Mapped[str] = mapped_column(Text, default="schedule")
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    retry_interval_s: Mapped[int] = mapped_column(Integer, default=120)
    callerid_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_international: Mapped[bool] = mapped_column(default=False)
    appearance: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CallbackRequest(Base):
    """A1 — vidjetdan kelgan bitta qayta chaqirish so'rovi (jamoatchilik
    terminal holati: `connected`/`failed`/`rejected`/`cancelled`).
    `linkedid` — AMI Originate'dan keyin dialplan CURL orqali yoziladi."""
    __tablename__ = "callback_requests"
    __table_args__ = (
        Index("ix_callback_requests_tenant_created", "tenant_id", "created_at"),
        Index("ix_callback_requests_status_next", "status", "next_attempt_at"),
    )

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    widget_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("callback_widgets.id", ondelete="CASCADE"))
    phone: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    linkedid: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MissedCallRule(Base):
    """A2 — o'tkazib yuborilgan qo'ng'iroq bo'yicha bildirishnoma qoidasi
    (`scope_kind`/`scope_value` — `call.ended` hodisasi maydonlari bilan
    solishtiriladi, `app/services/missed_call_notify.py::rule_matches`)."""
    __tablename__ = "missed_call_rules"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    scope_kind: Mapped[str] = mapped_column(Text)
    scope_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    emails: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    include_internal: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MissedCallNotice(Base):
    """A2 — bitta qoida uchun bitta qo'ng'iroq bo'yicha yuborilgan/muvaffaqiyatsiz
    bildirishnoma (`unique(rule_id, call_id)` — takror yuborishdan himoya)."""
    __tablename__ = "missed_call_notices"
    __table_args__ = (Index("ix_missed_call_notices_rule_call", "rule_id", "call_id", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    rule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("missed_call_rules.id", ondelete="CASCADE"))
    call_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MissedNotifyCursor(Base):
    """A2 — tenant bo'yicha `integration_events.seq` o'qish kursori (fon vazifa
    `missed_call_notify.py::run_forever` har aylanishda shundan davom etadi)."""
    __tablename__ = "missed_notify_cursor"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    last_seq: Mapped[int] = mapped_column(BigInteger, default=0)


class TtsSettings(Base):
    """A3 — Yandex SpeechKit TTS sozlamalari (tenant bo'yicha YAGONA qator).
    `api_key_enc` — `crypto.encrypt_secret`, hech qachon qaytarilmaydi
    (`crypto_registry.py`da ro'yxatdan o'tgan)."""
    __tablename__ = "tts_settings"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, default="none")
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    voices: Mapped[dict] = mapped_column(JSONB, default=lambda: {"uz": "nigora", "ru": "alena", "en": "john"})
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DayNight(Base):
    """M12 A1 — Kun/Tun rejimi (Call Flow Control). O'z `call_targets` yozuvi
    (`target_id`) bor — IVR/marshrut/vaqt sharti undan manzil sifatida
    foydalanishi mumkin (`TimeCondition` bilan BIR XIL qolip). Holat (`mode`)
    astdb'da EMAS — shu qatorda (PG — yagona manba, dialplan CURL bilan
    reload'siz o'qiydi/yozadi, `compiler.py::_day_night_dest_lines`/
    `_day_night_toggle_lines`). `pin_hmac` — mavjud HMAC-SHA256 usuli
    (`pin_hmac.py`, `pin_sets.pin_hmac` BILAN BIR XIL qolip, ochiq matn
    saqlanmaydi)."""
    __tablename__ = "day_night"
    __table_args__ = (
        Index("ix_day_night_tenant_code", "tenant_id", "code", unique=True),
        Index("ix_day_night_tenant_name", "tenant_id", "name", unique=True),
    )

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text, default="day")
    day_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    night_target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="RESTRICT"))
    pin_hmac: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Disa(Base):
    """M12 A2 — DISA (tashqaridan PIN bilan chiquvchi marshrutga kirish).
    `cid_override` — DISA orqali chiqadigan qo'ng'iroq uchun CallerID (bo'sh
    bo'lsa o'zgartirilmaydi). `max_attempts`/`allow_no_pin` — xavfsizlik
    (API: PIN bo'sh faqat `allow_no_pin=true` bilan, `compiler.py` 3
    urinishdan keyin Hangup qiladi)."""
    __tablename__ = "disa"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False),
                                                  ForeignKey("tenants.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("call_targets.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    pin_hmac: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_no_pin: Mapped[bool] = mapped_column(default=False)
    cid_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    digit_timeout: Mapped[int] = mapped_column(Integer, default=5)
    response_timeout: Mapped[int] = mapped_column(Integer, default=10)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
