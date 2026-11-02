"""M5a apply — HAQIQIY Postgres (`reports_test`, asosiy `innova` EMAS) ustida to'liq
fon vazifasi (`run_apply_job`): fixture to'plami -> har tur bo'yicha son, qayta
apply -> 0 yaratildi, `INNOVA_TEST_FAIL_AT=routes|audio` -> hech narsa qolmaydi,
sirlar CSV/audit/ish JSON'ida yo'q. Tashqi qismlar (pre_import zaxira, Asterisk
dialplan/AMI) almashtiriladi — ular o'z testlarida; bu yerda DB atomarligi va
haqiqiy ffmpeg o'girish tekshiriladi."""
from __future__ import annotations

import json
import re
import secrets
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import AuditLog, Extension, MigrationItem, MigrationJob, Tenant
from app.services.crypto import encrypt_secret
from app.services.fpbx import apply_job, bundle
from app.services.fpbx import plan as plan_mod
from app.services.fpbx.apply_plan import build_report_csv
from app.services.fpbx.writers import WriteCtx, WriteError, refs
from app.services.target_resolution import create_target
from tests.test_fpbx_plan import _EXPECTED_CREATE_COUNTS, FIXTURE, SECRET_NEEDLES
from tests.test_reports_live import _DATABASE_URL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_DATABASE_URL is None, reason="reports_test Postgres konteyneri topilmadi"),
]

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_COUNTED = ("extensions", "trunks", "ivrs", "inbound_routes", "outbound_routes", "queues", "ring_groups",
            "audio_files", "moh_classes", "blacklist", "voicemail_boxes", "conferences", "migration_items")
_CLEANUP = (
    "DELETE FROM inbound_routes WHERE tenant_id = :t",
    "DELETE FROM time_conditions WHERE tenant_id = :t",
    "DELETE FROM ivr_options WHERE ivr_id IN (SELECT id FROM ivrs WHERE tenant_id = :t)",
    "DELETE FROM ivrs WHERE tenant_id = :t",
    "DELETE FROM announcements WHERE tenant_id = :t",
    "DELETE FROM moh_class_files WHERE moh_class_id IN (SELECT id FROM moh_classes WHERE tenant_id = :t)",
    "DELETE FROM tenants WHERE id = :t",
)


class _FakeLock:
    released = 0

    async def release(self) -> None:
        self.released += 1


