"""`/reports/*` — HAQIQIY Postgres'ga qarshi (`innova-m0-postgres-1`), lekin
ALOHIDA `reports_test` bazasida (m2b-contract.md §5 talabi: asosiy `innova`
bazasiga HECH QACHON yozilmaydi). HTTP orqali EMAS (API konteyneri bu
agentning yangi kodi bilan qayta qurilmagan) — to'g'ridan-to'g'ri
`report_defs.py`/ORM qatlamini HAQIQIY Postgres semantikasiga (timestamptz,
indekslar) qarshi tekshiradi.

Ulanish: `innova-net` tashqi portga chiqarilmagan (architecture.md xavf
hududlari) — shu sabab konteyner IP'si `docker inspect` orqali avtomatik
topiladi (host konteyner bridge tarmog'iga to'g'ridan-to'g'ri yeta oladi)."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Cdr, QueueLog
from app.services.report_defs import build_daily, build_hourly, build_summary, report_calls_from_rows

_DB_NAME = "reports_test"
_DB_USER = "innova"
_DB_PASSWORD = "nvpDPrdUzNKZ4dmzqIfVl28Xzxdg5bh"
_CONTAINER = "innova-m0-postgres-1"


def _postgres_container_ip() -> str | None:
    try:
        out = subprocess.run(
            ["docker", "inspect", _CONTAINER, "--format", "{{json .NetworkSettings.Networks}}"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        networks = json.loads(out)
        return next(iter(networks.values()))["IPAddress"]
    except Exception:
        return None


_CONTAINER_IP = _postgres_container_ip()
_DATABASE_URL = (
    f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_CONTAINER_IP}:5432/{_DB_NAME}"
    if _CONTAINER_IP else None
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        _DATABASE_URL is None, reason=f"`{_CONTAINER}` topilmadi/ishlamayapti — `docker inspect` muvaffaqiyatsiz",
    ),
]


@pytest.fixture()
async def session():
    """HAR safar ALOHIDA engine — asosiy `innova` sozlamalaridan (`app.db.session`)
    MUSTAQIL, faqat `reports_test`ga ulanadi (asosiy bazaga yozish MUMKIN EMAS,
    chunki bu yerda umuman ulanmaydi)."""
    engine = create_async_engine(_DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as s:
        yield s
    await engine.dispose()


_ACCOUNTCODE = "m2b_reports_live_probe"


async def _cleanup(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM cdr WHERE accountcode = :a"), {"a": _ACCOUNTCODE})
    await session.execute(text("DELETE FROM queue_log WHERE queuename = :q"), {"q": f"{_ACCOUNTCODE}-q-probe"})
    await session.commit()


async def test_cdr_query_and_report_defs_match_against_real_postgres(session: AsyncSession):
    """Haqiqiy `timestamptz` ustuni + `cdr(accountcode, calldate)` indeksi
    bilan: javob berilgan/o'tkazib yuborilgan/bloklangan sonlar kutilganiga
    AYNAN teng bo'lishi SHART (ORM mapping + report_defs birgalikda)."""
    await _cleanup(session)
    base = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)  # 10:00 Tashkent
    rows = [
        Cdr(calldate=base, src="912345678", dst="s", dcontext="t1-dest-x",
            channel="PJSIP/t1-trunk-1-x", dstchannel="PJSIP/t1-101-x", lastapp="Dial",
            duration=20, billsec=15, disposition="ANSWERED", accountcode=_ACCOUNTCODE,
            uniqueid="live-1.0", linkedid="live-1.0", userfield=None, sequence=0),
        Cdr(calldate=base + timedelta(minutes=5), src="912345679", dst="s", dcontext="t1-dest-x",
            channel="PJSIP/t1-trunk-1-x", dstchannel=None, lastapp="Dial",
            duration=10, billsec=0, disposition="NO ANSWER", accountcode=_ACCOUNTCODE,
            uniqueid="live-2.0", linkedid="live-2.0", userfield=None, sequence=0),
        Cdr(calldate=base + timedelta(minutes=10), src="912345680", dst="s", dcontext="t1-dest-x",
            channel="PJSIP/t1-trunk-1-x", dstchannel=None, lastapp="Dial",
            duration=5, billsec=0, disposition="NO ANSWER", accountcode=_ACCOUNTCODE,
            uniqueid="live-3.0", linkedid="live-3.0", userfield="blacklisted", sequence=0),
    ]
    session.add_all(rows)
    await session.commit()
    try:
        start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)  # 2026-10-28 00:00 Tashkent
        end = datetime(2026, 10, 28, 19, 0, tzinfo=timezone.utc)
        fetched = (await session.execute(
            select(Cdr).where(Cdr.accountcode == _ACCOUNTCODE, Cdr.calldate >= start, Cdr.calldate < end)
        )).scalars().all()
        assert len(fetched) == 3
        calls = report_calls_from_rows(list(fetched))
        summary = build_summary(calls, "Asia/Tashkent", [])
        assert summary["total"] == 3
        assert summary["inbound"] == 3
        assert summary["answered"] == 1
        assert summary["missed"] == 1
        assert summary["blocked"] == 1
        hourly = build_hourly(calls, "Asia/Tashkent")
        assert sum(h["inbound"] for h in hourly) == summary["inbound"]
        daily = build_daily(calls, "Asia/Tashkent", date(2026, 10, 28), date(2026, 10, 28))
        assert daily[0]["total"] == 3
    finally:
        await _cleanup(session)


