"""Pydantic so'rov/javob modellari — manba: `replica/m0-contract.md` (yagona manba,
frontend `web/src/api/types.ts` shu bilan mos bo'lishi SHART)."""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.netd.firewall import SERVICE_NAMES, is_valid_cidr
from app.netd.systemtime import is_valid_ntp_server, is_valid_timezone
from app.netd.validate import is_valid_hostname
from app.services.dialplan_safety import has_control_chars, is_dialplan_number

Lang = Literal["uz", "ru", "en"]
# m7-roles-contract.md §3: endi istalgan mavjud rol NOMI (maxsus rollar ham
# bo'lishi mumkin) — shu sabab `Literal["admin","operator"]` EMAS, erkin satr
# (login/`/auth/me` javobida `user.role.name` qanday bo'lsa SHU qaytariladi).
Role = str
ApplyStatus = Literal["applied", "unchanged", "rolled_back", "realtime", "restart_required"]
ExtensionStatus = Literal["online", "offline", "unknown"]
TrunkHealthState = Literal["ok", "unreachable", "unknown", "disabled"]
CallDirection = Literal["in", "out", "internal"]
RecordingPolicy = Literal["always", "never", "on_demand"]
CallDisposition = Literal["answered", "no_answer", "busy", "failed"]
TargetKind = Literal[
    "extension", "ring_group", "queue", "ivr", "time_condition", "hangup", "busy", "voicemail",
    # Avval ham `call_targets`/`target_resolution.py`da mavjud edi (conference — M2a),
    # lekin shu Literal'da yo'q edi — M9 A bilan birga tuzatildi.
    "conference", "announcement", "misc",
    # M12 A1/A2: Kun/Tun rejimi va DISA — boshqa marshrut/IVR ularni manzil
    # sifatida ko'rsata oladi (satellit qolipi).
    "day_night", "disa",
]
RingGroupStrategy = Literal["ringall", "hunt", "memoryhunt"]
QueueStrategy = Literal[
    "ringall", "leastrecent", "fewestcalls", "random", "rrmemory", "linear", "wrandom",
]
TimeConditionOverride = Literal["auto", "force_open", "force_closed"]
TimeConditionState = Literal["open", "closed"]
UsageKind = Literal["inbound_route", "ivr", "ivr_option", "time_condition", "ring_group", "queue", "outbound_route",
                    "extension", "announcement", "misc_application", "parking_settings",
                    "day_night"]  # M12 A1
AuthMode = Literal["ip", "register"]
RegistrationState = Literal["registered", "rejected", "unregistered", "null"]
SimulateStepResult = Literal["match", "no_pattern", "ext_not_allowed", "international_blocked", "disabled"]
AuditAction = Literal[
    "create", "update", "delete", "login", "login_failed", "restore", "restart", "override",
]
RevisionStatus = Literal["compiled", "applied", "failed", "rolled_back"]


# ----------------------------------------------- dialplan injection himoyasi (kirish validatsiyasi)
# CONFIRMED HIGH tuzatish: ism/DID/CID/callerid/`add_prefix` kabi matn/raqam
# maydonlari generatsiya qilinadigan Asterisk dialplan'ga TO'G'RIDAN-TO'G'RI
# tushadi (`app/services/compiler.py`). Bu yerda — BIRINCHI himoya chizig'i
# (yaxshi UX, aniq 422 xabar); `app/services/dialplan_safety.py` — render
# vaqtidagi IKKINCHI chiziq (CSV import/FreePBX migratsiyasi Pydantic'ni
# chetlab o'tishi mumkin, shu sabab ikkalasi ham SHART).
def _check_no_control_chars(value: str | None) -> str | None:
    if has_control_chars(value):
        raise ValueError("boshqaruv belgilar (shu jumladan qator ko'chirish \\r\\n) ruxsat etilmagan")
    return value


def _check_dialplan_number_opt(value: str | None) -> str | None:
    """Bo'sh/`None` — ruxsat (DID/CID/callerid filtrsiz/qiymatsiz bo'lishi
    mumkin); aks holda faqat Asterisk dialplan uchun xavfsiz belgi to'plami
    (raqam, `+ * # _ X N Z . ! [ ] -`, 1-40 ta)."""
    if not value:
        return value
    if not is_dialplan_number(value):
        raise ValueError("faqat raqam va + * # _ X N Z . ! [ ] - belgilari (1-40 ta) ruxsat etilgan")
    return value


class ApplyResult(BaseModel):
    status: ApplyStatus
    revision: int | None
    message: str | None


