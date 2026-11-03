"""M10 Bo'lak B1 — Sifat baholash (QA): varaqa (checklist) CRUD + baholash
(evaluation) CRUD + xulosa (`/qa/summary`). Hudud `reports` (view=ko'rish,
edit=baholash/varaqa tahriri — `core/permissions.py::_PREFIX_REGION`)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import Extension, QaChecklist, QaCriterion, QaEvaluation, User
from app.schemas_qa import (
    CreateQaChecklistPayload,
    CreateQaEvaluationPayload,
    QaChecklistOut,
    QaChecklistsOut,
    QaCriterionOut,
    QaEvaluationOut,
    QaEvaluationsOut,
    QaSummaryByExtension,
    QaSummaryOut,
    UpdateQaChecklistPayload,
    UpdateQaEvaluationPayload,
)
from app.services.audit import record_audit
from app.services.qa import compute_score_pct, get_checklist_with_criteria

router = APIRouter(prefix="/qa", tags=["qa"])

_CHECKLIST_NAME_TAKEN = ApiError(409, "name_taken", "Shu nomli varaqa allaqachon mavjud", field="name")
_CHECKLIST_NOT_FOUND = "Baholash varaqasi topilmadi"
_EVALUATION_NOT_FOUND = "Baholash topilmadi"

_CHECKLIST_OPTIONS = (selectinload(QaChecklist.criteria),)


def _checklist_out(checklist: QaChecklist) -> QaChecklistOut:
    return QaChecklistOut(
        id=str(checklist.id), name=checklist.name, is_active=checklist.is_active,
        criteria=[QaCriterionOut(id=str(c.id), label=c.label, kind=c.kind, weight=c.weight,
                                  critical=c.critical, position=c.position)
                  for c in sorted(checklist.criteria, key=lambda c: c.position)],
        updated_at=checklist.updated_at,
    )


async def _get_checklist_or_404(session: AsyncSession, tenant_id: str, checklist_id: str) -> QaChecklist:
    return await get_tenant_scoped_or_404(
        session, QaChecklist, tenant_id, checklist_id, not_found_message=_CHECKLIST_NOT_FOUND,
        options=_CHECKLIST_OPTIONS,
    )


# --------------------------------------------------------------------- checklists
@router.get("/checklists", response_model=QaChecklistsOut)
async def list_checklists(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> QaChecklistsOut:
    rows = (await session.execute(
        select(QaChecklist).where(QaChecklist.tenant_id == user.tenant_id).order_by(QaChecklist.name)
        .options(*_CHECKLIST_OPTIONS)
    )).scalars().all()
    return QaChecklistsOut(items=[_checklist_out(r) for r in rows])


@router.post("/checklists", response_model=QaChecklistOut, status_code=201)
async def create_checklist(
    payload: CreateQaChecklistPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> QaChecklistOut:
    tenant_id = str(user.tenant_id)
    checklist = QaChecklist(tenant_id=tenant_id, name=payload.name)
    session.add(checklist)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _CHECKLIST_NAME_TAKEN from exc

    for position, criterion in enumerate(payload.criteria):
        session.add(QaCriterion(checklist_id=checklist.id, label=criterion.label, kind=criterion.kind,
                                 weight=criterion.weight, critical=criterion.critical, position=position))
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_checklist.create",
                        entity="qa_checklist", entity_id=str(checklist.id), diff={"name": payload.name})
    await session.commit()
    return _checklist_out(await _get_checklist_or_404(session, tenant_id, str(checklist.id)))


@router.patch("/checklists/{checklist_id}", response_model=QaChecklistOut)
async def update_checklist(
    checklist_id: str, payload: UpdateQaChecklistPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> QaChecklistOut:
    tenant_id = str(user.tenant_id)
    checklist = await _get_checklist_or_404(session, tenant_id, checklist_id)
    check_not_stale(checklist.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        checklist.name = payload.name
        diff["name"] = payload.name
    if payload.is_active is not None:
        checklist.is_active = payload.is_active
        diff["is_active"] = payload.is_active
    if payload.criteria is not None:
        for old in list(checklist.criteria):
            await session.delete(old)
        await session.flush()
        for position, criterion in enumerate(payload.criteria):
            session.add(QaCriterion(checklist_id=checklist.id, label=criterion.label, kind=criterion.kind,
                                     weight=criterion.weight, critical=criterion.critical, position=position))
        diff["criteria_count"] = len(payload.criteria)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _CHECKLIST_NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_checklist.update",
                        entity="qa_checklist", entity_id=str(checklist.id), diff=diff)
    await session.commit()
    return _checklist_out(await _get_checklist_or_404(session, tenant_id, checklist_id))


@router.delete("/checklists/{checklist_id}", status_code=204, response_model=None)
async def delete_checklist(
    checklist_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    checklist = await _get_checklist_or_404(session, tenant_id, checklist_id)
    in_use = (await session.execute(
        select(func.count()).select_from(QaEvaluation).where(QaEvaluation.checklist_id == checklist_id)
    )).scalar_one()
    if in_use:
        raise ApiError(409, "in_use", f"«{checklist.name}» hali {in_use} baholashda ishlatilgan",
                        details={"usages": in_use})

    await session.delete(checklist)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_checklist.delete",
                        entity="qa_checklist", entity_id=checklist_id)
    await session.commit()


# --------------------------------------------------------------------- evaluations
def _evaluation_out(ev: QaEvaluation, evaluator_name: str | None) -> QaEvaluationOut:
    return QaEvaluationOut(
        id=str(ev.id), checklist_id=str(ev.checklist_id), checklist_name=ev.checklist.name,
        call_id=ev.call_id, extension_id=str(ev.extension_id) if ev.extension_id else None,
        evaluator_id=str(ev.evaluator_id) if ev.evaluator_id else None, evaluator_name=evaluator_name,
        answers=ev.answers, comment=ev.comment, score_pct=ev.score_pct,
        created_at=ev.created_at, updated_at=ev.updated_at,
    )


async def _evaluator_names(session: AsyncSession, rows: list[QaEvaluation]) -> dict[str, str]:
    ids = {r.evaluator_id for r in rows if r.evaluator_id}
    if not ids:
        return {}
    found = (await session.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all()
    return {str(r.id): r.full_name for r in found}


def _name_of(names: dict[str, str], ev: QaEvaluation) -> str | None:
    return names.get(str(ev.evaluator_id)) if ev.evaluator_id else None


async def _get_evaluation_or_404(session: AsyncSession, tenant_id: str, evaluation_id: str) -> QaEvaluation:
    return await get_tenant_scoped_or_404(
        session, QaEvaluation, tenant_id, evaluation_id, not_found_message=_EVALUATION_NOT_FOUND,
        options=(selectinload(QaEvaluation.checklist),),
    )


@router.get("/evaluations", response_model=QaEvaluationsOut)
async def list_evaluations(
    call_id: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> QaEvaluationsOut:
    stmt = (select(QaEvaluation).where(QaEvaluation.tenant_id == user.tenant_id)
            .options(selectinload(QaEvaluation.checklist)).order_by(QaEvaluation.created_at.desc()))
    if call_id:
        stmt = stmt.where(QaEvaluation.call_id == call_id)
    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)
    start = (page - 1) * size
    page_rows = rows[start:start + size]
    names = await _evaluator_names(session, page_rows)
    return QaEvaluationsOut(items=[_evaluation_out(r, _name_of(names, r)) for r in page_rows], total=total)


@router.post("/evaluations", response_model=QaEvaluationOut, status_code=201)
async def create_evaluation(
    payload: CreateQaEvaluationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> QaEvaluationOut:
    tenant_id = str(user.tenant_id)
    checklist = await get_checklist_with_criteria(session, tenant_id, payload.checklist_id)
    if checklist is None:
        raise ApiError(404, "not_found", _CHECKLIST_NOT_FOUND, field="checklist_id")
    if payload.extension_id is not None:
        parse_uuid(payload.extension_id, not_found_message="Ichki raqam topilmadi")
        ext = await session.get(Extension, payload.extension_id)
        if ext is None or str(ext.tenant_id) != tenant_id:
            raise ApiError(404, "not_found", "Ichki raqam topilmadi", field="extension_id")

    score = compute_score_pct(checklist, payload.answers)
    evaluation = QaEvaluation(
        tenant_id=tenant_id, checklist_id=checklist.id, call_id=payload.call_id,
        extension_id=payload.extension_id, evaluator_id=user.id, answers=payload.answers,
        comment=payload.comment, score_pct=score,
    )
    session.add(evaluation)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_evaluation.create",
                        entity="qa_evaluation", entity_id=str(evaluation.id),
                        diff={"call_id": payload.call_id, "score_pct": score})
    await session.commit()
    saved = await _get_evaluation_or_404(session, tenant_id, str(evaluation.id))
    return _evaluation_out(saved, user.full_name)


@router.patch("/evaluations/{evaluation_id}", response_model=QaEvaluationOut)
async def update_evaluation(
    evaluation_id: str, payload: UpdateQaEvaluationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> QaEvaluationOut:
    tenant_id = str(user.tenant_id)
    evaluation = await _get_evaluation_or_404(session, tenant_id, evaluation_id)
    check_not_stale(evaluation.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.answers is not None:
        checklist = await get_checklist_with_criteria(session, tenant_id, str(evaluation.checklist_id))
        evaluation.answers = payload.answers
        evaluation.score_pct = compute_score_pct(checklist, payload.answers)
        diff["score_pct"] = evaluation.score_pct
    if payload.comment is not None:
        evaluation.comment = payload.comment
        diff["comment"] = payload.comment

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_evaluation.update",
                        entity="qa_evaluation", entity_id=str(evaluation.id), diff=diff)
    await session.commit()
    saved = await _get_evaluation_or_404(session, tenant_id, evaluation_id)
    return _evaluation_out(saved, _name_of(await _evaluator_names(session, [saved]), saved))


@router.delete("/evaluations/{evaluation_id}", status_code=204, response_model=None)
async def delete_evaluation(
    evaluation_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    evaluation = await _get_evaluation_or_404(session, tenant_id, evaluation_id)
    await session.delete(evaluation)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="qa_evaluation.delete",
                        entity="qa_evaluation", entity_id=evaluation_id)
    await session.commit()


# --------------------------------------------------------------------- summary
@router.get("/summary", response_model=QaSummaryOut)
async def qa_summary(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> QaSummaryOut:
    rows = (await session.execute(
        select(QaEvaluation.extension_id, QaEvaluation.score_pct)
        .where(QaEvaluation.tenant_id == user.tenant_id)
    )).all()
    if not rows:
        return QaSummaryOut(count=0, avg_score_pct=0.0, by_extension=[])

    ext_ids = {r.extension_id for r in rows if r.extension_id}
    numbers: dict[str, str] = {}
    if ext_ids:
        ext_rows = (await session.execute(select(Extension.id, Extension.number).where(Extension.id.in_(ext_ids)))).all()
        numbers = {str(r.id): r.number for r in ext_rows}

    by_ext: dict[str | None, list[float]] = {}
    for row in rows:
        by_ext.setdefault(row.extension_id, []).append(row.score_pct)

    by_extension = [
        QaSummaryByExtension(
            extension_id=str(ext_id) if ext_id else None,
            extension_number=numbers.get(str(ext_id)) if ext_id else None,
            count=len(scores), avg_score_pct=round(sum(scores) / len(scores), 2),
        )
        for ext_id, scores in sorted(by_ext.items(), key=lambda kv: numbers.get(str(kv[0]) if kv[0] else "", ""))
    ]
    all_scores = [r.score_pct for r in rows]
    return QaSummaryOut(count=len(all_scores), avg_score_pct=round(sum(all_scores) / len(all_scores), 2),
                        by_extension=by_extension)
