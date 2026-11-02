"""Tizim holati va konfiguratsiya reviziyalari — m0-contract.md «Tizim»,
m1b-contract.md bo'lim 7 (reviziya tafsiloti/diff/tiklash)."""
from __future__ import annotations

import difflib

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.errors import ApiError
from app.db.models import ConfigRevision, Tenant, User
from app.schemas import (
    AuditUserRef,
    ConfigRevisionDetailOut,
    ConfigRevisionDiffOut,
    ConfigRevisionOut,
    DbHealth,
    RestoreRevisionResult,
    SystemHealth,
)
from app.services.apply import restore_revision
from app.services.audit import record_audit
from app.services.health import asterisk_health, db_up

router = APIRouter(tags=["system"])


@router.get("/system/health", response_model=SystemHealth)
async def system_health(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin), ami=Depends(get_ami),
) -> SystemHealth:
    db_is_up = await db_up(session)
    asterisk = await asterisk_health(ami)

    last = (await session.execute(
        select(ConfigRevision)
        .where(ConfigRevision.tenant_id == user.tenant_id, ConfigRevision.status == "applied")
        .order_by(ConfigRevision.id.desc()).limit(1)
    )).scalar_one_or_none()

    return SystemHealth(asterisk=asterisk, db=DbHealth(up=db_is_up), revision=last.id if last else None)


@router.get("/config/revisions")
async def config_revisions(
    limit: int = 20, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    rows = (await session.execute(
        select(ConfigRevision).where(ConfigRevision.tenant_id == user.tenant_id)
        .order_by(ConfigRevision.id.desc()).limit(limit)
    )).scalars().all()
    items = [
        ConfigRevisionOut(id=str(r.id), sha256=r.dialplan_sha256, status=r.status, created_at=r.created_at,
                           message=r.error)
        for r in rows
    ]
    return {"items": items}


async def _get_revision_or_404(session: AsyncSession, tenant_id: str, revision_id: str) -> ConfigRevision:
    try:
        numeric_id = int(revision_id)
    except ValueError as exc:
        raise ApiError(404, "not_found", "Reviziya topilmadi") from exc
    revision = await session.get(ConfigRevision, numeric_id)
    if revision is None or revision.tenant_id != tenant_id:
        raise ApiError(404, "not_found", "Reviziya topilmadi")
    return revision


async def _revision_user_ref(session: AsyncSession, user_id: str | None) -> AuditUserRef | None:
    if user_id is None:
        return None
    user = await session.get(User, user_id)
    return AuditUserRef(id=str(user.id), login=user.login) if user else None


@router.get("/config/revisions/{revision_id}", response_model=ConfigRevisionDetailOut)
async def get_config_revision(
    revision_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ConfigRevisionDetailOut:
    revision = await _get_revision_or_404(session, str(user.tenant_id), revision_id)
    user_ref = await _revision_user_ref(session, revision.user_id)
    return ConfigRevisionDetailOut(
        id=str(revision.id), sha256=revision.dialplan_sha256, status=revision.status,
        created_at=revision.created_at, message=revision.error, user=user_ref, summary=None,
        dialplan=revision.dialplan,
    )


async def _diff_against_revision(
    session: AsyncSession, tenant_id: str, revision: ConfigRevision, against: str,
) -> ConfigRevision | None:
    """`prev` — shu reviziyadan oldingi istalgan holatdagi yozuv (ID bo'yicha
    kichikroq); `current` — hozir qo'llangan (status=applied) oxirgi
    reviziya."""
    if against == "current":
        result = await session.execute(
            select(ConfigRevision).where(ConfigRevision.tenant_id == tenant_id, ConfigRevision.status == "applied")
            .order_by(ConfigRevision.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()
    result = await session.execute(
        select(ConfigRevision).where(ConfigRevision.tenant_id == tenant_id, ConfigRevision.id < revision.id)
        .order_by(ConfigRevision.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/config/revisions/{revision_id}/diff", response_model=ConfigRevisionDiffOut)
async def diff_config_revision(
    revision_id: str, against: str = "prev", session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> ConfigRevisionDiffOut:
    if against not in ("prev", "current"):
        raise ApiError(422, "bad_value", "against faqat prev|current bo'lishi mumkin", field="against")
    tenant_id = str(user.tenant_id)
    revision = await _get_revision_or_404(session, tenant_id, revision_id)
    other = await _diff_against_revision(session, tenant_id, revision, against)
    other_lines = (other.dialplan.splitlines(keepends=True) if other else [])
    other_label = f"revision-{other.id}" if other else "(bo'sh)"
    unified = "".join(difflib.unified_diff(
        other_lines, revision.dialplan.splitlines(keepends=True),
        fromfile=other_label, tofile=f"revision-{revision.id}",
    ))
    return ConfigRevisionDiffOut(unified=unified)


@router.post("/config/revisions/{revision_id}/restore", response_model=RestoreRevisionResult)
async def restore_config_revision(
    revision_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> RestoreRevisionResult:
    tenant_id = str(user.tenant_id)
    revision = await _get_revision_or_404(session, tenant_id, revision_id)
    if revision.status != "applied":
        raise ApiError(409, "not_applied", "Faqat avval qo'llangan reviziyani tiklash mumkin")

    tenant = await session.get(Tenant, tenant_id)
    apply_result = await restore_revision(
        session, tenant_id=tenant_id, tenant_code=tenant.code, user_id=str(user.id), ami=ami, target=revision,
    )
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="restore",
                        entity="config_revision", entity_id=str(revision.id),
                        diff={"restored_from": revision.id, "result": apply_result.status})
    await session.commit()
    item = ConfigRevisionOut(id=str(revision.id), sha256=revision.dialplan_sha256, status=revision.status,
                              created_at=revision.created_at, message=revision.error)
    return RestoreRevisionResult(item=item, apply=apply_result.to_dict(), drift=True)