# --------------------------------------------------------------------------- setup/auth
class AdminPayload(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str
    full_name: str = Field(min_length=1, max_length=128)


class SetupPayload(BaseModel):
    admin: AdminPayload
    language: Lang = "uz"
    timezone: str = "Asia/Tashkent"
    external_ip: str | None = None
    local_nets: list[str] = Field(default_factory=lambda: ["10.0.0.0/8"])
    # 1.0.4: o'rnatish kodi (`settings.setup_code` bo'sh bo'lsa tekshirilmaydi).
    code: str | None = None


class SetupState(BaseModel):
    needed: bool


class LoginPayload(BaseModel):
    login: str
    password: str


class RefreshPayload(BaseModel):
    refresh: str


class UserOut(BaseModel):
    id: str
    login: str
    full_name: str
    role: Role
    permissions: list[str]
    language: Lang
    # M2b §3: `true` bo'lsa, web parolni almashtirishga majburlaydi (login
    # bloklanmaydi — faqat signal). `app.api.v1.auth._user_out()`da to'ldiriladi.
    must_change_password: bool = False
    # M2b: shell (yuqori panel) foydalanuvchining O'Z ichki raqamini ko'rsatadi; yo'q bo'lsa null.
    extension: "ExtensionRef | None" = None
    # M10 B2: 2FA holati — `must_enroll_2fa`=True bo'lsa frontend to'g'ridan-to'g'ri
    # `/me/2fa/setup`ga yo'naltirishi kerak (`app/api/deps.py` server tomonida ham bloklaydi).
    totp_enabled: bool = False
    must_enroll_2fa: bool = False


class UpdateMePayload(BaseModel):
    language: Lang



class AuthResult(BaseModel):
    # M10 B2: 2FA yoqilgan bo'lsa `status="totp_required"` va faqat `challenge`
    # qaytadi (access/refresh/user — HALI yo'q); eski klient uchun sukut
    # `status="ok"` + to'liq maydonlar (orqaga mos).
    status: Literal["ok", "totp_required"] = "ok"
    access: str | None = None
    refresh: str | None = None
    user: UserOut | None = None
    challenge: str | None = None


class TokenPair(BaseModel):
    access: str
    refresh: str


# --------------------------------------------------------------------------- extensions
class ExtensionOut(BaseModel):
    id: str
    number: str
    name: str
    enabled: bool
    status: ExtensionStatus
    contact: str | None
    user_agent: str | None
    outbound_allowed: bool = True
    outbound_callerid: str | None = None
    # M2a §1 — realtime (o'zgarishi apply talab qilmaydi).
    dnd: bool = False
    forward_always: str | None = None
    forward_busy: str | None = None
    pickup_group: str | None = None
    # M2c §3 — toll-fraud avtomatik bloki (admin `outbound_allowed`dan ALOHIDA).
    toll_blocked_at: datetime | None = None
    toll_block_reason: str | None = None
    # M3a §2 — `true`: raqamning YAGONA qurilmasi brauzer softfoni (endpoint `webrtc=yes`, realtime).
    webrtc: bool = False
    codecs: list[str] = Field(default_factory=list)
    # M3b/M3c §1 — yozuv siyosati (realtime, apply shart emas). `recording` — eski nom,
    # `recording_in` bilan BIR XIL qiymat (orqaga moslik); `recording_out` — chiquvchi.
    recording: RecordingPolicy = "always"
    recording_in: RecordingPolicy = "always"
    recording_out: RecordingPolicy = "always"
    # M9 A5 — kutish holatidagi qo'ng'iroq (realtime, apply shart emas).
    call_waiting: bool = True
    updated_at: datetime


class SipCredentials(BaseModel):
    username: str
    password: str
    domain: str
    port: int


class CreateExtensionPayload(BaseModel):
    number: str | None = Field(default=None, pattern=r"^\d{2,10}$")
    name: str = Field(min_length=1, max_length=128)
    # Foydalanuvchi o'zi belgilagan SIP paroli (FreePBX-uslubida); bo'sh — tasodifiy
    # (`generate_sip_secret`). Tekshiruv — `sip_secret_policy.validate_sip_password`.
    password: str | None = None
    # M3a §2: tekshiruv/standart — `app/services/ext_media.py` (422 `webrtc_codec`/`bad_codec`).
    webrtc: bool = False
    codecs: list[str] | None = None
    # M3c §1: `recording` — eski nom, ikkalasini ham o'rnatadi (orqaga moslik: FreePBX
    # import, public/fake API); aniq `recording_in`/`recording_out` berilsa ular ustun
    # (yagona birlashtirish qoidasi — `app/api/v1/extensions.py::_recording_changes`).
    recording: RecordingPolicy | None = None
    recording_in: RecordingPolicy | None = None
    recording_out: RecordingPolicy | None = None
    # Yaratishda darhol sozlash — `UpdateExtensionPayload` bilan BIR XIL maydonlar va
    # tekshiruv (`apply_call_field_patch`, dryer): berilmagan = standart qiymat.
    enabled: bool | None = None
    outbound_allowed: bool | None = None
    outbound_callerid: str | None = None
    dnd: bool | None = None
    forward_always: str | None = None
    forward_busy: str | None = None
    pickup_group: str | None = None
    call_waiting: bool | None = None

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_outbound_callerid = field_validator("outbound_callerid")(_check_dialplan_number_opt)


class UpdateExtensionPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    outbound_allowed: bool | None = None
    outbound_callerid: str | None = None
    # M2a §1: aniq `null` = tozalash, berilmagan = o'zgarmaydi (`model_fields_set`).
    # Format router'da tekshiriladi (422 `bad_number`/`bad_pickup_group` + `field`).
    dnd: bool | None = None
    forward_always: str | None = None
    forward_busy: str | None = None
    pickup_group: str | None = None
    webrtc: bool | None = None
    codecs: list[str] | None = None
    # M3c §1 — qarang `CreateExtensionPayload`dagi izoh (bitta birlashtirish qoidasi).
    recording: RecordingPolicy | None = None
    recording_in: RecordingPolicy | None = None
    recording_out: RecordingPolicy | None = None
    call_waiting: bool | None = None
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_outbound_callerid = field_validator("outbound_callerid")(_check_dialplan_number_opt)


class ExtensionCreated(BaseModel):
    item: ExtensionOut
    sip: SipCredentials
    apply: ApplyResult


class ExtensionMutated(BaseModel):
    item: ExtensionOut
    apply: ApplyResult


class RotateSecretResult(BaseModel):
    sip: SipCredentials
    apply: ApplyResult


class SetSecretPayload(BaseModel):
    """`PUT /extensions/{id}/secret` — foydalanuvchi o'zi tanlagan SIP paroli
    (`sip_secret_policy.validate_sip_password` tekshiradi)."""
    password: str


class Paged(BaseModel):
    items: list[Any]
    total: int


# --------------------------------------------------------------------------- trunks
class TrunkHealthOut(BaseModel):
    state: TrunkHealthState
    rtt_ms: int | None
    checked_at: datetime | None
    registration: RegistrationState | None = None
    reason: str | None = None


class TrunkOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    match: list[str]
    codecs: list[str]
    max_channels: int | None
    enabled: bool
    health: TrunkHealthOut
    updated_at: datetime
    auth_mode: AuthMode = "ip"
    username: str | None = None
    from_domain: str | None = None
    outbound_callerid: str | None = None
    has_password: bool = False


class CreateTrunkPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5060, ge=1, le=65535)
    match: list[str] = Field(default_factory=list)
    codecs: list[str] = Field(default_factory=lambda: ["alaw", "ulaw"])
    max_channels: int | None = None
    enabled: bool = True
    auth_mode: AuthMode = "ip"
    username: str | None = None
    password: str | None = None
    from_domain: str | None = None
    outbound_callerid: str | None = None

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_outbound_callerid = field_validator("outbound_callerid")(_check_dialplan_number_opt)


