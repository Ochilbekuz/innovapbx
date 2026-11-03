"""M10 Bo'lak B1 — Sifat baholash (QA) Pydantic sxemalari."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QaCriterionKind = Literal["yesno", "scale5"]


class QaCriterionIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    kind: QaCriterionKind
    weight: float = Field(default=1.0, gt=0)
    critical: bool = False


class QaCriterionOut(BaseModel):
    id: str
    label: str
    kind: QaCriterionKind
    weight: float
    critical: bool
    position: int


class CreateQaChecklistPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    criteria: list[QaCriterionIn] = Field(min_length=1)


class UpdateQaChecklistPayload(BaseModel):
    """Berilmagan maydon o'zgarmaydi; `criteria` berilsa — TO'LIQ almashtiradi
    (qisman qo'shish/o'chirish emas — `pinsets.py`dagi pin ro'yxati naqshidan
    farqli, chunki mezon tartibi/og'irligi bir butun sifatida tahrirlanadi)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    criteria: list[QaCriterionIn] | None = None
    updated_at: datetime


class QaChecklistOut(BaseModel):
    id: str
    name: str
    is_active: bool
    criteria: list[QaCriterionOut]
    updated_at: datetime


class QaChecklistsOut(BaseModel):
    items: list[QaChecklistOut]


class CreateQaEvaluationPayload(BaseModel):
    checklist_id: str
    call_id: str = Field(min_length=1, max_length=128)
    extension_id: str | None = None
    answers: dict[str, bool | int] = Field(min_length=1)
    comment: str | None = None


class UpdateQaEvaluationPayload(BaseModel):
    answers: dict[str, bool | int] | None = None
    comment: str | None = None
    updated_at: datetime


class QaEvaluationOut(BaseModel):
    id: str
    checklist_id: str
    checklist_name: str
    call_id: str
    extension_id: str | None
    evaluator_id: str | None
    evaluator_name: str | None
    answers: dict[str, bool | int]
    comment: str | None
    score_pct: float
    created_at: datetime
    updated_at: datetime


class QaEvaluationsOut(BaseModel):
    items: list[QaEvaluationOut]
    total: int


class QaSummaryByExtension(BaseModel):
    extension_id: str | None
    extension_number: str | None
    count: int
    avg_score_pct: float


class QaSummaryOut(BaseModel):
    count: int
    avg_score_pct: float
    by_extension: list[QaSummaryByExtension]
