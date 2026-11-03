"""Qo'ng'iroqlar tarixi — m0-contract.md «Tarix (S12)». Manba — `cdr` jadvali.

CDR qatorlarini mantiqiy qo'ng'iroqqa yig'ish/yo'nalish aniqlash qoidasi
`app/services/cdr_grouping.py`da — `/dashboard` (m1b-contract.md bo'lim 5)
bilan BIR XIL qoida ishlatiladi (ub-mode DRY)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.core.errors import ApiError
from app.core.permissions import ALL, CALLS_READ_OWN, has_permission, has_region_access
from app.db.models import Cdr, Extension, User
from app.schemas import CallDirection, CallOut
from app.schemas_qa import QaEvaluationsOut
from app.services.cdr_grouping import calls_from_rows, trunk_names
from app.services.cdr_search import EXPORT_LIMIT, CallSearch, build_search, calls_csv, filter_calls
from app.services.qa import attach_qa, evaluations_for_call
from app.services.recordings import attach_recordings

router = APIRouter(prefix="/calls", tags=["calls"])


async def _own_extension_number(session: AsyncSession, user: User) -> str | None:
    if user.extension_id is None:
        return None
    ext = await session.get(Extension, user.extension_id)
    return ext.number if ext else None


def _require_calls_permission(user: User) -> bool:
    """`True` qaytaradi — admin YOKI `reports:view` (hammasini ko'radi,
    m7-roles-contract.md §1); aks holda `CALLS_READ_OWN` bo'lmasa 403
    ko'taradi. Qaytgan qiymat chaqiruvchiga "o'z yozuvi bilan cheklash
    kerakmi" degan savolga javob beradi (sof funksiya, testlanadi)."""
    if has_permission(user.role.permissions, ALL):
        return True
    if has_region_access(user.role.permissions, "reports", "view"):
        return True
    if has_permission(user.role.permissions, CALLS_READ_OWN):
        return False
    raise ApiError(403, "forbidden", "Ruxsat yo'q")


def _build_calls_query(tenant_code: str, *, from_: str | None, to: str | None, q: str | None):
    """Filtrlarni `select(Cdr)`ga qo'shadi — sof, bazasiz sinalishi mumkin
    (faqat `Select` obyektini quradi, ijro etmaydi)."""
    stmt = select(Cdr).where(Cdr.accountcode == tenant_code)
    if from_:
        stmt = stmt.where(Cdr.calldate >= _parse_dt(from_))
    if to:
        stmt = stmt.where(Cdr.calldate <= _parse_dt(to))
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Cdr.src.ilike(like)) | (Cdr.dst.ilike(like)) | (Cdr.userfield.ilike(like)))
    return stmt.order_by(Cdr.calldate.desc())


def _filter_own_calls(calls: list[CallOut], own_number: str | None) -> list[CallOut]:
    return [c for c in calls if own_number and (c.src == own_number or c.dst == own_number)]


def _paginate(calls: list[CallOut], page: int, size: int) -> dict:
    start = (page - 1) * size
    return {"items": calls[start:start + size], "total": len(calls)}


async def paginate_with_recordings(session: AsyncSession, tenant_id: str, calls: list[CallOut],
                                   page: int, size: int) -> dict:
    """M3b §1 — faqat sahifadagi qo'ng'iroqlarga yozuvlar (bitta so'rov).
    M10 B1 — `qa` belgisi ham shu yerda (sahifadagi qo'ng'iroqlarga, N+1 yo'q)."""
    result = _paginate(calls, page, size)
    await attach_recordings(session, tenant_id, result["items"])
    await attach_qa(session, tenant_id, result["items"])
    return result


