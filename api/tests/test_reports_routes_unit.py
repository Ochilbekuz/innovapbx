"""`app/api/v1/reports.py` — marshrut (DB/AMI'siz, monkeypatch bilan ma'lumot
YIG'ISH funksiyalari almashtiriladi, `test_queue_members_routes_unit.py`
namunasi bo'yicha). Haqiqiy Postgres semantikasi/ORM mapping —
`tests/test_reports_live.py`da (`reports_test` bazasi)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import reports as rp
from app.core.errors import ApiError

TENANT = SimpleNamespace(id="t1", code="t1", timezone="Asia/Tashkent")
USER = SimpleNamespace(id="u1", tenant_id="t1", tenant=TENANT)


class _Session:
    """`/agents`da TO'G'RIDAN-TO'G'RI `session.execute` chaqiriladi (`AgentEvent`
    so'rovi) — boshqa barcha ma'lumot YIG'ISH funksiyalari monkeypatch
    qilinadi, shu sabab bu soxta sessiya FAQAT shu bitta chaqiruv uchun kerak."""
    def __init__(self, events: list) -> None:
        self._events = events

    async def execute(self, *_a, **_kw):
        events = self._events
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: events))


def _cdr_call(**kw) -> SimpleNamespace:
    defaults = dict(
        uniqueid="1.0", linkedid="1.0", calldate=datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc),
        channel="PJSIP/t1-trunk-1-x", dstchannel="PJSIP/t1-101-x", disposition="ANSWERED",
        duration=20, billsec=15, userfield=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _queue_log(**kw) -> SimpleNamespace:
    defaults = dict(callid="1.0", queuename="t1-q-1", agent=None, event="ENTERQUEUE",
                     data1=None, data2=None, data3=None, time=datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _queue(**kw) -> SimpleNamespace:
    defaults = dict(id="q1", name="Sotuv", sla_seconds=20)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _extension(**kw) -> SimpleNamespace:
    defaults = dict(id="e1", number="101", name="Operator Ali")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _agent_event(**kw) -> SimpleNamespace:
    defaults = dict(event="login", at=datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc), extension_id="e1")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------- sana validatsiyasi (umumiy)
@pytest.mark.asyncio
async def test_get_summary_bad_date_format_raises_422_validation_error():
    with pytest.raises(ApiError) as exc_info:
        await rp.get_summary(from_="not-a-date", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"
    assert exc_info.value.field == "from"


@pytest.mark.asyncio
async def test_get_summary_range_too_long_raises_bad_range():
    with pytest.raises(ApiError) as exc_info:
        await rp.get_summary(from_="2026-01-01", to="2026-04-03", queue_id=None, session=None, user=USER)
    assert exc_info.value.code == "bad_range"
    assert exc_info.value.field == "to"


# --------------------------------------------------------------- /reports/summary
@pytest.mark.asyncio
async def test_get_summary_without_queue_filter(monkeypatch):
    async def fake_resolve_queues(session, tenant_id, queue_id):
        return [_queue()]

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        return [_queue_log(event="CONNECT", data1="5")]

    async def fake_fetch_cdr_rows(session, tenant_code, start, end):
        return [_cdr_call(), _cdr_call(uniqueid="2.0", linkedid="2.0", disposition="NO ANSWER",
                                        dstchannel=None, billsec=0)]

    monkeypatch.setattr(rp, "_resolve_queues", fake_resolve_queues)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)
    monkeypatch.setattr(rp, "_fetch_cdr_rows", fake_fetch_cdr_rows)

    out = await rp.get_summary(from_="2026-10-28", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert out.total == 2
    assert out.answered == 1
    assert out.missed == 1
    assert out.timezone == "Asia/Tashkent"
    assert out.model_dump(by_alias=True)["from"] == "2026-10-28"


@pytest.mark.asyncio
async def test_get_summary_with_queue_id_filters_by_linkedid(monkeypatch):
    async def fake_resolve_queues(session, tenant_id, queue_id):
        assert queue_id == "q1"
        return [_queue(id="q1")]

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        return [_queue_log(callid="1.0", queuename="t1-q-q1")]

    async def fake_fetch_cdr_rows(session, tenant_code, start, end):
        return [_cdr_call(uniqueid="1.0", linkedid="1.0"), _cdr_call(uniqueid="2.0", linkedid="2.0")]

    monkeypatch.setattr(rp, "_resolve_queues", fake_resolve_queues)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)
    monkeypatch.setattr(rp, "_fetch_cdr_rows", fake_fetch_cdr_rows)

    out = await rp.get_summary(from_="2026-10-28", to="2026-10-28", queue_id="q1", session=None, user=USER)
    assert out.total == 1  # faqat linkedid=1.0 (queue_log.callid bilan mos)


# --------------------------------------------------------------- /reports/queues
@pytest.mark.asyncio
async def test_get_queues_report_builds_one_row_per_queue(monkeypatch):
    queue = _queue(id="q1", name="Sotuv", sla_seconds=10)

    async def fake_resolve_queues(session, tenant_id, queue_id):
        return [queue]

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        assert queuenames == ["t1-q-q1"]
        return [_queue_log(queuename="t1-q-q1", event="CONNECT", data1="5"),
                _queue_log(queuename="t1-q-q1", event="ABANDON", data3="30")]

    monkeypatch.setattr(rp, "_resolve_queues", fake_resolve_queues)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)

    out = await rp.get_queues_report(from_="2026-10-28", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert len(out.items) == 1
    assert out.items[0].queue_id == "q1"
    assert out.items[0].answered == 1
    assert out.items[0].abandoned == 1
    assert out.items[0].sla_percent == 50.0


# --------------------------------------------------------------- /reports/agents
@pytest.mark.asyncio
async def test_get_agents_report_no_members_returns_empty(monkeypatch):
    async def fake_agent_members(session, tenant_id, queue_id):
        return []

    monkeypatch.setattr(rp, "_agent_members", fake_agent_members)
    out = await rp.get_agents_report(from_="2026-10-28", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert out.items == []


@pytest.mark.asyncio
async def test_get_agents_report_builds_row_with_login_and_queue_stats(monkeypatch):
    ext = _extension(id="e1", number="101", name="Operator Ali")
    queue = _queue(id="q1")

    async def fake_agent_members(session, tenant_id, queue_id):
        return [(ext, queue)]

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        return [_queue_log(agent="Operator Ali", event="CONNECT"),
                _queue_log(agent="Operator Ali", event="COMPLETECALLER", data2="42")]

    events = [
        _agent_event(event="login", at=datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc), extension_id="e1"),
    ]

    monkeypatch.setattr(rp, "_agent_members", fake_agent_members)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)

    out = await rp.get_agents_report(
        from_="2026-10-28", to="2026-10-28", queue_id=None, session=_Session(events), user=USER,
    )
    assert len(out.items) == 1
    row = out.items[0]
    assert row.extension == "101"
    assert row.answered == 1
    assert row.talk_seconds == 42
    assert row.login_seconds > 0


@pytest.mark.asyncio
async def test_get_agents_report_dedups_extension_in_multiple_queues(monkeypatch):
    ext = _extension(id="e1", number="101", name="Operator Ali")

    async def fake_agent_members(session, tenant_id, queue_id):
        return [(ext, _queue(id="q1")), (ext, _queue(id="q2"))]

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        return []

    monkeypatch.setattr(rp, "_agent_members", fake_agent_members)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)

    out = await rp.get_agents_report(from_="2026-10-28", to="2026-10-28", queue_id=None,
                                      session=_Session([]), user=USER)
    assert len(out.items) == 1  # BIR extension — ikki navbatga a'zo bo'lsa ham bitta qator


@pytest.mark.asyncio
async def test_get_agents_report_with_queue_id_checks_tenant_scope(monkeypatch):
    checked = {}

    async def fake_get_tenant_scoped_or_404(session, model, tenant_id, entity_id, **kw):
        checked["entity_id"] = entity_id
        return _queue(id=entity_id)

    async def fake_agent_members(session, tenant_id, queue_id):
        return []

    monkeypatch.setattr(rp, "get_tenant_scoped_or_404", fake_get_tenant_scoped_or_404)
    monkeypatch.setattr(rp, "_agent_members", fake_agent_members)

    await rp.get_agents_report(from_="2026-10-28", to="2026-10-28", queue_id="q9", session=None, user=USER)
    assert checked["entity_id"] == "q9"


# --------------------------------------------------------------- /reports/hourly, /reports/daily
@pytest.mark.asyncio
async def test_get_hourly_report_without_queue_filter_returns_24_rows(monkeypatch):
    async def fake_fetch_cdr_rows(session, tenant_code, start, end):
        return [_cdr_call()]

    monkeypatch.setattr(rp, "_fetch_cdr_rows", fake_fetch_cdr_rows)
    out = await rp.get_hourly_report(from_="2026-10-28", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert len(out.items) == 24
    assert sum(h.answered for h in out.items) == 1


@pytest.mark.asyncio
async def test_get_hourly_report_with_queue_id_filters_calls(monkeypatch):
    async def fake_get_tenant_scoped_or_404(session, model, tenant_id, entity_id, **kw):
        return _queue(id=entity_id)

    async def fake_fetch_queue_log_rows(session, queuenames, start, end):
        return [_queue_log(callid="1.0")]

    async def fake_fetch_cdr_rows(session, tenant_code, start, end):
        return [_cdr_call(uniqueid="1.0", linkedid="1.0"), _cdr_call(uniqueid="2.0", linkedid="2.0")]

    monkeypatch.setattr(rp, "get_tenant_scoped_or_404", fake_get_tenant_scoped_or_404)
    monkeypatch.setattr(rp, "_fetch_queue_log_rows", fake_fetch_queue_log_rows)
    monkeypatch.setattr(rp, "_fetch_cdr_rows", fake_fetch_cdr_rows)

    out = await rp.get_hourly_report(from_="2026-10-28", to="2026-10-28", queue_id="q1", session=None, user=USER)
    assert sum(h.answered for h in out.items) == 1  # faqat linkedid=1.0


@pytest.mark.asyncio
async def test_get_daily_report_covers_every_day_in_range(monkeypatch):
    async def fake_fetch_cdr_rows(session, tenant_code, start, end):
        return [_cdr_call()]

    monkeypatch.setattr(rp, "_fetch_cdr_rows", fake_fetch_cdr_rows)
    out = await rp.get_daily_report(from_="2026-10-26", to="2026-10-28", queue_id=None, session=None, user=USER)
    assert [d.date for d in out.items] == ["2026-10-26", "2026-10-27", "2026-10-28"]
    assert sum(d.total for d in out.items) == 1
