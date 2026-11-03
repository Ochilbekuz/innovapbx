"""M10 A1 — qayta chaqirish so'rovlari (faqat ko'rish, `apps` ruxsat hududi).
Yozuvlar — ommaviy vidjet (`api/public_widget.py`) va fon dialer
(`services/callback_dialer.py`) tomonidan yaratiladi/yangilanadi."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.db.models import CallbackRequest, CallbackWidget, User
from app.schemas import CallbackRequestOut, Paged

router = APIRouter(prefix="/callback-requests", tags=["callback-widgets"])


@router.get("", response_model=Paged)
async def list_callback_requests(
    widget_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    conds = [CallbackRequest.tenant_id == user.tenant_id]
    if widget_id:
        conds.append(CallbackRequest.widget_id == widget_id)
    if status:
        conds.append(CallbackRequest.status == status)
    total = (await session.execute(select(func.count()).select_from(CallbackRequest).where(*conds))).scalar_one()
    rows = (await session.execute(select(CallbackRequest).where(*conds)
                                  .order_by(CallbackRequest.created_at.desc())
                                  .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    widget_names = {str(w.id): w.name for w in (await session.execute(
        select(CallbackWidget).where(CallbackWidget.tenant_id == user.tenant_id))).scalars().all()}
    items = [
        CallbackRequestOut(
            id=str(r.id), widget_id=str(r.widget_id), widget_name=widget_names.get(str(r.widget_id), "-"),
            phone=r.phone, name=r.name, page_url=r.page_url, status=r.status, attempts=r.attempts,
            next_attempt_at=r.next_attempt_at, linkedid=r.linkedid, last_error=r.last_error,
            created_at=r.created_at, updated_at=r.updated_at,
        )
        for r in rows
    ]
    return Paged(items=items, total=total)