class UpdateTrunkPayload(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    # `match_ips` — DB ustuni nomi (m5a-proof §5 shu kalit bilan yuboradi); jim e'tiborsiz qolmasin.
    match: list[str] | None = Field(default=None, validation_alias=AliasChoices("match", "match_ips"))
    codecs: list[str] | None = None
    max_channels: int | None = None
    enabled: bool | None = None
    auth_mode: AuthMode | None = None
    username: str | None = None
    password: str | None = None
    from_domain: str | None = None
    outbound_callerid: str | None = None
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_outbound_callerid = field_validator("outbound_callerid")(_check_dialplan_number_opt)


class TrunkMutated(BaseModel):
    item: TrunkOut
    apply: ApplyResult


class TrunkTestResult(BaseModel):
    ok: bool
    rtt_ms: int | None
    detail: str


# --------------------------------------------------------------------------- targets / inbound routes
class RouteTarget(BaseModel):
    id: str
    kind: TargetKind
    label: str
    number: str | None = None
    broken: bool


class TargetUsage(BaseModel):
    kind: UsageKind
    id: str
    label: str
    field: str


class CidLookupSourceRef(BaseModel):
    id: str
    name: str


# M9 B3: SIP Alert-Info — faqat xavfsiz belgilar (sarlavha qiymati sifatida yuboriladi).
_ALERT_INFO_PATTERN = r"^[A-Za-z0-9=<>:;/._@-]{1,128}$"


class InboundRouteOut(BaseModel):
    id: str
    name: str
    did: str | None
    cid: str | None
    target: RouteTarget
    enabled: bool
    updated_at: datetime
    # M9 B3 (0032): CID nom prefiksi + Alert-Info + CID Lookup manbai.
    cid_name_prefix: str | None = None
    alert_info: str | None = None
    cid_lookup_source: CidLookupSourceRef | None = None


class CreateInboundRoutePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    did: str | None = None
    cid: str | None = None
    target_id: str
    enabled: bool = True
    cid_name_prefix: str | None = Field(default=None, max_length=64)
    alert_info: str | None = Field(default=None, pattern=_ALERT_INFO_PATTERN)
    cid_lookup_source_id: str | None = None

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_cid_name_prefix = field_validator("cid_name_prefix")(_check_no_control_chars)
    _check_did = field_validator("did")(_check_dialplan_number_opt)
    _check_cid = field_validator("cid")(_check_dialplan_number_opt)


class UpdateInboundRoutePayload(BaseModel):
    name: str | None = None
    did: str | None = None
    cid: str | None = None
    target_id: str | None = None
    enabled: bool | None = None
    cid_name_prefix: str | None = Field(default=None, max_length=64)
    alert_info: str | None = Field(default=None, pattern=_ALERT_INFO_PATTERN)
    cid_lookup_source_id: str | None = None
    cid_name_prefix_clear: bool = False
    alert_info_clear: bool = False
    cid_lookup_source_clear: bool = False
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_cid_name_prefix = field_validator("cid_name_prefix")(_check_no_control_chars)
    _check_did = field_validator("did")(_check_dialplan_number_opt)
    _check_cid = field_validator("cid")(_check_dialplan_number_opt)


class InboundRouteMutated(BaseModel):
    item: InboundRouteOut
    apply: ApplyResult


# --------------------------------------------------------------------------- calls
class CallRecordingRef(BaseModel):
    id: str
    duration_s: int


class CallQaBadge(BaseModel):
    """M10 B1 — `/calls` ro'yxatida bitta yengil belgi (ro'yxat uchun to'liq
    `QaEvaluationOut` EMAS): bir nechta baholash bo'lsa ENG OXIRGISI (eng
    yangi `created_at`)."""
    evaluation_id: str
    checklist_name: str
    score_pct: float


class CallOut(BaseModel):
    uniqueid: str
    started_at: datetime
    src: str
    dst: str
    did: str | None
    direction: CallDirection
    disposition: CallDisposition
    duration: int
    billsec: int
    trunk: str | None
    # M9 — CallerID ismi (`cdr.clid`) va PIN-to'plam yorlig'i (`cdr.pin_label`, FreePBX accountcode).
    src_name: str | None = None
    pin_label: str | None = None
    # M3b §1 — `linkedid` bo'yicha yozuvlar (transfer — bir nechta fayl).
    linkedid: str | None = None
    recordings: list[CallRecordingRef] = Field(default_factory=list)
    # M10 B1: ko'p N+1'siz (bir martalik bulk so'rov — `qa.attach_qa()`) belgi.
    qa: CallQaBadge | None = None


# --------------------------------------------------------------------------- system
class AsteriskHealth(BaseModel):
    up: bool
    version: str | None
    uptime_s: int | None


class DbHealth(BaseModel):
    up: bool


class SystemHealth(BaseModel):
    asterisk: AsteriskHealth
    db: DbHealth
    revision: int | None


# --------------------------------------------------------------- GET /system/status
DiskCategoryKey = Literal["recordings", "backups", "migrations", "voicemail", "logs"]


class DiskCategoryOut(BaseModel):
    key: DiskCategoryKey
    bytes: int
    files: int
    cleanable: bool


class SystemDiskOut(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    used_pct: int
    categories: list[DiskCategoryOut]


class SystemInternetOut(BaseModel):
    up: bool
    dns_ok: bool
    latency_ms: int | None
    target: str
    error: str | None


class SipTransportOut(BaseModel):
    name: str
    protocol: str
    bind: str


class SystemSipOut(BaseModel):
    asterisk_up: bool
    transports: list[SipTransportOut]
    endpoints_total: int
    endpoints_online: int


class SystemStatusOut(BaseModel):
    disk: SystemDiskOut
    trunks: list[TrunkDashboardOut]
    internet: SystemInternetOut
    sip: SystemSipOut


# --------------------------------------------------------------- disk tozalash
class CleanupIn(BaseModel):
    recordings_older_than_days: int | None = Field(default=None, ge=1)
    backups_keep_last: int | None = Field(default=None, ge=1)
    migrations: bool = False


class CleanupCategoryOut(BaseModel):
    files: int
    bytes: int


class CleanupResultOut(BaseModel):
    recordings: CleanupCategoryOut
    backups: CleanupCategoryOut
    migrations: CleanupCategoryOut
    total_bytes: int
    errors: list[str]


class ConfigRevisionOut(BaseModel):
    id: str
    sha256: str
    status: str
    created_at: datetime
    message: str | None


# =============================================================== M1a: ish vaqti
class TimeRangeIn(BaseModel):
    weekdays: list[int] = Field(min_length=1)
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class TimeGroupOut(BaseModel):
    id: str
    name: str
    ranges: list[TimeRangeIn]
    updated_at: datetime


class CreateTimeGroupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ranges: list[TimeRangeIn] = Field(default_factory=list)


class UpdateTimeGroupPayload(BaseModel):
    name: str | None = None
    ranges: list[TimeRangeIn] | None = None
    updated_at: datetime


class TimeGroupMutated(BaseModel):
    item: TimeGroupOut


class HolidayOut(BaseModel):
    id: str
    name: str
    day: str
    recurring_yearly: bool


class CreateHolidayPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    day: str
    recurring_yearly: bool = False


class ImportUzHolidaysPayload(BaseModel):
    year: int = Field(ge=2000, le=2100)


class ImportUzHolidaysResult(BaseModel):
    items: list[HolidayOut]
    created: int
    skipped: list[str] = Field(default_factory=list)


class TimeConditionOut(BaseModel):
    id: str
    name: str
    number: str | None
    time_group: dict
    honor_holidays: bool
    open_target: RouteTarget
    closed_target: RouteTarget
    override: TimeConditionOverride
    toggle_code: str | None
    state_now: TimeConditionState
    updated_at: datetime


class CreateTimeConditionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    time_group_id: str
    honor_holidays: bool = True
    open_target_id: str
    closed_target_id: str
    override: TimeConditionOverride = "auto"
    toggle_code: str | None = Field(default=None, pattern=r"^\*[0-9]{2,4}$")


class UpdateTimeConditionPayload(BaseModel):
    name: str | None = None
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    time_group_id: str | None = None
    honor_holidays: bool | None = None
    open_target_id: str | None = None
    closed_target_id: str | None = None
    toggle_code: str | None = Field(default=None, pattern=r"^\*[0-9]{2,4}$")
    updated_at: datetime


class TimeConditionMutated(BaseModel):
    item: TimeConditionOut
    apply: ApplyResult


class OverridePayload(BaseModel):
    override: TimeConditionOverride


# =============================================================================== M12 A1: Kun/Tun rejimi
class DayNightOut(BaseModel):
    id: str
    name: str
    code: str
    mode: Literal["day", "night"]
    day_target: RouteTarget
    night_target: RouteTarget
    has_pin: bool
    updated_at: datetime


class CreateDayNightPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(pattern=r"^[0-9]$")
    day_target_id: str
    night_target_id: str
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")

    _check_name = field_validator("name")(_check_no_control_chars)


class UpdateDayNightPayload(BaseModel):
    name: str | None = None
    code: str | None = Field(default=None, pattern=r"^[0-9]$")
    day_target_id: str | None = None
    night_target_id: str | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    pin_clear: bool = False
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)


class DayNightMutated(BaseModel):
    item: DayNightOut
    apply: ApplyResult


# =============================================================================== M12 A2: DISA
class DisaOut(BaseModel):
    id: str
    name: str
    has_pin: bool
    allow_no_pin: bool
    cid_override: str | None
    digit_timeout: int
    response_timeout: int
    max_attempts: int
    enabled: bool
    updated_at: datetime


class CreateDisaPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    allow_no_pin: bool = False
    cid_override: str | None = None
    digit_timeout: int = Field(default=5, ge=1, le=60)
    response_timeout: int = Field(default=10, ge=1, le=60)
    max_attempts: int = Field(default=3, ge=1, le=10)
    enabled: bool = True

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_cid = field_validator("cid_override")(_check_dialplan_number_opt)

    @model_validator(mode="after")
    def _check_pin_or_allow(self) -> "CreateDisaPayload":
        # m12-contract.md A2: PIN bo'sh FAQAT `allow_no_pin=true` bilan.
        if not self.pin and not self.allow_no_pin:
            raise ValueError("PIN bo'sh bo'lishi uchun allow_no_pin=true ko'rsatilishi SHART")
        return self


class UpdateDisaPayload(BaseModel):
    name: str | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    pin_clear: bool = False
    allow_no_pin: bool | None = None
    cid_override: str | None = None
    digit_timeout: int | None = Field(default=None, ge=1, le=60)
    response_timeout: int | None = Field(default=None, ge=1, le=60)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    enabled: bool | None = None
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_cid = field_validator("cid_override")(_check_dialplan_number_opt)


class DisaMutated(BaseModel):
    item: DisaOut
    apply: ApplyResult


# =============================================================================== IVR
class IvrOptionOut(BaseModel):
    digit: str
    target: RouteTarget


class IvrOptionIn(BaseModel):
    digit: str = Field(pattern=r"^[0-9*#]$")
    target_id: str


class AudioOut(BaseModel):
    id: str
    name: str
    duration_ms: int
    format: Literal["wav"] = "wav"
    created_at: datetime


class IvrOut(BaseModel):
    id: str
    name: str
    number: str | None
    greeting: AudioOut
    invalid_audio: AudioOut | None
    timeout_seconds: int
    repeats: int
    direct_dial: bool
    options: list[IvrOptionOut]
    timeout_target: RouteTarget
    invalid_target: RouteTarget
    updated_at: datetime


class CreateIvrPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    greeting_audio_id: str
    invalid_audio_id: str | None = None
    timeout_seconds: int = Field(default=7, ge=1, le=60)
    repeats: int = Field(default=2, ge=0, le=5)
    direct_dial: bool = False
    options: list[IvrOptionIn] = Field(default_factory=list)
    timeout_target_id: str
    invalid_target_id: str


class UpdateIvrPayload(BaseModel):
    name: str | None = None
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    greeting_audio_id: str | None = None
    invalid_audio_id: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    repeats: int | None = Field(default=None, ge=0, le=5)
    direct_dial: bool | None = None
    options: list[IvrOptionIn] | None = None
    timeout_target_id: str | None = None
    invalid_target_id: str | None = None
    updated_at: datetime


class IvrMutated(BaseModel):
    item: IvrOut
    apply: ApplyResult


# ================================================================ qo'ng'iroq guruhi
class ExtensionRef(BaseModel):
    id: str
    number: str
    name: str


class RingGroupMemberOut(BaseModel):
    position: int
    extension: ExtensionRef | None = None
    external_number: str | None = None


class RingGroupMemberIn(BaseModel):
    """m1b-contract.md bo'lim 3: `{"extension_id"}|{"external_number"}` —
    bittasi berilishi SHART (ikkisi ham yoki hech biri emas)."""
    extension_id: str | None = None
    external_number: str | None = Field(default=None, pattern=r"^\+?[0-9]{3,15}$")

    @model_validator(mode="after")
    def _exactly_one(self) -> "RingGroupMemberIn":
        if bool(self.extension_id) == bool(self.external_number):
            raise ValueError("Faqat extension_id YOKI external_number berilishi SHART")
        return self


class RingGroupOut(BaseModel):
    id: str
    name: str
    number: str | None
    strategy: RingGroupStrategy
    ring_seconds: int
    members: list[RingGroupMemberOut]
    no_answer_target: RouteTarget
    callerid_prefix: str | None
    updated_at: datetime


class CreateRingGroupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    strategy: RingGroupStrategy = "ringall"
    ring_seconds: int = Field(default=20, ge=5, le=300)
    members: list[RingGroupMemberIn] = Field(default_factory=list)
    no_answer_target_id: str
    callerid_prefix: str | None = None


class UpdateRingGroupPayload(BaseModel):
    name: str | None = None
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    strategy: RingGroupStrategy | None = None
    ring_seconds: int | None = Field(default=None, ge=5, le=300)
    members: list[RingGroupMemberIn] | None = None
    no_answer_target_id: str | None = None
    callerid_prefix: str | None = None
    updated_at: datetime


class RingGroupMutated(BaseModel):
    item: RingGroupOut
    apply: ApplyResult


# ======================================================================== navbat
class QueueMemberOut(BaseModel):
    extension: ExtensionRef
    penalty: int
    # M2b §1 — agent holati (yagona manba PG, `asterisk_queue_members`/
    # `asterisk_agent_state` view'lar shu ustunlarni o'qiydi/yozadi).
    dynamic: bool
    logged_in: bool
    paused: bool
    pause_reason: str | None
    state_at: datetime


class QueueLive(BaseModel):
    waiting: int
    members_online: int


class QueueOut(BaseModel):
    id: str
    name: str
    number: str | None
    strategy: QueueStrategy
    agent_ring_seconds: int
    retry_seconds: int
    wrapup_seconds: int
    max_wait_seconds: int
    max_callers: int | None
    announce_position: bool
    announce_frequency_seconds: int
    sla_seconds: int
    join_empty: bool
    record: bool
    members: list[QueueMemberOut]
    timeout_target: RouteTarget
    live: QueueLive | None
    moh_class: "MohClassRef | None" = None
    updated_at: datetime


class QueueMemberIn(BaseModel):
    extension_id: str
    penalty: int = Field(default=0, ge=0, le=10)
    dynamic: bool = False


class CreateQueuePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    strategy: QueueStrategy = "rrmemory"
    agent_ring_seconds: int = Field(default=15, ge=5, le=120)
    retry_seconds: int = Field(default=5, ge=1)
    wrapup_seconds: int = Field(default=0, ge=0)
    max_wait_seconds: int = Field(default=300, gt=0)
    max_callers: int | None = Field(default=None, gt=0)
    announce_position: bool = True
    announce_frequency_seconds: int = Field(default=60, ge=0)
    sla_seconds: int = Field(default=20, ge=0)
    join_empty: bool = False
    record: bool = True
    members: list[QueueMemberIn] = Field(default_factory=list)
    timeout_target_id: str
    moh_class_id: str | None = None


class UpdateQueuePayload(BaseModel):
    name: str | None = None
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{2,10}$")
    strategy: QueueStrategy | None = None
    agent_ring_seconds: int | None = Field(default=None, ge=5, le=120)
    retry_seconds: int | None = Field(default=None, ge=1)
    wrapup_seconds: int | None = Field(default=None, ge=0)
    max_wait_seconds: int | None = Field(default=None, gt=0)
    max_callers: int | None = Field(default=None, gt=0)
    announce_position: bool | None = None
    announce_frequency_seconds: int | None = Field(default=None, ge=0)
    sla_seconds: int | None = Field(default=None, ge=0)
    join_empty: bool | None = None
    record: bool | None = None
    members: list[QueueMemberIn] | None = None
    timeout_target_id: str | None = None
    moh_class_id: str | None = None
    updated_at: datetime


class QueueMutated(BaseModel):
    item: QueueOut
    apply: ApplyResult


class AddQueueMemberPayload(BaseModel):
    extension_id: str
    penalty: int = Field(default=0, ge=0, le=10)
    dynamic: bool = False


class UpdateQueueMemberPayload(BaseModel):
    """`PATCH /queues/{id}/members/{extension_id}` (m2b-contract.md §1)."""
    penalty: int | None = Field(default=None, ge=0, le=10)
    dynamic: bool | None = None


class QueueMemberActionPayload(BaseModel):
    """`POST .../{login|logout|pause|unpause}` — `reason` faqat pauzada ma'noli
    (boshqalarida e'tiborsiz qoldiriladi, xato emas)."""
    reason: str | None = Field(default=None, max_length=64)


class QueueMemberMutated(BaseModel):
    """Kontrakt matni aniq: `{item: QueueMemberOut}` — `apply` YO'Q (realtime)."""
    item: QueueMemberOut


# ======================================================================== jonli (S29)
LiveCallState = Literal["ringing", "up", "queued", "held", "parked"]
LiveCallDirection = Literal["inbound", "outbound", "internal"]
AgentLiveState = Literal["idle", "ringing", "busy", "paused", "offline", "unavailable"]
ExtensionLiveState = Literal["idle", "ringing", "busy", "unavailable", "dnd"]


class LiveCallItem(BaseModel):
    id: str
    direction: LiveCallDirection
    from_: str = Field(alias="from")
    to: str
    state: LiveCallState
    started_at: datetime
    answered_at: datetime | None
    queue_id: str | None
    extension: str | None
    channels: list[str]

    model_config = {"populate_by_name": True}


class LiveQueueWaitingItem(BaseModel):
    from_: str = Field(alias="from")
    since: datetime
    position: int

    model_config = {"populate_by_name": True}


class LiveQueueAgentItem(BaseModel):
    extension: str
    name: str
    dynamic: bool
    logged_in: bool
    paused: bool
    pause_reason: str | None
    state: AgentLiveState
    answered_today: int


class LiveQueueItem(BaseModel):
    id: str
    name: str
    number: str | None
    waiting: list[LiveQueueWaitingItem]
    agents: list[LiveQueueAgentItem]


class LiveExtensionItem(BaseModel):
    number: str
    name: str
    state: ExtensionLiveState
    dnd: bool


class LiveStatusOut(BaseModel):
    at: datetime
    calls: list[LiveCallItem]
    queues: list[LiveQueueItem]
    extensions: list[LiveExtensionItem]
    # Qo'shimcha (kontraktda faqat "down" holati uchun eslatilgan) — doim
    # mavjud, web agent "up"/"down" bilan ishonchli farqlashi uchun
    # (m2b-contract.md §2: "Asterisk yo'q bo'lsa 200 ... `asterisk: down`").
    asterisk: Literal["up", "down"]


class LiveSpyPayload(BaseModel):
    call_id: str | None = None
    channel: str | None = None
    mode: Literal["listen", "whisper", "barge"] = "listen"

    @model_validator(mode="after")
    def _one_of(self) -> "LiveSpyPayload":
        if not self.call_id and not self.channel:
            raise ValueError("call_id yoki channel kerak")
        return self


class LiveSpyOut(BaseModel):
    status: Literal["calling"]


# ======================================================================== raqamlar
class FreeNumbersOut(BaseModel):
    items: list[str]


# ========================================================================== audio
class AudioCreated(BaseModel):
    item: AudioOut


# =================================================================== oqim grafigi
class FlowNode(BaseModel):
    target: RouteTarget
    edge: str | None
    children: list["FlowNode"] = Field(default_factory=list)
    loop: bool = False
    broken: bool = False


class FlowOut(BaseModel):
    root: FlowNode


FlowNode.model_rebuild()


# ============================================================ M1b: chiquvchi
class OutboundPatternIn(BaseModel):
    strip_prefix: str = Field(default="", max_length=20)
    pattern: str = Field(min_length=1, max_length=40)
    add_prefix: str = Field(default="", max_length=20)
    callerid_match: str = Field(default="", max_length=40)

    _check_pattern = field_validator("pattern")(_check_dialplan_number_opt)
    _check_add_prefix = field_validator("add_prefix")(_check_dialplan_number_opt)


class OutboundPatternOut(OutboundPatternIn):
    pass


class TrunkRef(BaseModel):
    id: str
    name: str
    health_state: TrunkHealthState = "unknown"


class OutboundRouteTrunkOut(BaseModel):
    position: int
    trunk: TrunkRef


class ExtensionAllowRef(BaseModel):
    id: str
    number: str
    name: str


class PinSetRef(BaseModel):
    id: str
    name: str


class OutboundRouteOut(BaseModel):
    id: str
    name: str
    priority: int
    enabled: bool
    patterns: list[OutboundPatternOut]
    trunks: list[OutboundRouteTrunkOut]
    callerid: str | None
    override_extension_callerid: bool
    has_pin: bool
    international: bool
    extensions: Literal["all"] | list[ExtensionAllowRef]
    updated_at: datetime
    # M9 B1 (0032): PIN to'plami — yagona `pin`dan tashqari ishlaydi.
    pin_set: PinSetRef | None = None


class CreateOutboundRoutePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    priority: int | None = Field(default=None, ge=1)
    enabled: bool = True
    patterns: list[OutboundPatternIn] = Field(min_length=1)
    trunk_ids: list[str] = Field(min_length=1)
    callerid: str | None = None
    override_extension_callerid: bool = False
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    international: bool = False
    extension_ids: Literal["all"] | list[str] = "all"
    pin_set_id: str | None = None

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_callerid = field_validator("callerid")(_check_dialplan_number_opt)


class UpdateOutboundRoutePayload(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    patterns: list[OutboundPatternIn] | None = None
    trunk_ids: list[str] | None = None
    callerid: str | None = None
    override_extension_callerid: bool | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    pin_clear: bool = False
    international: bool | None = None
    extension_ids: Literal["all"] | list[str] | None = None
    pin_set_id: str | None = None
    pin_set_id_clear: bool = False
    updated_at: datetime

    _check_name = field_validator("name")(_check_no_control_chars)
    _check_callerid = field_validator("callerid")(_check_dialplan_number_opt)


class OutboundRouteMutated(BaseModel):
    item: OutboundRouteOut
    apply: ApplyResult


class ReorderOutboundRoutesPayload(BaseModel):
    ids: list[str] = Field(min_length=1)


class SimulatePayload(BaseModel):
    extension: str
    number: str


class SimulateStepOut(BaseModel):
    route: str
    result: SimulateStepResult
    detail: str


class SimulateRouteRef(BaseModel):
    id: str
    name: str


class SimulateResult(BaseModel):
    allowed: bool
    route: SimulateRouteRef | None
    dialed: str | None
    callerid: str | None
    trunks: list[TrunkRef]
    steps: list[SimulateStepOut]
    reason: str | None


# ============================================================ M1b: sozlamalar
class DetectedNetworkOut(BaseModel):
    public_ip: str | None
    local_ips: list[str]


class SipSettingsOut(BaseModel):
    external_ip: str | None
    external_host: str | None
    local_nets: list[str]
    sip_udp_port: int
    sip_tls_port: int | None
    rtp_start: int
    rtp_end: int
    codecs: list[str]
    detected: DetectedNetworkOut
    restart_required: bool
    updated_at: datetime


class UpdateSipSettingsItem(BaseModel):
    external_ip: str | None = None
    external_host: str | None = None
    local_nets: list[str] | None = None
    sip_udp_port: int | None = None
    sip_tls_port: int | None = None
    rtp_start: int | None = None
    rtp_end: int | None = None
    codecs: list[str] | None = None


class UpdateSipSettingsPayload(BaseModel):
    item: UpdateSipSettingsItem
    apply: bool = True


class SipSettingsMutated(BaseModel):
    item: SipSettingsOut
    apply: ApplyResult


class RestartResult(BaseModel):
    ok: bool
    message: str | None = None


# ====================================================== M1c: SIP TLS (S32 davomi)
BadCertificateReason = Literal["key_mismatch", "expired", "not_pem", "encrypted_key"]


class TlsCertificateOut(BaseModel):
    subject: str
    issuer: str
    not_after: datetime
    self_signed: bool
    fingerprint_sha256: str


class SipTlsOut(BaseModel):
    enabled: bool
    port: int | None
    certificate: TlsCertificateOut | None
    restart_required: bool


class SelfSignedCertPayload(BaseModel):
    common_name: str = Field(min_length=1, max_length=255)


# ================================================================ M1b: audit
class AuditUserRef(BaseModel):
    id: str
    login: str


class AuditEntryOut(BaseModel):
    id: str
    at: datetime
    user: AuditUserRef | None
    action: AuditAction
    entity: str
    entity_id: str | None
    label: str | None
    diff: dict[str, Any]
    ip: str | None


# ======================================================== M1b: konfiguratsiya
class ConfigRevisionDetailOut(BaseModel):
    id: str
    sha256: str
    status: RevisionStatus
    created_at: datetime
    message: str | None
    user: AuditUserRef | None
    summary: str | None
    dialplan: str


class ConfigRevisionDiffOut(BaseModel):
    unified: str


class RestoreRevisionResult(BaseModel):
    item: ConfigRevisionOut
    apply: ApplyResult
    drift: bool = True


# ============================================================= M1b: bosh panel
class TrunkDashboardOut(BaseModel):
    id: str
    name: str
    state: TrunkHealthState
    registration: RegistrationState | None
    reason: str | None


SystemStatusOut.model_rebuild()  # `TrunkDashboardOut` undan keyin e'lon qilingan (forward ref)


class DiskHealthOut(BaseModel):
    used_pct: int
    free_gb: float


class DashboardHealthOut(BaseModel):
    asterisk: AsteriskHealth
    db: DbHealth
    disk: DiskHealthOut
    trunks: list[TrunkDashboardOut]


class LiveCallOut(BaseModel):
    channel: str
    from_: str = Field(alias="from")
    to: str
    state: str
    duration_s: int
    direction: CallDirection

    model_config = {"populate_by_name": True}


class DashboardLiveOut(BaseModel):
    active_calls: int
    calls: list[LiveCallOut]


class DashboardQueueOut(BaseModel):
    id: str
    name: str
    waiting: int
    members_online: int
    longest_wait_s: int


class HourBucketOut(BaseModel):
    hour: int
    in_: int = Field(alias="in")
    out: int
    missed: int

    model_config = {"populate_by_name": True}


class DashboardTodayOut(BaseModel):
    total: int
    answered: int
    missed: int
    out: int
    avg_wait_s: int | None
    by_hour: list[HourBucketOut]


class MissedCallOut(BaseModel):
    uniqueid: str
    started_at: datetime
    src: str
    did: str | None
    called_back: bool


class DashboardAlertOut(BaseModel):
    level: Literal["warn", "danger"]
    code: str
    text: str
    link: str


class DashboardOut(BaseModel):
    health: DashboardHealthOut
    live: DashboardLiveOut
    queues: list[DashboardQueueOut]
    today: DashboardTodayOut
    missed: list[MissedCallOut]
    alerts: list[DashboardAlertOut]


# ================================================================== M1b: MOH
class MohClassRef(BaseModel):
    id: str
    name: str


class MohClassOut(BaseModel):
    """`web/src/api/types.ts` `MohClass` bilan AYNAN BIR XIL shakl — qo'shimcha
    maydon YO'Q (`default` sinfni o'chirib bo'lmasligi `name == "default"`
    orqali aniqlanadi, xuddi `web/src/api/fake.ts` qilgani kabi — ikkita joyda
    bitta qoida)."""
    id: str
    name: str
    shuffle: bool
    files: list[AudioOut]
    updated_at: datetime


class CreateMohClassPayload(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    shuffle: bool = False
    file_ids: list[str] = Field(default_factory=list)


class UpdateMohClassPayload(BaseModel):
    name: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,32}$")
    shuffle: bool | None = None
    file_ids: list[str] | None = None
    updated_at: datetime


class MohClassMutated(BaseModel):
    item: MohClassOut
    apply: ApplyResult


# =============================================================== M8: tarmoq sozlamalari
# m8-network-contract.md bo'lim 4 — maydon nomlari FRONTEND bilan bitta manba
# (shartnoma); IP/interfeys maydonlari bu yerda HAM tekshiriladi (chegara
# intizomi: `ipaddress`/regex — birinchi himoya chizig'i), to'liq biznes
# qoidalari (subnet/shlyuz mosligi va h.k.) `app/netd/validate.py`da.
#
# FAQAT IPv4: konfiguratsiya yozuvchi tomon (`netd/ifupdown.py`, klassik
# `address`/`netmask`) IPv6ga mo'ljallanmagan — `live_ipv6` faqat O'QISH
# uchun (joriy holatni ko'rsatish). IPv6ning scope-id qismi
# (`fe80::1%zone`) ichida bo'sh joy/qator ko'chirish TAQIQLANMAGAN —
# `ipaddress.ip_interface`/`ip_address` buni QABUL QILADI va xom satrni
# o'zgartirmay saqlaydi; shu orqali netd yozadigan
# `/etc/network/interfaces`ga `pre-up`/`up` qatori in'eksiya qilinishi
# mumkin edi (admin -> root RCE). IPv4-only + `ValueError` o'rniga KANONIK
# `str(...)` qaytarish bu yo'lni butunlay yopadi.
_IFACE_NAME_RE = r"^[a-zA-Z0-9_.:-]{1,15}$"
_UNSAFE_CHARS_RE = re.compile(r"[\s%\x00-\x1f\x7f]")
NetworkMode = Literal["dhcp", "static"]


def _reject_unsafe_chars(value: str) -> None:
    if _UNSAFE_CHARS_RE.search(value):
        raise ValueError("maydonda bo'sh joy, boshqaruv belgisi yoki '%' ruxsat etilmagan")


def _check_ip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    _reject_unsafe_chars(value)
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError as exc:
        raise ValueError("yaroqsiz IPv4 manzil") from exc


def _check_cidr_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    _reject_unsafe_chars(value)
    try:
        return str(ipaddress.IPv4Interface(value))
    except ValueError as exc:
        raise ValueError("yaroqsiz IPv4 CIDR manzil (masalan 10.0.0.5/24)") from exc


def _check_hostname(value: str) -> str:
    if not is_valid_hostname(value):
        raise ValueError("Mezbon nomi RFC1123 talablariga mos emas")
    return value


class NetworkInterfaceIn(BaseModel):
    name: str = Field(pattern=_IFACE_NAME_RE)
    mode: NetworkMode
    address: str | None = Field(default=None, description="CIDR, masalan 10.0.0.5/24")
    gateway: str | None = None
    mtu: int | None = Field(default=None, ge=68, le=9000)

    _check_address = field_validator("address")(classmethod(lambda cls, v: _check_cidr_or_none(v)))
    _check_gateway = field_validator("gateway")(classmethod(lambda cls, v: _check_ip_or_none(v)))


class NetworkRouteIn(BaseModel):
    destination: str = Field(description="CIDR, masalan 10.1.0.0/24")
    gateway: str | None = None
    interface: str | None = Field(default=None, pattern=_IFACE_NAME_RE)
    metric: int | None = Field(default=None, ge=0, le=65535)

    _check_destination = field_validator("destination")(classmethod(lambda cls, v: _check_cidr_or_none(v)))
    _check_gateway = field_validator("gateway")(classmethod(lambda cls, v: _check_ip_or_none(v)))


class NetworkDnsIn(BaseModel):
    servers: list[str] = Field(default_factory=list, max_length=4)
    search: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("servers")
    @classmethod
    def _check_servers(cls, value: list[str]) -> list[str]:
        return [_check_ip_or_none(server) for server in value]

    @field_validator("search")
    @classmethod
    def _check_search(cls, value: list[str]) -> list[str]:
        for domain in value:
            if not isinstance(domain, str) or not is_valid_hostname(domain):
                raise ValueError("yaroqsiz domen nomi (RFC1123, <=253 belgi)")
        return value


class NetworkConfigIn(BaseModel):
    hostname: str = Field(min_length=1, max_length=253)
    interfaces: list[NetworkInterfaceIn]
    routes: list[NetworkRouteIn] = Field(default_factory=list)
    dns: NetworkDnsIn = Field(default_factory=NetworkDnsIn)
    timeout_s: int = Field(default=180, ge=60, le=600)

    _check_hostname = field_validator("hostname")(classmethod(lambda cls, v: _check_hostname(v)))


class NetworkPendingActionIn(BaseModel):
    pending_id: str = Field(min_length=1, max_length=64)


class NetworkInterfaceConfigOut(BaseModel):
    mode: str
    address: str | None
    gateway: str | None
    mtu: int | None


class NetworkInterfaceOut(BaseModel):
    name: str
    mac: str | None
    kind: str
    oper_state: str
    carrier: bool
    speed_mbps: int | None
    mtu: int
    live_ipv4: list[str]
    live_ipv6: list[str]
    editable: bool
    config: NetworkInterfaceConfigOut


class NetworkRouteOut(BaseModel):
    destination: str
    gateway: str | None
    interface: str | None
    metric: int | None


class NetworkLiveRouteOut(BaseModel):
    destination: str
    gateway: str | None
    interface: str | None
    metric: int | None
    protocol: str | None


class NetworkRoutesOut(BaseModel):
    static: list[NetworkRouteOut]
    live: list[NetworkLiveRouteOut]


class NetworkDnsOut(BaseModel):
    servers: list[str]
    search: list[str]
    editable: bool


class NetworkDefaultGatewayOut(BaseModel):
    address: str | None
    interface: str | None


class NetworkPendingOut(BaseModel):
    id: str
    applied_at: datetime
    expires_at: datetime
    summary: list[str]


class NetworkLastResultOut(BaseModel):
    kind: str
    at: datetime
    message: str | None


class NetworkHelperOut(BaseModel):
    available: bool
    version: str | None
    error: str | None


class NetworkStateOut(BaseModel):
    helper: NetworkHelperOut
    backend: str
    editable: bool
    readonly_reason: str | None
    hostname: str
    dns: NetworkDnsOut
    default_gateway: NetworkDefaultGatewayOut
    interfaces: list[NetworkInterfaceOut]
    routes: NetworkRoutesOut


# ============================================================ M9 B1: PIN to'plamlari
class PinSetUsageRef(BaseModel):
    id: str
    name: str


class PinSetOut(BaseModel):
    id: str
    name: str
    record_in_cdr: bool
    pin_count: int
    used_by: list[PinSetUsageRef]
    updated_at: datetime


class CreatePinSetPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    record_in_cdr: bool = True


class UpdatePinSetPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    record_in_cdr: bool | None = None
    updated_at: datetime


class PinItemOut(BaseModel):
    id: str
    label: str


class PinItemsOut(BaseModel):
    # DIQQAT: frontend (`web/src/api/real.ts`/`client.ts`) PIN ro'yxatini
    # HAR DOIM `{items: [...]}` shaklida kutadi (xuddi `list_pin_sets` kabi) --
    # ILGARI bu yer`da `response_model=list[PinItemOut]` (yalang'och massiv)
    # qaytarilardi, shu sabab brauzerda `res.items` -> `undefined` bo'lib,
    # `<PinsDrawer>`ni "Cannot read properties of undefined (reading 'length')"
    # xatosi bilan qulatardi (jonli isbotda topilgan haqiqiy ildiz sabab).
    items: list[PinItemOut]


class PinItemIn(BaseModel):
    pin: str = Field(pattern=r"^\d{4,12}$")
    label: str = Field(min_length=1, max_length=128)


class AddPinsPayload(BaseModel):
    pins: list[PinItemIn] = Field(min_length=1)


# ============================================================ M9 B2: Telefon kitobi
class PhonebookNumberIn(BaseModel):
    number: str = Field(min_length=1, max_length=40)
    label: str | None = Field(default=None, max_length=64)


class PhonebookNumberOut(BaseModel):
    id: str
    number: str
    label: str | None = None


class PhonebookContactOut(BaseModel):
    id: str
    name: str
    company: str | None = None
    note: str | None = None
    numbers: list[PhonebookNumberOut]
    updated_at: datetime


class CreatePhonebookContactPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    company: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=512)
    numbers: list[PhonebookNumberIn] = Field(default_factory=list)


class UpdatePhonebookContactPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    company: str | None = None
    note: str | None = None
    numbers: list[PhonebookNumberIn] | None = None
    updated_at: datetime


class PhonebookContactMutated(BaseModel):
    item: PhonebookContactOut


class PhonebookImportError(BaseModel):
    row: int
    message: str


class PhonebookImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[PhonebookImportError]


# ============================================================ M9 B2: CID Lookup manbalari
class CidSourceUsageRef(BaseModel):
    id: str
    name: str


class CidSourceOut(BaseModel):
    id: str
    name: str
    kind: Literal["phonebook", "crm", "http"]
    http_url: str | None = None
    http_json_path: str | None = None
    timeout_ms: int
    cache_ttl_s: int
    enabled: bool
    used_by: list[CidSourceUsageRef]
    updated_at: datetime


class CreateCidSourcePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["phonebook", "crm", "http"]
    http_url: str | None = None
    http_json_path: str | None = Field(default=None, max_length=256)
    timeout_ms: int = Field(default=1500, ge=300, le=3000)
    cache_ttl_s: int = Field(default=3600, ge=0, le=86400)
    enabled: bool = True


class UpdateCidSourcePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    kind: Literal["phonebook", "crm", "http"] | None = None
    http_url: str | None = None
    http_json_path: str | None = Field(default=None, max_length=256)
    timeout_ms: int | None = Field(default=None, ge=300, le=3000)
    cache_ttl_s: int | None = Field(default=None, ge=0, le=86400)
    enabled: bool | None = None
    updated_at: datetime


class CidSourceMutated(BaseModel):
    item: CidSourceOut


class CidSourceTestPayload(BaseModel):
    number: str = Field(min_length=1, max_length=40)


class CidSourceTestResult(BaseModel):
    name: str | None = None
    ms: int
    error: str | None = None


# ============================================================ M9 B4: ichki raqamlar CSV
class ExtensionImportRow(BaseModel):
    row: int
    number: str
    action: Literal["create", "update", "skip", "error"]
    message: str | None = None


class ExtensionImportResult(BaseModel):
    rows: list[ExtensionImportRow]
    created: int
    updated: int
    errors: int
    secrets_csv: str | None = None


class NetworkFieldErrorOut(BaseModel):
    field: str
    message: str


class NetworkValidateOut(BaseModel):
    ok: bool
    errors: list[NetworkFieldErrorOut]
    warnings: list[str]
    diff: list[str]


# ============================================================ M12 B1: sana/vaqt
class TimeConfigIn(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)
    ntp_servers: list[str] = Field(default_factory=list, max_length=5)
    ntp_enabled: bool = True

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError("Vaqt zonasi IANA ro'yxatida topilmadi")
        return value

    @field_validator("ntp_servers")
    @classmethod
    def _check_ntp_servers(cls, value: list[str]) -> list[str]:
        for server in value:
            if not is_valid_ntp_server(server):
                raise ValueError(f"Yaroqsiz NTP server: {server!r}")
        return value


class TimeStateOut(BaseModel):
    now_utc: datetime
    timezone: str
    ntp_enabled: bool
    ntp_servers: list[str]
    # Admin ro'yxati bo'sh/javobsiz bo'lsa ishlatiladigan mintaqa pool'i (`FallbackNTP=`).
    default_ntp_servers: list[str] = Field(default_factory=list)
    synced: bool
    # NTP javobi kelgan server (timesyncd); javob yo'q / chrony — None.
    sync_server: str | None = None
    backend: str
    readonly_reason: str | None
    # PUT: vaqt zonasi o'zgarib dialplan qayta qo'llangan bo'lsa — natija.
    apply: ApplyResult | None = None


# ============================================================ M12 B2: qayta yuklash/o'chirish
class PowerStatusOut(BaseModel):
    hostname: str
    active_calls: int | None
    readonly_reason: str | None


class PowerActionIn(BaseModel):
    """Faqat qayta yuklash (o'chirish UI'dan olib tashlangan — masofadan qayta yoqib bo'lmaydi);
    `confirm` — qo'lda yozilgan `reboot` so'zi."""
    action: Literal["reboot"]
    confirm: str = Field(min_length=1, max_length=32)


class PowerActionOut(BaseModel):
    action: str
    delay_s: float
    scheduled: bool
    active_calls: int | None


# ============================================================ M12 B3: firewall GUI
class FirewallServiceIn(BaseModel):
    name: Literal["ssh", "web", "sip", "rtp"]
    mode: Literal["all", "allowlist"]
    allow: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("allow")
    @classmethod
    def _check_allow(cls, value: list[str]) -> list[str]:
        for cidr in value:
            if not is_valid_cidr(cidr):
                raise ValueError(f"Yaroqsiz IPv4 CIDR: {cidr!r}")
        return value


class FirewallConfigIn(BaseModel):
    services: list[FirewallServiceIn] = Field(min_length=len(SERVICE_NAMES), max_length=len(SERVICE_NAMES))
    blocked_cidrs: list[str] = Field(default_factory=list, max_length=100)
    timeout_s: int = Field(default=120, ge=30, le=600)

    @field_validator("blocked_cidrs")
    @classmethod
    def _check_blocked(cls, value: list[str]) -> list[str]:
        for cidr in value:
            if not is_valid_cidr(cidr):
                raise ValueError(f"Yaroqsiz IPv4 CIDR: {cidr!r}")
        return value


class FirewallPendingActionIn(BaseModel):
    pending_id: str = Field(min_length=1, max_length=64)


class FirewallServiceOut(BaseModel):
    name: str
    mode: str
    allow: list[str]


class FirewallPendingOut(BaseModel):
    id: str
    applied_at: datetime
    expires_at: datetime
    summary: list[str]


class FirewallLastResultOut(BaseModel):
    kind: str
    at: datetime
    message: str | None


class FirewallStateOut(BaseModel):
    services: list[FirewallServiceOut]
    blocked_cidrs: list[str]
    readonly_reason: str | None
    pending: FirewallPendingOut | None
    last_result: FirewallLastResultOut | None


class FirewallValidateOut(BaseModel):
    ok: bool
    errors: list[NetworkFieldErrorOut]
    warnings: list[str]
    diff: list[str]


# ================================================================== M9 A1: e'lonlar
class AnnouncementOut(BaseModel):
    id: str
    name: str
    audio: AudioOut
    allow_skip: bool
    repeat_key: str | None
    answer: bool
    next_target: RouteTarget
    updated_at: datetime


class CreateAnnouncementPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    audio_file_id: str
    allow_skip: bool = False
    repeat_key: str | None = Field(default=None, pattern=r"^[0-9*#]$")
    answer: bool = True
    next_target_id: str


class UpdateAnnouncementPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    audio_file_id: str | None = None
    allow_skip: bool | None = None
    repeat_key: str | None = Field(default=None, pattern=r"^[0-9*#]$")
    answer: bool | None = None
    next_target_id: str | None = None
    updated_at: datetime


class AnnouncementMutated(BaseModel):
    item: AnnouncementOut
    apply: ApplyResult


# ============================================================ M9 A2: boshqa manzil/ilova
class MiscDestinationOut(BaseModel):
    id: str
    name: str
    dial: str
    updated_at: datetime


class CreateMiscDestinationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dial: str = Field(pattern=r"^[0-9*#+]{1,32}$")


class UpdateMiscDestinationPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    dial: str | None = Field(default=None, pattern=r"^[0-9*#+]{1,32}$")
    updated_at: datetime


class MiscDestinationMutated(BaseModel):
    item: MiscDestinationOut
    apply: ApplyResult


class MiscApplicationOut(BaseModel):
    id: str
    name: str
    code: str
    target: RouteTarget
    enabled: bool
    updated_at: datetime


class CreateMiscApplicationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(pattern=r"^(\*[0-9*#]{1,6}|[0-9]{1,10})$")
    target_id: str
    enabled: bool = True


class UpdateMiscApplicationPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    code: str | None = Field(default=None, pattern=r"^(\*[0-9*#]{1,6}|[0-9]{1,10})$")
    target_id: str | None = None
    enabled: bool | None = None
    updated_at: datetime


class MiscApplicationMutated(BaseModel):
    item: MiscApplicationOut
    apply: ApplyResult


# =============================================================== M9 A3: parking sozlamalari
class ParkingSettingsOut(BaseModel):
    """Yagona (tenant uchun bitta) yozuv — `POST` yo'q, faqat `GET`/`PUT`."""
    lot_number: str
    first_slot: int
    slot_count: int
    timeout_s: int
    on_timeout: Literal["origin", "target"]
    timeout_target: RouteTarget | None
    moh_class: MohClassRef | None
    updated_at: datetime


class UpdateParkingSettingsPayload(BaseModel):
    lot_number: str | None = Field(default=None, pattern=r"^[0-9*#]{1,10}$")
    first_slot: int | None = Field(default=None, ge=1)
    slot_count: int | None = Field(default=None, ge=1, le=100)
    timeout_s: int | None = Field(default=None, ge=10, le=3600)
    on_timeout: Literal["origin", "target"] | None = None
    timeout_target_id: str | None = None
    moh_class_id: str | None = None
    updated_at: datetime


class ParkingSettingsMutated(BaseModel):
    item: ParkingSettingsOut
    apply: ApplyResult


# ================================================================ M9 A4: paging/intercom
class PageGroupOut(BaseModel):
    id: str
    name: str
    number: str
    members: list[ExtensionRef]
    duplex: bool
    skip_busy: bool
    beep: bool
    updated_at: datetime


class CreatePageGroupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    number: str = Field(pattern=r"^[0-9*#]{1,10}$")
    member_extension_ids: list[str] = Field(default_factory=list)
    duplex: bool = False
    skip_busy: bool = True
    beep: bool = True


class UpdatePageGroupPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    number: str | None = Field(default=None, pattern=r"^[0-9*#]{1,10}$")
    member_extension_ids: list[str] | None = None
    duplex: bool | None = None
    skip_busy: bool | None = None
    beep: bool | None = None
    updated_at: datetime


class PageGroupMutated(BaseModel):
    item: PageGroupOut
    apply: ApplyResult


QueueOut.model_rebuild()


UserOut.model_rebuild()  # `ExtensionRef` UserOut'dan keyin e'lon qilingan (forward ref)


# ================================================================ M10 A1: qayta chaqirish vidjeti
class CallbackWidgetOut(BaseModel):
    id: str
    name: str
    public_key: str
    target: RouteTarget
    allowed_origins: list[str]
    time_group_id: str | None = None
    time_group_name: str | None = None
    offhours_mode: Literal["reject", "schedule"]
    max_attempts: int
    retry_interval_s: int
    callerid_prefix: str | None = None
    allow_international: bool
    appearance: dict
    enabled: bool
    # Bo'sh — `public_base_url` sozlanmagan (UI ogohlantiradi, 409 EMAS).
    embed_snippet: str | None = None
    updated_at: datetime


class CreateCallbackWidgetPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    target_id: str
    allowed_origins: list[str] = Field(default_factory=list)
    time_group_id: str | None = None
    offhours_mode: Literal["reject", "schedule"] = "schedule"
    max_attempts: int = Field(default=2, ge=1, le=5)
    retry_interval_s: int = Field(default=120, ge=60, le=1800)
    callerid_prefix: str | None = Field(default=None, max_length=16)
    allow_international: bool = False
    appearance: dict = Field(default_factory=dict)
    enabled: bool = True


class UpdateCallbackWidgetPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    target_id: str | None = None
    allowed_origins: list[str] | None = None
    time_group_id: str | None = None
    offhours_mode: Literal["reject", "schedule"] | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=5)
    retry_interval_s: int | None = Field(default=None, ge=60, le=1800)
    callerid_prefix: str | None = Field(default=None, max_length=16)
    allow_international: bool | None = None
    appearance: dict | None = None
    enabled: bool | None = None
    updated_at: datetime


