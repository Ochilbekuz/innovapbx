"""M2c §4 — `GET /alerts` — ogohlantirish tarixi (`alert_log`, faqat o'qish;
yozish — `app/services/alerts.py` `raise_alert`/fon vazifa)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.db.models import AlertLog, User
from app.schemas_security import AlertLogList, AlertLogOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertLogList)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=500), kind: str | None = None,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> AlertLogList:
    stmt = (
        select(AlertLog).where(AlertLog.tenant_id == user.tenant_id)
        .order_by(AlertLog.at.desc()).limit(limit)
    )
    if kind:
        stmt = stmt.where(AlertLog.kind == kind)
    rows = (await session.execute(stmt)).scalars().all()
    return AlertLogList(items=[
        AlertLogOut(id=r.id, at=r.at, kind=r.kind, key=r.key, text=r.body, status=r.status,
                    error=r.error, sent_at=r.sent_at)
        for r in rows
    ])
