"""`crm_call_links` tozalovchi — HAQIQIY Postgres (`reports_test`): 30 kundan eskisi o'chadi, yangisi qoladi."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.prov import purge_requests_once
from app.db.models import CrmCallLink, Tenant
from app.services.integrations.crm import LINK_RETENTION_DAYS
from tests.test_reports_live import _DATABASE_URL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_DATABASE_URL is None, reason="reports_test Postgres konteyneri topilmadi"),
]

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def factory():
    engine = create_async_engine(_DATABASE_URL)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def test_purge_removes_only_links_older_than_retention(factory):
    tid = str(uuid.uuid4())
    age = timedelta(days=LINK_RETENTION_DAYS)
    async with factory() as s:
        s.add(Tenant(id=tid, code=f"cl{secrets.token_hex(3)}", name="CRM link sinov", timezone="Asia/Tashkent"))
        await s.flush()
        for linkedid, created in (("eski", NOW - age - timedelta(minutes=1)), ("chegara", NOW - age + timedelta(minutes=1)),
                                  ("yangi", NOW - timedelta(hours=1))):
            s.add(CrmCallLink(tenant_id=tid, provider="bitrix24", linkedid=linkedid, external_call_id="x",
                              origin="pbx", shown_users=[], created_at=created))
        await s.commit()
    try:
        await purge_requests_once(factory, NOW)
        async with factory() as s:
            left = (await s.execute(select(CrmCallLink.linkedid).where(CrmCallLink.tenant_id == tid))).scalars().all()
        assert sorted(left) == ["chegara", "yangi"]
    finally:
        async with factory() as s:
            await s.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await s.commit()