class CallbackWidgetMutated(BaseModel):
    item: CallbackWidgetOut
    apply: ApplyResult


class RotateWidgetKeyResult(BaseModel):
    item: CallbackWidgetOut
    apply: ApplyResult


class CallbackRequestOut(BaseModel):
    id: str
    widget_id: str
    widget_name: str
    phone: str
    name: str | None = None
    page_url: str | None = None
    status: str
    attempts: int
    next_attempt_at: datetime | None = None
    linkedid: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Ommaviy (JWT'siz) vidjet endpointlari — `api/public_widget.py`
class PublicWidgetConfig(BaseModel):
    name: str
    appearance: dict
    allow_international: bool


class PublicCallbackPayload(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    # Honeypot — bo'lsa botga 200 OK (jim) qaytariladi, yozuv yaratilmaydi.
    hp: str = Field(default="", max_length=64)


class PublicCallbackAccepted(BaseModel):
    accepted: bool
    message: str


# ================================================================ M10 A2: o'tkazib yuborilgan qo'ng'iroq bildirishnomasi
class MissedCallRuleOut(BaseModel):
    id: str
    name: str
    scope_kind: Literal["any", "did", "queue", "ring_group", "extension"]
    scope_value: str | None = None
    scope_label: str | None = None
    telegram_chat_ids: list[str]
    emails: list[str]
    include_internal: bool
    enabled: bool
    updated_at: datetime


class CreateMissedCallRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scope_kind: Literal["any", "did", "queue", "ring_group", "extension"] = "any"
    scope_value: str | None = None
    telegram_chat_ids: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    include_internal: bool = False
    enabled: bool = True


class UpdateMissedCallRulePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    scope_kind: Literal["any", "did", "queue", "ring_group", "extension"] | None = None
    scope_value: str | None = None
    telegram_chat_ids: list[str] | None = None
    emails: list[str] | None = None
    include_internal: bool | None = None
    enabled: bool | None = None
    updated_at: datetime


class MissedCallRuleMutated(BaseModel):
    item: MissedCallRuleOut


class MissedCallRuleTestResult(BaseModel):
    ok: bool
    message: str


class MissedCallNoticeOut(BaseModel):
    id: int
    rule_id: str
    rule_name: str
    call_id: str
    status: Literal["pending", "sent", "failed"]
    last_error: str | None = None
    attempts: int
    created_at: datetime
    sent_at: datetime | None = None


# ================================================================ M10 A3: Yandex SpeechKit TTS
class TtsSettingsOut(BaseModel):
    provider: Literal["none", "yandex"]
    has_api_key: bool
    folder_id: str | None = None
    voices: dict
    # `NotifySettingsOut` qolipi — qator hali yaratilmagan bo'lsa (yangi tenant) `None` (frontend-check: 500 topildi, tuzatildi).
    updated_at: datetime | None = None


class UpdateTtsSettingsPayload(BaseModel):
    provider: Literal["none", "yandex"] | None = None
    folder_id: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    voices: dict | None = None
    updated_at: datetime | None = None


class TtsSettingsMutated(BaseModel):
    item: TtsSettingsOut


class TtsTestResult(BaseModel):
    ok: bool
    message: str


class TtsSynthesizePayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    name: str = Field(min_length=1, max_length=128)


class TtsPreviewPayload(BaseModel):
    text: str = Field(min_length=1, max_length=500)