def call_search_params(
    src: str | None = None, src_mode: str | None = None, src_not: bool = False,
    dst: str | None = None, dst_mode: str | None = None, dst_not: bool = False,
    did: str | None = None, did_mode: str | None = None, did_not: bool = False,
    name: str | None = None, ext: str | None = None, trunk: str | None = None,
    account: str | None = None, disposition: str | None = None,
    min_duration: int | None = None, max_duration: int | None = None, recording: str | None = None,
) -> CallSearch:
    """M9 — FreePBX «CDR Reports» qidiruv shabloni (`app/services/cdr_search.py`)."""
    return build_search(
        src=src, src_mode=src_mode, src_not=src_not, dst=dst, dst_mode=dst_mode, dst_not=dst_not,
        did=did, did_mode=did_mode, did_not=did_not, name=name, ext=ext, trunk=trunk, account=account,
        disposition=disposition, min_duration=min_duration, max_duration=max_duration, recording=recording,
    )


async def _searched_calls(session: AsyncSession, user: User, *, from_: str | None, to: str | None,
                          q: str | None, direction: CallDirection | None, search: CallSearch) -> list[CallOut]:
    """Ruxsat + tenant + sana/q (SQL) → yig'ish → o'z qo'ng'iroqlari/yo'nalish/qidiruv (Python)."""
    is_admin = _require_calls_permission(user)
    tenant_code = await _tenant_code(session, user)
    rows = (await session.execute(_build_calls_query(tenant_code, from_=from_, to=to, q=q))).scalars().all()
    calls = calls_from_rows(list(rows), await trunk_names(session, str(user.tenant_id)))
    if not is_admin:
        calls = _filter_own_calls(calls, await _own_extension_number(session, user))
    calls = [c for c in calls if direction in (None, c.direction)]
    if search.needs_recordings:
        await attach_recordings(session, str(user.tenant_id), calls)
    return filter_calls(search, calls)


@router.get("")
async def list_calls(
    from_: str | None = Query(default=None, alias="from"), to: str | None = None, q: str | None = None,
    direction: CallDirection | None = None, page: int = 1, size: int = 50,
    search: CallSearch = Depends(call_search_params),
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> dict:
    calls = await _searched_calls(session, user, from_=from_, to=to, q=q, direction=direction, search=search)
    return await paginate_with_recordings(session, str(user.tenant_id), calls, page, size)


@router.get("/export.csv")
async def export_calls_csv(
    from_: str | None = Query(default=None, alias="from"), to: str | None = None, q: str | None = None,
    direction: CallDirection | None = None, search: CallSearch = Depends(call_search_params),
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> Response:
    """Joriy qidiruv natijasi CSV (ko'pi bilan `EXPORT_LIMIT` qator, yozuvlar soni bilan)."""
    calls = (await _searched_calls(session, user, from_=from_, to=to, q=q, direction=direction,
                                   search=search))[:EXPORT_LIMIT]
    await attach_recordings(session, str(user.tenant_id), calls)
    return Response(calls_csv(calls), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="calls.csv"'})


@router.get("/{linkedid}/evaluations", response_model=QaEvaluationsOut)
async def call_evaluations(
    linkedid: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> QaEvaluationsOut:
    """M10 B1 — bitta qo'ng'iroqning barcha baholashlari (eng yangisi birinchi).
    Ruxsat `/calls` bilan BIR XIL (`_require_calls_permission`) — o'z
    qo'ng'iroqlarini ko'ra oladigan operator shu qo'ng'iroq uchun baholashni
    ham ko'radi (baholovchi ismi ko'rsatilmaydi — faqat varaqa/ball)."""
    _require_calls_permission(user)
    rows = await evaluations_for_call(session, str(user.tenant_id), linkedid)
    items = [
        {
            "id": str(r.id), "checklist_id": str(r.checklist_id), "checklist_name": r.checklist.name,
            "call_id": r.call_id, "extension_id": str(r.extension_id) if r.extension_id else None,
            "evaluator_id": str(r.evaluator_id) if r.evaluator_id else None, "evaluator_name": None,
            "answers": r.answers, "comment": r.comment, "score_pct": r.score_pct,
            "created_at": r.created_at, "updated_at": r.updated_at,
        }
        for r in rows
    ]
    return QaEvaluationsOut(items=items, total=len(items))


async def _tenant_code(session: AsyncSession, user: User) -> str:
    return user.tenant.code


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Sana formati noto'g'ri", field="from") from exc
