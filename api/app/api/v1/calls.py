"""Qo'ng'iroqlar tarixi — m0-contract.md «Tarix (S12)». Manba — `cdr` jadvali.

CDR qatorlarini mantiqiy qo'ng'iroqqa yig'ish/yo'nalish aniqlash qoidasi
`app/services/cdr_grouping.py`da — `/dashboard` (m1b-contract.md bo'lim 5)
bilan BIR XIL qoida ishlatiladi (ub-mode DRY)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.core.errors import ApiError
from app.core.permissions import ALL, CALLS_READ_OWN, has_permission
from app.db.models import Cdr, Extension, User
from app.schemas import CallDirection, CallOut
from app.services.cdr_grouping import calls_from_rows, trunk_names
from app.services.recordings import attach_recordings

router = APIRouter(prefix="/calls", tags=["calls"])


async def _own_extension_number(session: AsyncSession, user: User) -> str | None:
    if user.extension_id is None:
        return None
    ext = await session.get(Extension, user.extension_id)
    return ext.number if ext else None


def _require_calls_permission(user: User) -> bool:
    """`True` qaytaradi — admin (hammasini ko'radi); aks holda `CALLS_READ_OWN`
    bo'lmasa 403 ko'taradi. Qaytgan qiymat chaqiruvchiga "o'z yozuvi bilan
    cheklash kerakmi" degan savolga javob beradi (sof funksiya, testlanadi)."""
    if has_permission(user.role.permissions, ALL):
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
    """M3b §1 — faqat sahifadagi qo'ng'iroqlarga yozuvlar (bitta so'rov)."""
    result = _paginate(calls, page, size)
    await attach_recordings(session, tenant_id, result["items"])
    return result


@router.get("")
async def list_calls(
    from_: str | None = Query(default=None, alias="from"), to: str | None = None, q: str | None = None,
    direction: CallDirection | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> dict:
    is_admin = _require_calls_permission(user)
    tenant_code = await _tenant_code(session, user)
    stmt = _build_calls_query(tenant_code, from_=from_, to=to, q=q)

    rows = (await session.execute(stmt)).scalars().all()
    calls = calls_from_rows(list(rows), await trunk_names(session, str(user.tenant_id)))

    if not is_admin:
        calls = _filter_own_calls(calls, await _own_extension_number(session, user))
    if direction:
        calls = [c for c in calls if c.direction == direction]

    return await paginate_with_recordings(session, str(user.tenant_id), calls, page, size)


async def _tenant_code(session: AsyncSession, user: User) -> str:
    return user.tenant.code


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Sana formati noto'g'ri", field="from") from exc
