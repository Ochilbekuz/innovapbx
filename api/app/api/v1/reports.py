"""`GET /reports/*` — m2b-contract.md bo'lim 5 (Analitika, S13). Bu router
FAQAT ma'lumot YIG'ADI (CDR/queue_log/agent_events/extensions qatorlari) —
BUTUN hisoblash mantiqi `app/services/report_defs.py`da (sof funksiyalar,
testlanadi) — dashboard.py bilan BIR XIL naqsh (ub-mode Boundary Discipline).
Hammasi admin-only (`require_admin`, m2b-contract.md §0)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.db.models import AgentEvent, Cdr, Extension, Queue, QueueLog, QueueMember, User
from app.schemas_reports import (
    ReportAgentRowOut,
    ReportAgentsOut,
    ReportDailyOut,
    ReportDailyRowOut,
    ReportHourlyOut,
    ReportHourlyRowOut,
    ReportQueueRowOut,
    ReportQueuesOut,
    ReportSummaryOut,
)
from app.services.report_defs import (
    AgentQueueStats,
    agent_queue_stats,
    build_agent_report_row,
    build_daily,
    build_hourly,
    build_queue_report_row,
    build_summary,
    filter_calls_by_linkedid,
    login_pause_seconds,
    queue_stats_from_log,
    queue_wait_samples,
    range_bounds_utc,
    report_calls_from_rows,
    validate_range,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Sana formati noto'g'ri (YYYY-MM-DD)", field=field) from exc


def _parse_range(from_: str, to: str) -> tuple[date, date]:
    from_date = _parse_date(from_, "from")
    to_date = _parse_date(to, "to")
    validate_range(from_date, to_date)
    return from_date, to_date


async def _resolve_queues(session: AsyncSession, tenant_id: str, queue_id: str | None) -> list[Queue]:
    """`?queue_id=` bo'lsa — faqat O'SHA (tenant-skopli, bo'lmasa 404) navbat;
    bo'lmasa — tenantning BARCHA navbatlari (summary/queues SLA pooling uchun)."""
    if queue_id is not None:
        queue = await get_tenant_scoped_or_404(
            session, Queue, tenant_id, queue_id, not_found_message="Navbat topilmadi", field="queue_id",
        )
        return [queue]
    return list((await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name)
    )).scalars().all())


async def _fetch_cdr_rows(session: AsyncSession, tenant_code: str, start: datetime, end: datetime) -> list[Cdr]:
    return list((await session.execute(
        select(Cdr).where(Cdr.accountcode == tenant_code, Cdr.calldate >= start, Cdr.calldate < end)
    )).scalars().all())


async def _fetch_queue_log_rows(
    session: AsyncSession, queuenames: list[str], start: datetime, end: datetime,
) -> list[QueueLog]:
    if not queuenames:
        return []
    return list((await session.execute(
        select(QueueLog).where(
            QueueLog.queuename.in_(queuenames), QueueLog.time >= start, QueueLog.time < end,
        )
    )).scalars().all())


def _queuename(tenant_code: str, queue: Queue) -> str:
    return f"{tenant_code}-q-{queue.id}"


_IGNORED_AGENT_NAMES = ("NONE", "REALTIME")


def _call_ids_from_log(rows: list[QueueLog]) -> set[str]:
    return {r.callid for r in rows if r.callid and r.callid not in _IGNORED_AGENT_NAMES}