async def test_queue_log_orm_mapping_reads_real_table(session: AsyncSession):
    """`QueueLog` ORM modeli (`app/db/models.py`) haqiqiy `queue_log`
    jadvali ustunlariga TO'G'RI ulanganini tasdiqlaydi (0001_schema.sql)."""
    await _cleanup(session)
    queuename = f"{_ACCOUNTCODE}-q-probe"
    await session.execute(text(
        "INSERT INTO queue_log (time, callid, queuename, agent, event, data1, data2, data3) "
        "VALUES (now(), 'live-1.0', :q, 'Operator Live', 'CONNECT', '7', NULL, NULL)"
    ), {"q": queuename})
    await session.commit()
    try:
        rows = (await session.execute(select(QueueLog).where(QueueLog.queuename == queuename))).scalars().all()
        assert len(rows) == 1
        assert rows[0].event == "CONNECT"
        assert rows[0].agent == "Operator Live"
        assert rows[0].data1 == "7"
    finally:
        await _cleanup(session)


async def test_92_day_50k_call_query_and_compute_within_2_seconds(session: AsyncSession):
    """Samaradorlik nishoni (m2b-contract.md §5): 92 kun x ~50k qo'ng'iroq —
    DB so'rov + Python hisoblash JAMI 2 soniyadan oshmasligi SHART."""
    await _cleanup(session)
    n = 50_000
    base = datetime(2026, 7, 1, tzinfo=timezone.utc)
    await session.execute(text(
        """
        INSERT INTO cdr (calldate, src, dst, dcontext, channel, dstchannel, lastapp,
                          duration, billsec, disposition, accountcode, uniqueid, linkedid, userfield, sequence)
        SELECT
          CAST(:base AS timestamptz) + (i * interval '159 seconds'),
          '998901112233', 's', 'perf-dest-x',
          CASE WHEN i % 5 = 0 THEN 'PJSIP/perf-internal-' || i ELSE 'PJSIP/perf-trunk-1-' || i END,
          CASE WHEN i % 3 = 0 THEN 'PJSIP/perf-101-' || i ELSE NULL END,
          'Dial',
          CASE WHEN i % 3 = 0 THEN 20 ELSE 0 END,
          CASE WHEN i % 3 = 0 THEN 15 ELSE 0 END,
          CASE WHEN i % 3 = 0 THEN 'ANSWERED' ELSE 'NO ANSWER' END,
          :account, 'perf-' || i || '.0', 'perf-' || i || '.0', NULL, 0
        FROM generate_series(1, :n) AS i
        """
    ), {"base": base, "account": _ACCOUNTCODE, "n": n})
    await session.commit()
    try:
        start = base - timedelta(days=1)
        end = base + timedelta(days=92)
        t0 = time.perf_counter()
        rows = (await session.execute(
            select(Cdr).where(Cdr.accountcode == _ACCOUNTCODE, Cdr.calldate >= start, Cdr.calldate < end)
        )).scalars().all()
        t1 = time.perf_counter()
        calls = report_calls_from_rows(list(rows))
        build_summary(calls, "Asia/Tashkent", [])
        build_hourly(calls, "Asia/Tashkent")
        build_daily(calls, "Asia/Tashkent", start.date(), end.date())
        t2 = time.perf_counter()

        assert len(rows) >= n * 0.9
        db_seconds = t1 - t0
        compute_seconds = t2 - t1
        total_seconds = t2 - t0
        print(f"\n[perf] DB so'rov: {db_seconds:.3f}s, Python hisob: {compute_seconds:.3f}s, "
              f"JAMI: {total_seconds:.3f}s ({len(rows)} qator)")
        assert total_seconds < 2.0, f"2s chegarasidan oshdi: {total_seconds:.3f}s"
    finally:
        await _cleanup(session)
