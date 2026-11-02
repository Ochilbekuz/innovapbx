"""Audit jurnali — m1b-contract.md bo'lim 6."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.db.models import AuditLog, User
from app.schemas import AuditEntryOut, AuditUserRef

router = APIRouter(prefix="/audit", tags=["audit"])


def _apply_filters(
    stmt, tenant_id: str, *, entity: str | None, user_id: str | None, action: str | None,
    date_from: datetime | None, date_to: datetime | None, q: str | None,
):
    stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if entity is not None:
        stmt = stmt.where(AuditLog.entity == entity)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    if q:
        # `entity` yetarli emas — web/src/api/fake.ts `listAudit` kabi
        # `entity_id`/`diff` (JSON matn sifatida) ichidan ham qidiradi, aks
        # holda admin biror obyekt id'sini audit jurnalida topa olmaydi.
        needle = f"%{q}%"
        login_match = select(User.id).where(User.username.ilike(needle), User.tenant_id == tenant_id)
        stmt = stmt.where(or_(
            AuditLog.entity.ilike(needle),
            cast(AuditLog.entity_id, Text).ilike(needle),
            cast(AuditLog.diff, Text).ilike(needle),
            AuditLog.user_id.in_(login_match),
        ))
    return stmt


async def _user_refs(session: AsyncSession, user_ids: set[str]) -> dict[str, AuditUserRef]:
    if not user_ids:
        return {}
    rows = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    return {str(u.id): AuditUserRef(id=str(u.id), login=u.username) for u in rows}


@router.get("")
async def list_audit(
    entity: str | None = None, user_id: str | None = None, action: str | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"), q: str | None = None,
    page: int = Query(default=1, ge=1), size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    tenant_id = str(user.tenant_id)
    base = _apply_filters(select(AuditLog), tenant_id, entity=entity, user_id=user_id, action=action,
                           date_from=date_from, date_to=date_to, q=q)

    total = (await session.execute(
        _apply_filters(select(func.count(AuditLog.id)), tenant_id, entity=entity, user_id=user_id, action=action,
                        date_from=date_from, date_to=date_to, q=q)
    )).scalar_one()

    rows = (await session.execute(
        base.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)
    )).scalars().all()

    refs = await _user_refs(session, {r.user_id for r in rows if r.user_id})
    items = [
        AuditEntryOut(
            id=str(r.id), at=r.created_at, user=refs.get(r.user_id), action=r.action, entity=r.entity,
            entity_id=r.entity_id, label=None, diff=r.diff,
            ip=str(r.ip) if r.ip is not None else None,  # asyncpg INET -> IPv4Address, schema str kutadi
        )
        for r in rows
    ]
    return {"items": items, "total": total}