@router.get("/summary", response_model=ReportSummaryOut)
async def get_summary(
    from_: str = Query(alias="from"), to: str = Query(...), queue_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ReportSummaryOut:
    tenant = user.tenant
    tenant_id = str(user.tenant_id)
    from_date, to_date = _parse_range(from_, to)
    start, end = range_bounds_utc(tenant.timezone, from_date, to_date)

    queues = await _resolve_queues(session, tenant_id, queue_id)
    queuenames = [_queuename(tenant.code, q) for q in queues]
    log_rows = await _fetch_queue_log_rows(session, queuenames, start, end)

    calls = report_calls_from_rows(await _fetch_cdr_rows(session, tenant.code, start, end))
    if queue_id is not None:
        calls = filter_calls_by_linkedid(calls, _call_ids_from_log(log_rows))

    sla_by_queuename = {_queuename(tenant.code, q): q.sla_seconds for q in queues}
    samples = queue_wait_samples(log_rows, sla_by_queuename)

    data = build_summary(calls, tenant.timezone, samples)
    return ReportSummaryOut(**data, **{"from": from_date.isoformat(), "to": to_date.isoformat()},
                             timezone=tenant.timezone)


@router.get("/queues", response_model=ReportQueuesOut)
async def get_queues_report(
    from_: str = Query(alias="from"), to: str = Query(...), queue_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ReportQueuesOut:
    tenant = user.tenant
    tenant_id = str(user.tenant_id)
    from_date, to_date = _parse_range(from_, to)
    start, end = range_bounds_utc(tenant.timezone, from_date, to_date)

    queues = await _resolve_queues(session, tenant_id, queue_id)
    queuenames = [_queuename(tenant.code, q) for q in queues]
    log_rows = await _fetch_queue_log_rows(session, queuenames, start, end)
    rows_by_queuename: dict[str, list[QueueLog]] = {name: [] for name in queuenames}
    for row in log_rows:
        if row.queuename in rows_by_queuename:
            rows_by_queuename[row.queuename].append(row)

    items = [
        ReportQueueRowOut(
            queue_id=str(q.id), name=q.name,
            **build_queue_report_row(queue_stats_from_log(rows_by_queuename[_queuename(tenant.code, q)]),
                                      q.sla_seconds),
        )
        for q in queues
    ]
    return ReportQueuesOut(items=items)


async def _agent_members(session: AsyncSession, tenant_id: str, queue_id: str | None) -> list[tuple[Extension, Queue]]:
    """`(extension, queue)` juftliklari — bir extension bir nechta navbatda
    bo'lsa, HAR navbat uchun alohida qator (`queue_id` filtrisiz)."""
    query = (
        select(Extension, Queue)
        .join(QueueMember, QueueMember.extension_id == Extension.id)
        .join(Queue, Queue.id == QueueMember.queue_id)
        .where(Queue.tenant_id == tenant_id)
        .order_by(Extension.number)
    )
    if queue_id is not None:
        query = query.where(Queue.id == queue_id)
    rows = (await session.execute(query)).all()
    return [(ext, q) for ext, q in rows]


@router.get("/agents", response_model=ReportAgentsOut)
async def get_agents_report(
    from_: str = Query(alias="from"), to: str = Query(...), queue_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ReportAgentsOut:
    tenant = user.tenant
    tenant_id = str(user.tenant_id)
    from_date, to_date = _parse_range(from_, to)
    start, end = range_bounds_utc(tenant.timezone, from_date, to_date)
    if queue_id is not None:
        # tenant-skopli borligini tekshiramiz (404 bo'lsa shu yerda ko'tariladi)
        await get_tenant_scoped_or_404(
            session, Queue, tenant_id, queue_id, not_found_message="Navbat topilmadi", field="queue_id",
        )

    members = await _agent_members(session, tenant_id, queue_id)
    if not members:
        return ReportAgentsOut(items=[])

    queues = {q.id: q for _, q in members}
    queuenames = [_queuename(tenant.code, q) for q in queues.values()]
    log_rows = await _fetch_queue_log_rows(session, queuenames, start, end)
    stats_by_agent_name = agent_queue_stats(log_rows)

    extension_ids = list({ext.id for ext, _ in members})
    events = list((await session.execute(
        select(AgentEvent).where(AgentEvent.extension_id.in_(extension_ids), AgentEvent.at < end)
        .order_by(AgentEvent.at)
    )).scalars().all())
    events_by_extension: dict[str, list[AgentEvent]] = {ext_id: [] for ext_id in extension_ids}
    for e in events:
        events_by_extension[e.extension_id].append(e)

    window_end = min(end, datetime.now(timezone.utc))
    items = []
    seen_extensions: set[str] = set()
    for ext, _ in members:
        if ext.id in seen_extensions:
            continue
        seen_extensions.add(ext.id)
        login_seconds, pause_seconds = login_pause_seconds(events_by_extension[ext.id], start, window_end)
        stats = stats_by_agent_name.get(ext.name, AgentQueueStats())
        items.append(ReportAgentRowOut(**build_agent_report_row(
            extension_number=ext.number, extension_name=ext.name, queue_stats=stats,
            login_seconds=login_seconds, pause_seconds=pause_seconds,
        )))
    return ReportAgentsOut(items=items)


@router.get("/hourly", response_model=ReportHourlyOut)
async def get_hourly_report(
    from_: str = Query(alias="from"), to: str = Query(...), queue_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ReportHourlyOut:
    tenant = user.tenant
    tenant_id = str(user.tenant_id)
    from_date, to_date = _parse_range(from_, to)
    start, end = range_bounds_utc(tenant.timezone, from_date, to_date)

    calls = report_calls_from_rows(await _fetch_cdr_rows(session, tenant.code, start, end))
    if queue_id is not None:
        queue = await get_tenant_scoped_or_404(
            session, Queue, tenant_id, queue_id, not_found_message="Navbat topilmadi", field="queue_id",
        )
        log_rows = await _fetch_queue_log_rows(session, [_queuename(tenant.code, queue)], start, end)
        calls = filter_calls_by_linkedid(calls, _call_ids_from_log(log_rows))

    return ReportHourlyOut(items=[ReportHourlyRowOut(**row) for row in build_hourly(calls, tenant.timezone)])


@router.get("/daily", response_model=ReportDailyOut)
async def get_daily_report(
    from_: str = Query(alias="from"), to: str = Query(...), queue_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> ReportDailyOut:
    tenant = user.tenant
    tenant_id = str(user.tenant_id)
    from_date, to_date = _parse_range(from_, to)
    start, end = range_bounds_utc(tenant.timezone, from_date, to_date)

    calls = report_calls_from_rows(await _fetch_cdr_rows(session, tenant.code, start, end))
    if queue_id is not None:
        queue = await get_tenant_scoped_or_404(
            session, Queue, tenant_id, queue_id, not_found_message="Navbat topilmadi", field="queue_id",
        )
        log_rows = await _fetch_queue_log_rows(session, [_queuename(tenant.code, queue)], start, end)
        calls = filter_calls_by_linkedid(calls, _call_ids_from_log(log_rows))

    return ReportDailyOut(items=[ReportDailyRowOut(**row)
                                  for row in build_daily(calls, tenant.timezone, from_date, to_date)])
