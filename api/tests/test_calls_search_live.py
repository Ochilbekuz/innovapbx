"""M9 — `/calls` kengaytirilgan qidiruvi HAQIQIY Postgres'da (`reports_test`): tenant ajratish,
PIN yorlig'i (`cdr.pin_label`), CallerID ismi, yozuv filtri, operator faqat o'z qo'ng'iroqlari."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.calls import _searched_calls
from app.core.permissions import ALL, CALLS_READ_OWN
from app.db.models import Cdr, Tenant
from app.services.cdr_search import build_search
from tests.test_reports_live import _DATABASE_URL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_DATABASE_URL is None, reason="reports_test Postgres konteyneri topilmadi"),
]

T0 = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def tenant():
    engine = create_async_engine(_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    tid, code = str(uuid.uuid4()), f"cs{secrets.token_hex(3)}"
    async with factory() as s:
        s.add(Tenant(id=tid, code=code, name="CDR qidiruv sinovi", timezone="Asia/Tashkent"))
        await s.flush()
        rows = [
            ("a1", '"Ali Valiyev" <201>', "201", "998901112233", "Sotuv", 40),
            ("a2", '"201" <201>', "201", "202", None, 5),
            ("a3", '"Karim" <203>', "203", "998712223344", None, 90),
        ]
        for i, (uid, clid, src, dst, pin, dur) in enumerate(rows):
            s.add(Cdr(calldate=T0 + timedelta(minutes=i), clid=clid, src=src, dst=dst, dcontext="from-internal",
                      channel=f"PJSIP/{src}-0000000{i}", dstchannel="", disposition="ANSWERED", duration=dur,
                      billsec=dur, accountcode=code, uniqueid=uid, linkedid=uid, pin_label=pin, sequence=1))
        # Boshqa tenant qatori (accountcode boshqa) — hech qachon ko'rinmasligi kerak.
        s.add(Cdr(calldate=T0, clid='"Ali" <201>', src="201", dst="998901112233", disposition="ANSWERED",
                  duration=40, billsec=40, accountcode=f"x{code}", uniqueid="other1", linkedid="other1", sequence=1))
        await s.commit()
    try:
        yield factory, tid, code
    finally:
        async with factory() as s:
            await s.execute(text("DELETE FROM cdr WHERE accountcode IN (:c, :o)"), {"c": code, "o": f"x{code}"})
            await s.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await s.commit()
        await engine.dispose()


def _user(tid: str, code: str, perms: list[str]):
    return SimpleNamespace(tenant_id=tid, tenant=SimpleNamespace(code=code), extension_id=None,
                           role=SimpleNamespace(permissions=perms))


async def _search(factory, user, **kw):
    async with factory() as s:
        calls = await _searched_calls(s, user, from_=None, to=None, q=None, direction=None, search=build_search(**kw))
    return sorted(c.uniqueid for c in calls)


async def test_admin_search_fields_and_tenant_isolation(tenant):
    factory, tid, code = tenant
    admin = _user(tid, code, [ALL])
    assert await _search(factory, admin) == ["a1", "a2", "a3"]
    assert await _search(factory, admin, account="sot") == ["a1"]
    assert await _search(factory, admin, name="vali") == ["a1"]
    assert await _search(factory, admin, dst="998", dst_mode="begins", dst_not=True) == ["a2"]
    assert await _search(factory, admin, min_duration=30, max_duration=60) == ["a1"]
    assert await _search(factory, admin, recording="with") == []
    assert await _search(factory, admin, recording="without") == ["a1", "a2", "a3"]


async def test_pin_label_and_name_are_exposed_on_calls(tenant):
    factory, tid, code = tenant
    async with factory() as s:
        calls = await _searched_calls(s, _user(tid, code, [ALL]), from_=None, to=None, q=None,
                                      direction=None, search=build_search(src="201", src_mode="exact"))
    by_id = {c.uniqueid: c for c in calls}
    assert by_id["a1"].pin_label == "Sotuv" and by_id["a1"].src_name == "Ali Valiyev"
    assert by_id["a2"].src_name is None


async def test_operator_without_extension_sees_nothing(tenant):
    factory, tid, code = tenant
    assert await _search(factory, _user(tid, code, [CALLS_READ_OWN])) == []
