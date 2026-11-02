"""M6 kampaniyalar — HAQIQIY Postgres (`reports_test`) ustida: tekshiruv, import (qora ro'yxat/opt-out),
holat o'tishlari, dialer claim (max_concurrent, oyna), natija (idempotent, retry → failed), DTMF opt-out,
supurgich (LOST), AMI xatosida qaytarish, completed."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import ApiError
from app.db.models import AudioFile, Blacklist, Campaign, CampaignAttempt, CampaignContact, DialNumber, Tenant
from app.services import campaign_dialer as dialer
from app.services import campaigns as svc
from tests.test_reports_live import _DATABASE_URL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_DATABASE_URL is None, reason="reports_test Postgres konteyneri topilmadi"),
]

MONDAY_NOON_UTC = datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc)  # Toshkent 12:00, Du


class FakeAmi:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[dict] = []

    async def action(self, name, **fields):
        self.calls.append({"Action": name, **fields})
        return {"Response": "Success" if self.ok else "Error", "Message": "x"}


@pytest.fixture()
async def factory():
    engine = create_async_engine(_DATABASE_URL)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture()
async def tenant(factory):
    tid = str(uuid.uuid4())
    code = f"m6{secrets.token_hex(3)}"
    async with factory() as s:
        s.add(Tenant(id=tid, code=code, name="M6 sinov", timezone="Asia/Tashkent"))
        await s.flush()
        s.add(AudioFile(id=str(uuid.uuid4()), tenant_id=tid, name="xabar", source="upload",
                        storage_path=f"sounds/{code}/a1", duration_ms=1000))
        await s.commit()
    yield tid, code
    async with factory() as s:
        await s.execute(text("DELETE FROM campaigns WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        await s.commit()


async def _audio_id(s, tid) -> str:
    return (await s.execute(select(AudioFile.id).where(AudioFile.tenant_id == tid))).scalar_one()


async def _campaign(factory, tid, csv_text="998900000001\n998900000002\n998900000003", **kw) -> str:
    async with factory() as s:
        fields = svc.merge_fields({}, {"name": f"K{secrets.token_hex(2)}", "mode": "message",
                                       "audio_id": await _audio_id(s, tid), **kw})
        await svc.validate_campaign(s, tid, fields)
        item = Campaign(tenant_id=tid, **fields.model_dump())
        s.add(item)
        await s.flush()
        await svc.import_contacts(s, tid, item, csv_text, False)
        await svc.transition(s, item, "start")
        await s.commit()
        return str(item.id)


async def _contacts(factory, cid) -> dict[str, CampaignContact]:
    async with factory() as s:
        rows = (await s.execute(select(CampaignContact).where(CampaignContact.campaign_id == cid))).scalars()
        return {c.number: c for c in rows}


async def test_validate_refs_and_name(factory, tenant):
    tid, _ = tenant
    async with factory() as s:
        audio = await _audio_id(s, tid)
        with pytest.raises(ApiError) as exc:
            await svc.validate_campaign(s, tid, svc.merge_fields({}, {"name": "A", "mode": "message",
                                                                      "audio_id": str(uuid.uuid4())}))
        assert exc.value.code == "campaign_bad_audio"
        with pytest.raises(ApiError) as exc:
            await svc.validate_campaign(s, tid, svc.merge_fields({}, {"name": "A", "mode": "connect",
                                                                      "target_number": "201"}))
        assert exc.value.code == "campaign_bad_target"
        target = str(uuid.uuid4())
        await s.execute(text("INSERT INTO call_targets (id, tenant_id, kind, label) VALUES (:id, :t, 'queue', 'q')"),
                        {"id": target, "t": tid})
        s.add(DialNumber(tenant_id=tid, number="201", target_id=target))
        await s.flush()
        await svc.validate_campaign(s, tid, svc.merge_fields({}, {"name": "A", "mode": "connect",
                                                                  "target_number": "201"}))
        s.add(Campaign(tenant_id=tid, name="A", mode="message", audio_id=audio))
        await s.flush()
        with pytest.raises(ApiError) as exc:
            await svc.validate_campaign(s, tid, svc.merge_fields({}, {"name": "A", "mode": "message",
                                                                      "audio_id": audio}))
        assert exc.value.code == "name_taken"
        await s.rollback()


async def test_import_blacklist_optout_and_transitions(factory, tenant):
    tid, _ = tenant
    async with factory() as s:
        s.add(Blacklist(tenant_id=tid, number="998900000002"))
        await s.execute(text("INSERT INTO campaign_optouts (tenant_id, number) VALUES (:t, '998900000003')"),
                        {"t": tid})
        item = Campaign(tenant_id=tid, name="Imp", mode="message", audio_id=await _audio_id(s, tid))
        s.add(item)
        await s.flush()
        with pytest.raises(ApiError) as exc:
            await svc.transition(s, item, "start")
        assert exc.value.code == "campaign_empty"
        report = await svc.import_contacts(s, tid, item, "tel,ism\n998900000001,A\n998900000002\n998900000003\n"
                                                         "998900000001\nxx", False)
        assert {k: report[k] for k in ("added", "duplicates", "skipped", "invalid_count")} == \
            {"added": 1, "duplicates": 1, "skipped": 2, "invalid_count": 1}
        again = await svc.import_contacts(s, tid, item, "998900000001\n998900000004", False)
        assert (again["added"], again["duplicates"]) == (1, 1)
        stats = (await svc.stats_for(s, [str(item.id)]))[str(item.id)]
        assert (stats.total, stats.pending, stats.skipped) == (4, 2, 2)
        await svc.transition(s, item, "start")
        assert item.status == "running" and item.started_at is not None
        with pytest.raises(ApiError) as exc:
            await svc.import_contacts(s, tid, item, "998900000009", True)
        assert exc.value.code == "campaign_running"
        with pytest.raises(ApiError) as exc:
            await svc.transition(s, item, "start")
        assert exc.value.code == "campaign_bad_state"
        await svc.transition(s, item, "pause")
        replaced = await svc.import_contacts(s, tid, item, "998900000009", True)
        assert replaced["added"] == 1
        await svc.transition(s, item, "stop")
        assert item.status == "stopped" and item.finished_at is not None
        with pytest.raises(ApiError):
            await svc.transition(s, item, "start")
        await s.commit()


async def test_dialer_respects_concurrency_window_and_records(factory, tenant):
    tid, code = tenant
    cid = await _campaign(factory, tid, max_concurrent=2, max_attempts=2, retry_delay_s=60, callerid="712000000")
    ami = FakeAmi()
    assert await dialer.dialer_cycle(factory, ami, MONDAY_NOON_UTC) == 2   # sweep + barcha running kampaniyalar
    assert await dialer.dial_campaign(factory, ami, cid, MONDAY_NOON_UTC) == 0  # bo'sh joy yo'q
    call = ami.calls[0]
    assert call["Channel"] == f"Local/998900000001@{code}-campaign-dial/n"
    assert f"INNOVA_CAMP_AUDIO=/var/lib/innova/sounds/{code}/a1" in call["Variable"]
    assert "INNOVA_CAMP_CID=712000000" in call["Variable"]
    async with factory() as s:
        attempts = (await s.execute(select(CampaignAttempt).where(CampaignAttempt.campaign_id == cid)
                                    .order_by(CampaignAttempt.id))).scalars().all()
        a1, a2 = attempts
        assert await dialer.record_result(s, a1.id, "ANSWER", "12", MONDAY_NOON_UTC)
        assert not await dialer.record_result(s, a1.id, "BUSY", "", MONDAY_NOON_UTC)  # idempotent
        assert await dialer.record_result(s, a2.id, "BUSY", "", MONDAY_NOON_UTC)
        await s.commit()
    c = await _contacts(factory, cid)
    assert (c["998900000001"].status, c["998900000001"].billsec, c["998900000001"].result) == ("done", 12, "ANSWER")
    assert (c["998900000002"].status, c["998900000002"].result) == ("retry", "BUSY")
    # 3-kontakt teriladi; retry hali vaqti kelmagan
    assert await dialer.dial_campaign(factory, ami, cid, MONDAY_NOON_UTC) == 1
    assert ami.calls[-1]["Channel"].startswith("Local/998900000003@")
    # oyna tashqarisi (Toshkent 21:00) — terilmaydi
    late = MONDAY_NOON_UTC + timedelta(hours=9)
    async with factory() as s:
        await s.execute(text("UPDATE campaign_attempts SET ended_at = now() WHERE campaign_id = :c"), {"c": cid})
        await s.commit()
    assert await dialer.dial_campaign(factory, ami, cid, late) == 0
    # retry vaqti keldi → 2-urinish → BUSY → failed (max_attempts=2)
    later = MONDAY_NOON_UTC + timedelta(minutes=2)
    assert await dialer.dial_campaign(factory, ami, cid, later) == 1
    async with factory() as s:
        open_attempt = (await s.execute(select(CampaignAttempt).where(
            CampaignAttempt.campaign_id == cid, CampaignAttempt.ended_at.is_(None)))).scalar_one()
        await dialer.record_result(s, open_attempt.id, "CANCEL", "", later)
        await s.commit()
    c = await _contacts(factory, cid)
    assert (c["998900000002"].status, c["998900000002"].attempts, c["998900000002"].result) == \
        ("failed", 2, "NOANSWER")


async def test_key_optout_sweep_revert_and_complete(factory, tenant):
    tid, _ = tenant
    cid = await _campaign(factory, tid, csv_text="998900000011\n998900000012", max_concurrent=1,
                          dtmf_optout=True, max_attempts=1)
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, MONDAY_NOON_UTC) == 1
    async with factory() as s:
        attempt = (await s.execute(select(CampaignAttempt).where(CampaignAttempt.campaign_id == cid))).scalar_one()
        assert await dialer.record_key(s, attempt.id, "1") == "none"  # connect yoqilmagan
        assert await dialer.record_key(s, attempt.id, "x") == "none"
        assert await dialer.record_key(s, attempt.id, "9") == "optout"
        await s.commit()
        await dialer.record_result(s, attempt.id, "ANSWER", "5", MONDAY_NOON_UTC)
        await s.commit()
    c = await _contacts(factory, cid)
    assert (c["998900000011"].status, c["998900000011"].result, c["998900000011"].key,
            c["998900000011"].billsec) == ("skipped", "OPTOUT", "9", 5)
    # AMI xato → urinish qaytariladi
    assert await dialer.dial_campaign(factory, FakeAmi(ok=False), cid, MONDAY_NOON_UTC) == 0
    c = await _contacts(factory, cid)
    assert (c["998900000012"].status, c["998900000012"].attempts) == ("pending", 0)
    # terildi, hangup handler kelmadi → 3 soatdan keyin LOST → failed (max_attempts=1)
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, MONDAY_NOON_UTC) == 1
    async with factory() as s:
        assert await dialer.sweep_lost(s, MONDAY_NOON_UTC + timedelta(hours=4)) >= 1
        await s.commit()
    c = await _contacts(factory, cid)
    assert (c["998900000012"].status, c["998900000012"].result) == ("failed", "LOST")
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, MONDAY_NOON_UTC) == 0
    async with factory() as s:
        camp = await s.get(Campaign, cid)
        assert camp.status == "completed" and camp.finished_at is not None
    # opt-out keyingi kampaniyada — skipped
    cid2 = await _campaign(factory, tid, csv_text="998900000011\n998900000013")
    c2 = await _contacts(factory, cid2)
    assert (c2["998900000011"].status, c2["998900000011"].result) == ("skipped", "OPTOUT")



async def test_stop_closes_open_contacts_and_inflight_result(factory, tenant):
    """To'xtatish: pending/retry → skipped/STOPPED; terilayotgan qo'ng'iroq natijasi retry emas — skipped."""
    tid, _ = tenant
    cid = await _campaign(factory, tid, csv_text="998900000021\n998900000022\n998900000023", max_concurrent=1,
                          max_attempts=3)
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, MONDAY_NOON_UTC) == 1
    async with factory() as s:
        item = await s.get(Campaign, cid)
        await svc.transition(s, item, "stop")
        await s.commit()
        attempt = (await s.execute(select(CampaignAttempt).where(CampaignAttempt.campaign_id == cid))).scalar_one()
        assert await dialer.record_result(s, attempt.id, "BUSY", "", MONDAY_NOON_UTC)
        await s.commit()
    c = await _contacts(factory, cid)
    assert sorted((x.status, x.result, x.next_attempt_at) for x in c.values()) == [
        ("skipped", "BUSY", None), ("skipped", "STOPPED", None), ("skipped", "STOPPED", None)]
    async with factory() as s:
        stats = (await svc.stats_for(s, [cid]))[cid]
    assert (stats.pending, stats.retry, stats.dialing, stats.skipped) == (0, 0, 0, 3)

async def test_overnight_window_and_days(factory, tenant):
    tid, _ = tenant
    cid = await _campaign(factory, tid, csv_text="998900000021", window_start=time(22), window_end=time(2),
                          days=[1])
    sunday_late = datetime(2026, 11, 1, 21, 0, tzinfo=timezone.utc)  # Toshkent Du 02:00 → Ya oynasi, yo'q
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, sunday_late) == 0
    monday_late = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)  # Toshkent Du 23:00
    assert await dialer.dial_campaign(factory, FakeAmi(), cid, monday_late) == 1
