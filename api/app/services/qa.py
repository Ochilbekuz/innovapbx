"""M10 Bo'lak B1 — Sifat baholash DB-bog'liq yordamchilar.

Sof ball hisobi `app/services/qa_scoring.py`da; bu yerda faqat DB bilan
ishlash: `/calls` ro'yxatiga belgi biriktirish (bulk, N+1 YO'Q — `attach_recordings`
bilan bir xil naqsh), `QaEvaluation` dan mezonlar chiqarib ball qayta hisoblash."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import QaChecklist, QaCriterion, QaEvaluation
from app.schemas import CallQaBadge
from app.services.qa_scoring import Answer, Criterion, score_pct


def criteria_from_checklist(checklist: QaChecklist) -> list[Criterion]:
    return [Criterion(id=str(c.id), kind=c.kind, weight=c.weight, critical=c.critical)
            for c in checklist.criteria]


def answers_from_payload(raw: dict[str, bool | int]) -> list[Answer]:
    return [Answer(criterion_id=cid, value=value) for cid, value in raw.items()]


def compute_score_pct(checklist: QaChecklist, answers: dict[str, bool | int]) -> float:
    return float(score_pct(criteria_from_checklist(checklist), answers_from_payload(answers)))


async def attach_qa(session: AsyncSession, tenant_id: str, calls: list) -> list:
    """`/calls` sahifasidagi qo'ng'iroqlarga ENG OXIRGI baholash belgisini
    (`qa: {evaluation_id, checklist_name, score_pct} | None`) biriktiradi —
    bitta bulk so'rov (linkedid ro'yxati bo'yicha `IN`), N+1 YO'Q."""
    call_ids = sorted({c.linkedid for c in calls if c.linkedid})
    if not call_ids:
        for call in calls:
            call.qa = None
        return calls

    rows = (await session.execute(
        select(QaEvaluation).where(QaEvaluation.tenant_id == tenant_id, QaEvaluation.call_id.in_(call_ids))
        .options(selectinload(QaEvaluation.checklist))
        .order_by(QaEvaluation.call_id, QaEvaluation.created_at.desc())
    )).scalars().all()

    latest_by_call: dict[str, QaEvaluation] = {}
    for row in rows:
        latest_by_call.setdefault(row.call_id, row)  # birinchi uchragani — created_at DESC bo'yicha eng yangisi

    for call in calls:
        evaluation = latest_by_call.get(call.linkedid or "")
        call.qa = (
            CallQaBadge(evaluation_id=str(evaluation.id), checklist_name=evaluation.checklist.name,
                        score_pct=evaluation.score_pct)
            if evaluation else None
        )
    return calls


async def evaluations_for_call(session: AsyncSession, tenant_id: str, call_id: str) -> list[QaEvaluation]:
    return list((await session.execute(
        select(QaEvaluation).where(QaEvaluation.tenant_id == tenant_id, QaEvaluation.call_id == call_id)
        .options(selectinload(QaEvaluation.checklist)).order_by(QaEvaluation.created_at.desc())
    )).scalars().all())


async def get_checklist_with_criteria(session: AsyncSession, tenant_id: str, checklist_id: str) -> QaChecklist | None:
    return (await session.execute(
        select(QaChecklist).where(QaChecklist.tenant_id == tenant_id, QaChecklist.id == checklist_id)
        .options(selectinload(QaChecklist.criteria))
    )).scalar_one_or_none()