@pytest.fixture(scope="module")
def extracted(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("fpbx-apply-live")
    bundle.extract_bundle(FIXTURE, dest, max_total_bytes=20 * 1024 * 1024 * 1024)
    return bundle.find_bundle_root(dest)


@pytest.fixture()
async def factory():
    engine = create_async_engine(_DATABASE_URL)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture()
async def tenant_id(factory):
    tid = str(uuid.uuid4())
    async with factory() as s:
        s.add(Tenant(id=tid, code=f"m5a{secrets.token_hex(4)}", name="M5a apply sinov"))
        await s.commit()
    yield tid
    async with factory() as s:  # RESTRICT FK'lar: avval bog'lovchi qatorlar, keyin tenant (CASCADE)
        for sql in _CLEANUP:
            await s.execute(text(sql), {"t": tid})
        await s.commit()


@pytest.fixture()
def sounds(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "innova_db_key", "m5a-apply-live-test-key")
    monkeypatch.setattr(settings, "sounds_dir", str(tmp_path))
    monkeypatch.delenv("INNOVA_TEST_FAIL_AT", raising=False)

    async def _no_backup(_session, _tenant_id):
        return None

    async def _dialplan(_session, _tenant_id, _user_id, _ami):
        return "777"

    async def _reload(_ami):
        return True

    monkeypatch.setattr(apply_job, "_pre_import_backup", _no_backup)
    monkeypatch.setattr(apply_job, "_apply_dialplan", _dialplan)
    monkeypatch.setattr(apply_job, "_POST_APPLY", ())
    monkeypatch.setattr(apply_job, "_safe_reload", _reload)
    return tmp_path


async def _new_job(factory, tenant_id: str, bundle_dir: Path, *, rotate: bool = False, mutate=None) -> str:
    async with factory() as s:
        analysis = await plan_mod.analyze(bundle_dir, s, tenant_id)
        items = [e.public_dict() for e in analysis.items]
        if mutate:
            mutate(items)
        job = MigrationJob(tenant_id=tenant_id, source="upload", status="applying", bundle_path=str(bundle_dir),
                           plan={"items": items, "ignored": [], "warnings": []},
                           options={"rotate_weak_secrets": rotate})
        s.add(job)
        await s.commit()
        return str(job.id)


async def _run(factory, tenant_id: str, job_id: str) -> MigrationJob:
    lock = _FakeLock()
    await apply_job.run_apply_job(factory, lock, job_id, tenant_id, ami=None, user_id=None)
    assert lock.released == 1
    async with factory() as s:
        return await s.get(MigrationJob, job_id)


async def _counts(factory, tenant_id: str) -> dict[str, int]:
    async with factory() as s:
        return {t: (await s.execute(text(f"SELECT count(*) FROM {t} WHERE tenant_id = :t"),  # noqa: S608
                                    {"t": tenant_id})).scalar_one() for t in _COUNTED}


def _wavs(root: Path) -> list[Path]:
    return sorted(root.rglob("*.wav"))


def _assert_no_secrets(blob: str) -> None:
    """UUID'lar olib tashlanadi — qisqa raqamli PIN (masalan 4321) tasodifan UUID ichida uchrashi mumkin."""
    blob = _UUID.sub("<id>", blob)
    found = [needle for needle in SECRET_NEEDLES if needle in blob]
    assert not found, "sir topildi"


async def test_full_apply_then_idempotent(factory, tenant_id, extracted, sounds) -> None:
    job_id = await _new_job(factory, tenant_id, extracted, rotate=True)
    job = await _run(factory, tenant_id, job_id)
    assert job.status == "ok", job.error
    assert job.result["created"] == _EXPECTED_CREATE_COUNTS
    assert job.result["revision_id"] == "777"
    assert job.result["skipped"] == len(job.plan["items"]) - sum(_EXPECTED_CREATE_COUNTS.values())
    assert job.result["rotated"] == []  # fixture'da zaif SIP sirli ichki raqam yo'q (PIN'lar aylantirilmaydi)
    assert (job.step, job.progress, job.error) == (None, 100, None)
    counts = await _counts(factory, tenant_id)
    assert counts["extensions"] == 6 and counts["inbound_routes"] == 3 and counts["voicemail_boxes"] == 1
    assert counts["migration_items"] == sum(_EXPECTED_CREATE_COUNTS.values())
    wavs = _wavs(sounds)
    assert len(wavs) == counts["audio_files"] >= 2

    async with factory() as s:
        durations = (await s.execute(text("SELECT min(duration_ms) FROM audio_files WHERE tenant_id = :t"),
                                     {"t": tenant_id})).scalar_one()
        audit = (await s.execute(select(AuditLog.diff).where(AuditLog.tenant_id == tenant_id))).scalars().all()
        rows = (await s.execute(select(MigrationItem.kind, MigrationItem.source_ref, MigrationItem.innova_id)
                                .where(MigrationItem.job_id == job_id))).all()
    assert durations > 1
    assert [d["note"] for d in audit] == ["FreePBX importi"]
    created = {f"{k}:{r}": i for k, r, i in rows}
    report = build_report_csv(job.plan["items"], created=created, result=job.result, applied=True)
    assert "rotated" not in report and report.count("\n") == len(job.plan["items"]) + 1
    _assert_no_secrets(report + json.dumps(audit) + json.dumps([job.plan, job.result, job.error]))

    second = await _run(factory, tenant_id, await _new_job(factory, tenant_id, extracted))
    assert second.status == "ok", second.error
    assert {i["reason"] for i in second.plan["items"]} <= {"already_imported", "default_moh", "builtin"}
    assert second.result["created"] == {}
    assert await _counts(factory, tenant_id) == counts
    assert _wavs(sounds) == wavs


@pytest.mark.parametrize("stage", ["routes", "audio"])
async def test_test_fail_hook_leaves_nothing(factory, tenant_id, extracted, sounds, monkeypatch, stage) -> None:
    before = await _counts(factory, tenant_id)
    job_id = await _new_job(factory, tenant_id, extracted)
    monkeypatch.setenv("INNOVA_TEST_FAIL_AT", stage)
    job = await _run(factory, tenant_id, job_id)
    assert job.status == "failed"
    assert job.error["code"] == "test_fail"
    assert job.result is None
    assert await _counts(factory, tenant_id) == before
    assert _wavs(sounds) == []
    async with factory() as s:
        assert (await s.execute(select(AuditLog).where(AuditLog.tenant_id == tenant_id))).first() is None


async def test_stale_plan_fails_without_writes(factory, tenant_id, extracted, sounds) -> None:
    def rename_first(items: list[dict]) -> None:
        items[0]["name"] = "Boshqa nom"

    job = await _run(factory, tenant_id, await _new_job(factory, tenant_id, extracted, mutate=rename_first))
    assert job.status == "failed"
    assert job.error["code"] == "plan_stale"
    assert (await _counts(factory, tenant_id))["extensions"] == 0


async def _manual_extension(factory, tenant_id: str) -> tuple[str, str]:
    """Proof §7: admin qo'lda yaratgan 101 (migration_items izisiz)."""
    async with factory() as s:
        target = await create_target(s, tenant_id, "extension", "101 · Qolda 101")
        ext = Extension(tenant_id=tenant_id, target_id=target.id, number="101", name="Qolda 101",
                        sip_password_enc=await encrypt_secret(s, "QoldaParol-123456"))
        s.add(ext)
        await s.commit()
        return str(ext.id), str(target.id)


async def test_conflict_links_to_manual_extension(factory, tenant_id, extracted, sounds) -> None:
    manual_id, manual_target = await _manual_extension(factory, tenant_id)
    job = await _run(factory, tenant_id, await _new_job(factory, tenant_id, extracted))
    assert job.status == "ok", job.error
    assert job.result["created"]["extension"] == 5
    async with factory() as s:
        hosts = (await s.execute(text("SELECT auth_mode, host FROM trunks WHERE tenant_id = :t"),
                                 {"t": tenant_id})).all()
    assert dict(hosts)["ip"] == "203.0.113.10" and all(host for _, host in hosts)
    async with factory() as s:
        name = (await s.execute(select(Extension.name).where(Extension.id == manual_id))).scalar_one()
        option = (await s.execute(text(
            "SELECT o.target_id FROM ivr_options o JOIN ivrs i ON i.id = o.ivr_id "
            "WHERE i.tenant_id = :t AND o.digit = '1'"), {"t": tenant_id})).scalar_one()
        member = (await s.execute(text(
            "SELECT count(*) FROM ring_group_members m JOIN ring_groups g ON g.id = m.ring_group_id "
            "WHERE g.tenant_id = :t AND m.extension_id = :e"), {"t": tenant_id, "e": manual_id})).scalar_one()
    assert (name, str(option), member) == ("Qolda 101", manual_target, 1)
    report = build_report_csv(job.plan["items"], created={}, result=job.result, applied=True)
    row = next(line for line in report.splitlines() if line.startswith("extension,users:101,"))
    assert ",conflict," in row and row.endswith(",skipped,")


async def test_refs_resolution_after_import(factory, tenant_id, extracted, sounds) -> None:
    job = await _run(factory, tenant_id, await _new_job(factory, tenant_id, extracted))
    assert job.status == "ok", job.error
    async with factory() as s:
        code = (await s.get(Tenant, tenant_id)).code
        ctx = WriteCtx(session=s, tenant_id=tenant_id, tenant_code=code, job_id=str(job.id),
                       bundle_dir=extracted, sounds_dir=sounds)
        assert await refs.resolve_entity(ctx, None) is None
        assert await refs.resolve_entity(ctx, {"$ref": "audio:recordings:1"}) is not None
        assert await refs.resolve_entity(ctx, {"$ref": "trunk:trunks:99"}) is None
        assert await refs.resolve_entity(ctx, {"$ref": "nokind:x:1"}) is None
        ext_target = await refs.existing_target(ctx, "extension:users:101")
        assert ext_target is not None
        assert await refs.existing_target(ctx, "ring_group:ringgroups:600") is not None
        assert await refs.existing_target(ctx, "nokind:x:1") is None
        assert await refs.resolve_target(ctx, None, source_ref="r") is None
        assert await refs.resolve_target(ctx, {"$ref": "extension:users:101"}, source_ref="r") == ext_target
        hangup = await refs.resolve_target(ctx, {"kind": "external", "number": "0991234567"}, source_ref="r")
        assert await refs.resolve_target(ctx, {"kind": "hangup"}, source_ref="r") == hangup
        busy = await refs.resolve_target(ctx, {"kind": "busy"}, source_ref="r")
        assert busy not in (None, hangup)
        assert await refs.resolve_target(ctx, {"kind": "weird"}, source_ref="r") == hangup
        assert await refs.resolve_target(ctx, {"$ref": "ivr:ivr_details:99"}, source_ref="r") == hangup
        assert await refs.fallback_audio(ctx, "r")
        assert [w["code"] for w in ctx.warnings] == [
            "external_dest_unsupported", "dest_unsupported", "ref_unresolved", "audio_fallback"]
        await s.rollback()


async def test_fallback_audio_missing(factory, tenant_id, extracted, sounds) -> None:
    async with factory() as s:
        ctx = WriteCtx(session=s, tenant_id=tenant_id, tenant_code="x", job_id="j", bundle_dir=extracted,
                       sounds_dir=sounds)
        with pytest.raises(WriteError, match="audio"):
            await refs.fallback_audio(ctx, "r")
