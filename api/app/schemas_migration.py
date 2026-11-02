"""M5a — `/migration/freepbx` (FreePBX'dan ko'chirish). `/tmp/backend-brief.txt`
§«Qilinadigan ish» 3-band: maydon nomlari/shakllari AYNAN shunga mos (frontend
shu kontraktga yoziladi). `payload` BU YERDA YO'Q — faqat ommaviy maydonlar
(`app/services/fpbx/mappers/__init__.py::Entry.public_dict()`)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

MigrationSource = Literal["upload", "ssh"]
MigrationStatus = Literal["uploaded", "fetching", "analyzing", "analyzed", "applying", "ok", "failed"]
PlanAction = Literal["create", "skip", "conflict", "unsupported", "replace"]
PatchAction = Literal["skip", "replace", "create"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceMetaOut(BaseModel):
    file_name: str | None = None
    size_bytes: int | None = None
    host: str | None = None
    freepbx_version: str | None = None
    asterisk_version: str | None = None
    created_at: str | None = None


class ByKindSummaryOut(BaseModel):
    create: int = 0
    skip: int = 0
    conflict: int = 0
    unsupported: int = 0


class SummaryOut(BaseModel):
    by_kind: dict[str, ByKindSummaryOut]
    warnings: int
    ignored: int
    weak_secrets: int


class OptionsOut(BaseModel):
    rotate_weak_secrets: bool = False


class ResultOut(BaseModel):
    created: dict[str, int]
    skipped: int
    warnings: int
    revision_id: str | None


class JobErrorOut(BaseModel):
    code: str
    message: str


class JobOut(BaseModel):
    id: str
    source: MigrationSource
    status: MigrationStatus
    step: str | None
    progress: int | None
    source_meta: SourceMetaOut | None
    summary: SummaryOut | None
    options: OptionsOut
    result: ResultOut | None
    error: JobErrorOut | None
    pre_import_backup_id: str | None
    backup_ready: bool
    created_by: str | None
    created_at: datetime
    finished_at: datetime | None


class JobItem(BaseModel):
    item: JobOut


class JobList(BaseModel):
    items: list[JobOut]


class PlanWarningOut(BaseModel):
    code: str
    message: str


class PlanItemOut(BaseModel):
    kind: str
    source_ref: str
    name: str
    number: str | None
    action: PlanAction
    reason: str | None
    warnings: list[PlanWarningOut]
    depends_on: list[str]
    replaceable: bool
    has_secret: bool
    weak_secret: bool


class PlanItemList(BaseModel):
    items: list[PlanItemOut]
    total: int


class IgnoredItemOut(BaseModel):
    table: str
    key: str
    reason: str


class IgnoredList(BaseModel):
    items: list[IgnoredItemOut]


class WarningItemOut(BaseModel):
    code: str
    message: str
    source_ref: str | None = None


class WarningList(BaseModel):
    items: list[WarningItemOut]


class PatchPlanItem(_Strict):
    kind: str
    source_ref: str
    action: PatchAction


class PatchPlanPayload(_Strict):
    items: list[PatchPlanItem]


class ApplyOptionsIn(_Strict):
    rotate_weak_secrets: bool = False


class ApplyPayload(_Strict):
    """`confirm` ixtiyoriy — yo'q/noto'g'ri bo'lsa 422 `confirm_required` (validatsiya xatosi emas)."""

    confirm: str | None = None
    options: ApplyOptionsIn = ApplyOptionsIn()
