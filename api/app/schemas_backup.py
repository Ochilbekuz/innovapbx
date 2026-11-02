"""M4b — `/backups`, `/settings/backup` (replica/m4b-contract.md §2).

Maydon nomlari/literal qiymatlari `web/src/api/types.ts` (990-1114 qatorlar) bilan
BAYT-BAYTGA mos — UI shu kontraktga qarshi allaqachon yozilgan."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BackupKind = Literal["scheduled", "manual", "pre_restore", "uploaded", "pre_import"]
BackupStatus = Literal["running", "ok", "partial", "failed"]
BackupComponent = Literal["config", "history", "sounds", "voicemail", "recordings", "certs"]
BackupTargetKind = Literal["local", "s3", "sftp"]
BackupCopyStatus = Literal["pending", "ok", "failed", "deleted"]
BackupJobKind = Literal["backup", "restore"]
BackupJobStatus = Literal["running", "ok", "failed"]
RestoreJobSource = Literal["local", "upload"]
RestoreJobStatus = Literal["running", "ok", "failed"]
BackupScheduleFrequency = Literal["daily", "weekly"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRef(BaseModel):
    id: str
    login: str


class BackupCopyOut(BaseModel):
    target: BackupTargetKind
    status: BackupCopyStatus
    remote_path: str | None
    size_bytes: int | None
    error: str | None
    uploaded_at: datetime | None


class BackupManifestPart(BaseModel):
    name: str
    size: int
    sha256: str


class BackupManifestOut(BaseModel):
    format: str
    product_version: str
    alembic_revision: str
    created_at: datetime
    source_host: str
    components: list[BackupComponent]
    parts: list[BackupManifestPart]
    db_key_fp: str


class BackupOut(BaseModel):
    id: str
    kind: BackupKind
    status: BackupStatus
    components: list[BackupComponent]
    step: str | None
    progress: int | None
    file_name: str | None
    sha256: str | None
    manifest: BackupManifestOut | None
    size_bytes: int | None
    copies: list[BackupCopyOut]
    created_by: UserRef | None
    created_at: datetime


class BackupList(BaseModel):
    items: list[BackupOut]


class BackupItem(BaseModel):
    item: BackupOut


class CreateBackupPayload(_Strict):
    components: list[BackupComponent] = Field(min_length=1)


class BackupJobOut(BaseModel):
    kind: BackupJobKind
    id: str


class BackupJobResponse(BaseModel):
    job: BackupJobOut


class BackupJobState(BaseModel):
    kind: BackupJobKind
    status: BackupJobStatus
    step: str | None
    progress: int | None
    error: str | None


class InspectBackupPayload(_Strict):
    passphrase: str | None = None


class InspectChecks(BaseModel):
    sha256: Literal["ok"]


class InspectBackupResult(BaseModel):
    manifest: BackupManifestOut
    checks: InspectChecks
    compatible: bool
    warnings: list[str]


class RestoreBackupPayload(_Strict):
    passphrase: str | None = None
    confirm: Literal["TIKLASH"]
    force: bool = False


class RestoreJobOut(BaseModel):
    id: str
    backup_id: str | None
    source: RestoreJobSource
    status: RestoreJobStatus
    step: str | None
    progress: int | None
    error: str | None
    force: bool
    pre_restore_backup_id: str | None
    started_by: UserRef | None
    started_at: datetime
    finished_at: datetime | None


class RestoreJobList(BaseModel):
    items: list[RestoreJobOut]


# ------------------------------------------------------------------ /settings/backup
class BackupScheduleOut(BaseModel):
    enabled: bool
    frequency: BackupScheduleFrequency
    weekday: int = Field(ge=0, le=6)
    time: str
    components: list[BackupComponent]


class BackupLocalTargetOut(BaseModel):
    keep_last: int


class BackupS3TargetOut(BaseModel):
    enabled: bool
    endpoint: str
    region: str
    bucket: str
    prefix: str
    access_key: str
    has_secret_key: bool
    path_style: bool
    keep_last: int


class BackupSftpTargetOut(BaseModel):
    enabled: bool
    host: str
    port: int
    user: str
    has_password: bool
    has_key: bool
    folder: str
    host_key_fp: str | None
    keep_last: int


class BackupTargetsOut(BaseModel):
    local: BackupLocalTargetOut
    s3: BackupS3TargetOut
    sftp: BackupSftpTargetOut


class BackupSettingsOut(BaseModel):
    has_passphrase: bool
    schedule: BackupScheduleOut
    targets: BackupTargetsOut
    updated_at: datetime


class BackupScheduleIn(_Strict):
    enabled: bool
    frequency: BackupScheduleFrequency
    weekday: int = Field(ge=0, le=6)
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    components: list[BackupComponent] = Field(min_length=1)


class BackupLocalTargetIn(_Strict):
    keep_last: int = Field(ge=1, le=365)


class BackupS3TargetIn(_Strict):
    enabled: bool
    endpoint: str
    region: str
    bucket: str
    prefix: str
    access_key: str
    path_style: bool
    keep_last: int = Field(ge=1, le=365)
    secret_key: str | None = None


class BackupSftpTargetIn(_Strict):
    enabled: bool
    host: str
    port: int = Field(ge=1, le=65535)
    user: str
    folder: str
    keep_last: int = Field(ge=1, le=365)
    password: str | None = None
    key: str | None = None


class BackupTargetsIn(_Strict):
    local: BackupLocalTargetIn | None = None
    s3: BackupS3TargetIn | None = None
    sftp: BackupSftpTargetIn | None = None


class UpdateBackupSettingsPayload(_Strict):
    schedule: BackupScheduleIn | None = None
    targets: BackupTargetsIn | None = None
    updated_at: datetime


class UpdateBackupPassphrasePayload(_Strict):
    passphrase: str = Field(min_length=12, max_length=256)
    current: str | None = None


class TestBackupTargetPayload(_Strict):
    target: Literal["s3", "sftp"]


class TestBackupTargetResult(BaseModel):
    ok: bool
    error: str | None = None
    host_key_fp: str | None = None


class TrustSftpHostKeyPayload(_Strict):
    host_key_fp: str
