"""Bosh panel — m1b-contract.md bo'lim 5. Barcha BOG'LIQ qoidalar (vaqt
oynasi, CDR guruhlash, ogohlantirishlar) `app/services/dashboard.py`/
`cdr_grouping.py`da — bu yerda faqat ma'lumot YIG'ISH (DB/AMI) bor."""
from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.db.models import Cdr, ConfigRevision, OutboundRoute, Queue, Trunk, TrunkHealth, User
from app.schemas import (
    DashboardHealthOut,
    DashboardLiveOut,
    DashboardOut,
    DashboardQueueOut,
    DbHealth,
    LiveCallOut,
    TrunkDashboardOut,
)
from app.services.cdr_grouping import calls_from_rows
from app.services.dashboard import (
    build_alerts,
    build_missed_calls,
    build_today_stats,
    build_trunk_dashboard_items,
    disk_health,
    today_bounds_utc,
)
from app.services.health import asterisk_health, db_up
from app.services.live_status import active_calls_live, queue_live_status, trunk_registration_state
from app.services.trunk_health import endpoint_id_for

router = APIRouter(tags=["dashboard"])


async def _trunk_dashboard_items(session: AsyncSession, ami, tenant_id: str, tenant_code: str,
                                  ) -> list[TrunkDashboardOut]:
    """Ma'lumotni YIG'ADI (DB/AMI) — holat QOIDASI `build_trunk_dashboard_items`da
    (sof, bazasiz sinaladi). Samaradorlik (m1b-contract.md bo'lim 5, 300ms
    chegarasi, o'lchab aniqlangan): `ip` rejim — BITTA bulk SELECT (N alohida
    emas), `register` rejim — AMI so'rovlari BIR VAQTDA (`asyncio.gather`,
    AMI mijozi ActionID bilan konkurent javoblarni to'g'ri taqsimlaydi) —
    N ketma-ket AMI round-trip 300ms chegarasini buzgani o'lchab aniqlandi."""
    trunks = (await session.execute(
        select(Trunk).where(Trunk.tenant_id == tenant_id).order_by(Trunk.name)
    )).scalars().all()
    enabled_ip_ids = [t.id for t in trunks if t.enabled and t.auth_mode != "register"]
    db_health_by_id = {}
    if enabled_ip_ids:
        rows = (await session.execute(
            select(TrunkHealth).where(TrunkHealth.trunk_id.in_(enabled_ip_ids))
        )).scalars().all()
        db_health_by_id = {row.trunk_id: row for row in rows}

    register_trunks = [t for t in trunks if t.enabled and t.auth_mode == "register"]
    registrations = await asyncio.gather(*(
        trunk_registration_state(ami, endpoint_id_for(tenant_code, t.id)) for t in register_trunks
    ))
    reg_by_trunk_id = dict(zip((t.id for t in register_trunks), registrations, strict=True))

    return build_trunk_dashboard_items(trunks, db_health_by_id, reg_by_trunk_id)


async def _live_section(ami) -> DashboardLiveOut:
    calls = await active_calls_live(ami)
    if calls is None:
        return DashboardLiveOut(active_calls=0, calls=[])
    return DashboardLiveOut(active_calls=len(calls), calls=[LiveCallOut(**c) for c in calls])


_NO_LIVE_QUEUE_DATA = {"waiting": 0, "members_online": 0, "longest_wait_s": 0}


async def _queue_sections(session: AsyncSession, ami, tenant_id: str, tenant_code: str) -> list[DashboardQueueOut]:
    queues = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name)
    )).scalars().all()
    live_results = await asyncio.gather(*(
        queue_live_status(ami, f"{tenant_code}-q-{q.id}") for q in queues
    ))
    return [
        DashboardQueueOut(id=str(q.id), name=q.name, **(live or _NO_LIVE_QUEUE_DATA))
        for q, live in zip(queues, live_results, strict=True)
    ]


async def _has_outbound_route(session: AsyncSession, tenant_id: str) -> bool:
    route_id = (await session.execute(
        select(OutboundRoute.id).where(OutboundRoute.tenant_id == tenant_id).limit(1)
    )).scalar_one_or_none()
    return route_id is not None


async def _last_revision_rolled_back(session: AsyncSession, tenant_id: str) -> bool:
    status = (await session.execute(
        select(ConfigRevision.status).where(ConfigRevision.tenant_id == tenant_id)
        .order_by(ConfigRevision.id.desc()).limit(1)
    )).scalar_one_or_none()
    return status == "rolled_back"


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin), ami=Depends(get_ami),
) -> DashboardOut:
    tenant_id = str(user.tenant_id)
    tenant = user.tenant

    trunks = await _trunk_dashboard_items(session, ami, tenant_id, tenant.code)
    health = DashboardHealthOut(
        asterisk=await asterisk_health(ami), db=DbHealth(up=await db_up(session)),
        disk=disk_health(*shutil.disk_usage("/")[::2]), trunks=trunks,
    )
    live = await _live_section(ami)
    queues = await _queue_sections(session, ami, tenant_id, tenant.code)

    start, end = today_bounds_utc(tenant.timezone, datetime.now(timezone.utc))
    rows = (await session.execute(
        select(Cdr).where(Cdr.accountcode == tenant.code, Cdr.calldate >= start, Cdr.calldate < end)
        .order_by(Cdr.calldate.desc())
    )).scalars().all()
    todays_calls = calls_from_rows(list(rows))
    today = build_today_stats(todays_calls, tenant.timezone)
    missed = build_missed_calls(todays_calls)

    alerts = build_alerts(
        asterisk_up=health.asterisk.up, disk_used_pct=health.disk.used_pct,
        trunk_down=any(t.state == "unreachable" for t in trunks),
        has_outbound_route=await _has_outbound_route(session, tenant_id),
        last_revision_rolled_back=await _last_revision_rolled_back(session, tenant_id),
    )

    return DashboardOut(health=health, live=live, queues=queues, today=today, missed=missed, alerts=alerts)
