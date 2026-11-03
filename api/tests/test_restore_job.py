"""`app/services/restore_job.py` — arxiv o'qish/tekshirish haqiqiy `.ibk` fayllar bilan
(`backup_job.write_archive()` orqali quriladi, `test_backup_job.py`dagi usul); DB/tarmoq/
subprocess qadamlari (`_pg_restore`/`_alembic_upgrade_head`/`regenerate_all`/...) soxta
funksiyalar bilan — haqiqiy Postgres/Asterisk sinovlari bu loyihada `live` orqali (bu
faylda YO'Q)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import backup_job as bj
from app.services import restore_job as mod
from app.services.backup_format import BackupCorruptError, BadPassphraseError
from app.services.backup_manifest import db_key_fingerprint
from app.services.job_lock import JobAlreadyRunningError


def _build_archive(tmp_path, *, passphrase="s3cret", db_key="the-db-key", components=("config",)):
    part_a = tmp_path / "database.dump"
    part_a.write_bytes(b"dump-bytes")
    ibk = tmp_path / "out.ibk"
    manifest, _sha = bj.write_archive(
        ibk, passphrase, db_key, alembic_revision="rev1", components=list(components),
        parts=[("database.dump", part_a)], source_host="test-host",
    )
    return ibk, manifest


# ---------------------------------------------------------------- walk_archive / extract_archive
def test_walk_archive_round_trip_verifies_parts(tmp_path):
    ibk, manifest = _build_archive(tmp_path)
    result = mod.walk_archive(ibk, "s3cret")
    assert result == manifest


def test_walk_archive_wrong_passphrase_raises_bad_passphrase(tmp_path):
    ibk, _manifest = _build_archive(tmp_path)
    with pytest.raises(BadPassphraseError):
        mod.walk_archive(ibk, "wrong-pass")


def test_walk_archive_detects_tampered_body(tmp_path):
    ibk, _manifest = _build_archive(tmp_path)
    data = bytearray(ibk.read_bytes())
    data[-5] ^= 0xFF  # oxirgi blok ichidagi shifr matnni buzadi (AAD/tag mos kelmaydi)
    ibk.write_bytes(bytes(data))
    with pytest.raises(BackupCorruptError):
        mod.walk_archive(ibk, "s3cret")


def test_walk_archive_detects_truncated_file(tmp_path):
    ibk, _manifest = _build_archive(tmp_path)
    data = ibk.read_bytes()
    ibk.write_bytes(data[:-5])  # oxirgi blok to'liq kelmaydi
    with pytest.raises(BackupCorruptError):
        mod.walk_archive(ibk, "s3cret")


@pytest.mark.parametrize("evil_name", ["../evil.sh", "../../etc/passwd", "sounds.tar/../../evil"])
def test_extract_archive_rejects_path_traversal_part_name(tmp_path, evil_name):
    """Arxiv ichidagi qism nomi hujumchi nazorat qiladigan satr -- manifest hali
    tasdiqlanmasdan turib `stage_dir` tashqarisiga yozilmasligi SHART."""
    staged = tmp_path / "staged-src"
    staged.mkdir()
    part_a = staged / "database.dump"
    part_a.write_bytes(b"dump-bytes")
    evil_part = staged / "evil-payload"
    evil_part.write_bytes(b"pwned")
    ibk = tmp_path / "out.ibk"
    bj.write_archive(
        ibk, "s3cret", "the-db-key", alembic_revision="rev1", components=["config"],
        parts=[("database.dump", part_a), (evil_name, evil_part)], source_host="test-host",
    )
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    with pytest.raises(BackupCorruptError):
        mod.extract_archive(ibk, "s3cret", stage_dir)
    # Hech narsa `stage_dir` tashqarisiga yoki ildiziga yozilmagan bo'lishi kerak.
    assert not (tmp_path / "evil.sh").exists()
    assert list(stage_dir.iterdir()) == [] or all(
        p.resolve().is_relative_to(stage_dir.resolve()) for p in stage_dir.rglob("*")
    )


def test_walk_archive_rejects_unknown_part_name(tmp_path):
    staged = tmp_path / "staged-src"
    staged.mkdir()
    part_a = staged / "database.dump"
    part_a.write_bytes(b"dump-bytes")
    bogus = staged / "bogus"
    bogus.write_bytes(b"data")
    ibk = tmp_path / "out.ibk"
    bj.write_archive(
        ibk, "s3cret", "the-db-key", alembic_revision="rev1", components=["config"],
        parts=[("database.dump", part_a), ("bogus-part-name", bogus)], source_host="test-host",
    )
    with pytest.raises(BackupCorruptError):
        mod.walk_archive(ibk, "s3cret")


def test_extract_archive_writes_files_and_returns_db_key_blob(tmp_path):
    ibk, manifest = _build_archive(tmp_path, db_key="original-key")
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    got_manifest, db_key_blob = mod.extract_archive(ibk, "s3cret", stage_dir)
    assert got_manifest == manifest
    assert (stage_dir / "database.dump").read_bytes() == b"dump-bytes"
    from app.services.backup_dbkey import decrypt_db_key
    assert decrypt_db_key("s3cret", db_key_blob) == "original-key"


# ---------------------------------------------------------------- inspect
@pytest.mark.asyncio
async def test_inspect_compatible_no_warning_when_key_matches(tmp_path, monkeypatch):
    ibk, _manifest = _build_archive(tmp_path, db_key="server-key")
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev1"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: False)
    monkeypatch.setattr(mod, "settings", SimpleNamespace(require_db_key=lambda: "server-key"))

    result = await mod.inspect(session=None, path=ibk, passphrase="s3cret")
    assert result["checks"] == {"sha256": "ok"}
    assert result["compatible"] is True
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_inspect_warns_on_db_key_mismatch_and_incompatible_when_newer(tmp_path, monkeypatch):
    ibk, _manifest = _build_archive(tmp_path, db_key="archive-key")
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev0"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: True)
    monkeypatch.setattr(mod, "settings", SimpleNamespace(require_db_key=lambda: "different-server-key"))

    result = await mod.inspect(session=None, path=ibk, passphrase="s3cret")
    assert result["compatible"] is False
    assert len(result["warnings"]) == 1


# ---------------------------------------------------------------- precheck_and_create_job
class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_precheck_rejects_newer_revision(tmp_path, monkeypatch):
    ibk, manifest = _build_archive(tmp_path)
    monkeypatch.setattr(mod, "walk_archive", lambda *_a: manifest)
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev0"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: True)

    with pytest.raises(mod.RestoreNewerError):
        await mod.precheck_and_create_job(
            _FakeSession(), None, backup_id="b1", source="local", archive_path=ibk, passphrase="s3cret",
            force=False, tenant_id="t1", user_id="u1", ami=None,
        )


@pytest.mark.asyncio
async def test_precheck_blocks_on_active_calls_unless_forced(tmp_path, monkeypatch):
    ibk, manifest = _build_archive(tmp_path)
    monkeypatch.setattr(mod, "walk_archive", lambda *_a: manifest)
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev1"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: False)
    monkeypatch.setattr(mod, "active_calls_live", AsyncMock(return_value=[{"channel": "x"}]))

    with pytest.raises(mod.ActiveCallsError) as excinfo:
        await mod.precheck_and_create_job(
            _FakeSession(), None, backup_id="b1", source="local", archive_path=ibk, passphrase="s3cret",
            force=False, tenant_id="t1", user_id="u1", ami=None,
        )
    assert excinfo.value.count == 1


@pytest.mark.asyncio
async def test_precheck_treats_unknown_ami_as_active_calls(tmp_path, monkeypatch):
    ibk, manifest = _build_archive(tmp_path)
    monkeypatch.setattr(mod, "walk_archive", lambda *_a: manifest)
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev1"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: False)
    monkeypatch.setattr(mod, "active_calls_live", AsyncMock(return_value=None))

    with pytest.raises(mod.ActiveCallsError) as excinfo:
        await mod.precheck_and_create_job(
            _FakeSession(), None, backup_id="b1", source="local", archive_path=ibk, passphrase="s3cret",
            force=False, tenant_id="t1", user_id="u1", ami=None,
        )
    assert excinfo.value.count is None


@pytest.mark.asyncio
async def test_precheck_force_skips_active_calls_check(tmp_path, monkeypatch):
    ibk, manifest = _build_archive(tmp_path)
    monkeypatch.setattr(mod, "walk_archive", lambda *_a: manifest)
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev1"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: False)
    called = []
    monkeypatch.setattr(mod, "active_calls_live", AsyncMock(side_effect=lambda *_a: called.append(1)))
    lock = SimpleNamespace()
    monkeypatch.setattr(mod, "try_acquire_job_lock", AsyncMock(return_value=lock))

    session = _FakeSession()
    job, got_lock = await mod.precheck_and_create_job(
        session, None, backup_id="b1", source="local", archive_path=ibk, passphrase="s3cret",
        force=True, tenant_id="t1", user_id="u1", ami=None,
    )
    assert called == []
    assert got_lock is lock
    assert session.added == [job]
    assert job.step == "pre_restore_backup"
    assert job.force is True
    assert job.source == "local"


@pytest.mark.asyncio
async def test_precheck_propagates_job_already_running(tmp_path, monkeypatch):
    ibk, manifest = _build_archive(tmp_path)
    monkeypatch.setattr(mod, "walk_archive", lambda *_a: manifest)
    monkeypatch.setattr(mod, "current_alembic_revision", AsyncMock(return_value="rev1"))
    monkeypatch.setattr(mod, "load_script_directory", lambda: None)
    monkeypatch.setattr(mod, "is_revision_newer", lambda *_a: False)

    async def fake_acquire(_engine):
        raise JobAlreadyRunningError()

    monkeypatch.setattr(mod, "try_acquire_job_lock", fake_acquire)

    with pytest.raises(JobAlreadyRunningError):
        await mod.precheck_and_create_job(
            _FakeSession(), None, backup_id="b1", source="local", archive_path=ibk, passphrase="s3cret",
            force=True, tenant_id="t1", user_id="u1", ami=None,
        )


# ---------------------------------------------------------------- _create_pre_restore_backup
@pytest.mark.asyncio
async def test_create_pre_restore_backup_returns_none_without_passphrase(monkeypatch):
    async def fake_create(*_a, **_kw):
        raise bj.PassphraseRequiredError("yo'q")

    monkeypatch.setattr(mod.backup_job, "create_backup_record", fake_create)
    result = await mod._create_pre_restore_backup(AsyncMock(), "t1")
    assert result is None


@pytest.mark.asyncio
async def test_create_pre_restore_backup_runs_private_job_directly(monkeypatch):
    backup = SimpleNamespace(id="pb1", status="ok", error=None)

    async def fake_create(*_a, **_kw):
        return backup

    ran = []

    async def fake_run(_session, backup_id, tenant_id):
        ran.append((backup_id, tenant_id))

    monkeypatch.setattr(mod.backup_job, "create_backup_record", fake_create)
    monkeypatch.setattr(mod.backup_job, "_run_backup_job", fake_run)
    session = AsyncMock()

    result = await mod._create_pre_restore_backup(session, "t1")
    assert result is backup
    assert ran == [("pb1", "t1")]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_pre_restore_backup_failed_aborts_restore(monkeypatch):
    """Bug (m4b isbot): pre_restore zaxira `failed` bo'lsa ham tiklash davom etardi --
    bekor qilish nuqtasi yo'q edi (`POST /backups/{pre}/restore` -> 409 no_local_copy)."""
    backup = SimpleNamespace(id="pb1", status="running", error=None)

    async def fake_create(*_a, **_kw):
        return backup

    async def fake_run(_session, _backup_id, _tenant_id):
        backup.status, backup.error = "failed", "disk to'la"

    monkeypatch.setattr(mod.backup_job, "create_backup_record", fake_create)
    monkeypatch.setattr(mod.backup_job, "_run_backup_job", fake_run)
    with pytest.raises(mod.PreRestoreBackupError, match="pre_restore zaxira muvaffaqiyatsiz: disk to'la"):
        await mod._create_pre_restore_backup(AsyncMock(), "t1")


# ---------------------------------------------------------------- _restage_file_components
def test_restage_file_components_preserves_mount_root_clears_contents(tmp_path, monkeypatch):
    """Bug: eski kod `shutil.rmtree(target)` bilan NISHON PAPKANING O'ZINI o'chirar edi.
    `backup_parts.FILE_COMPONENTS` nishonlari (`/var/lib/innova/sounds` va h.k.)
    `deploy/docker-compose.yml`da ulangan Docker HAJM (volume) ILDIZI -- ildizning
    o'zini o'chirish HAQIQIY muhitda HAR DOIM `OSError: [Errno 16] Device or resource
    busy` bilan rad etiladi (mount nuqtasi o'chirilmaydi), shu sabab tiklash ishi
    shu bosqichda HAR DOIM muvaffaqiyatsiz bo'lardi. Tuzatish: ildiz SAQLANADI
    (inode o'zgarmaydi), FAQAT ichi tozalanadi."""
    import tarfile

    sounds_dir = tmp_path / "sounds-mount"
    sounds_dir.mkdir()
    (sounds_dir / "old.wav").write_bytes(b"old")
    old_subdir = sounds_dir / "oldsub"
    old_subdir.mkdir()
    (old_subdir / "nested.txt").write_text("x")
    inode_before = sounds_dir.stat().st_ino

    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    new_file_src = tmp_path / "new.wav"
    new_file_src.write_bytes(b"new-content")
    with tarfile.open(stage_dir / "sounds.tar", "w") as tar:
        tar.add(new_file_src, arcname="new.wav")

    monkeypatch.setattr(mod.backup_parts, "FILE_COMPONENTS", {"sounds": str(sounds_dir)})

    mod._restage_file_components(stage_dir)

    assert sounds_dir.stat().st_ino == inode_before, "nishon ILDIZI o'chirilib qayta yaratilmasligi kerak"
    assert not (sounds_dir / "old.wav").exists()
    assert not old_subdir.exists()
    assert (sounds_dir / "new.wav").read_bytes() == b"new-content"


# ---------------------------------------------------------------- _run_restore orchestration
class _JobSession:
    """`tenant` -- `_resolve_tenant()`ning oddiy (bir xil server) tez yo'lini
    simulyatsiya qiladi: `session.get(Tenant, tenant_id)` so'ralgan `tenant_id`
    bilan MOS keladigan qatorni topadi (DR holatini sinaydigan testlar buni
    `None` qilib, yagona-qator `execute(select(Tenant))` yo'lini sinaydi)."""

    def __init__(self, job, *, tenant_id="t1", tenant_code="pbx1"):
        self._job = job
        self._tenant_id = tenant_id
        self._tenant_code = tenant_code
        self.commits = 0

    async def get(self, model, pk):
        if model is mod.RestoreJob:
            return self._job
        if model is mod.Tenant and pk == self._tenant_id:
            return SimpleNamespace(id=self._tenant_id, code=self._tenant_code)
        return None

    async def execute(self, _stmt):
        tenant = SimpleNamespace(id=self._tenant_id, code=self._tenant_code)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: tenant))

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks = getattr(self, "rollbacks", 0) + 1


def _job():
    return SimpleNamespace(
        id="r1", backup_id="b1", pre_restore_backup_id=None, started_by="u1",
        status="running", step=None, progress=0, error=None, finished_at=None, result=None,
    )


def _patch_steps(monkeypatch, *, fail_at=None):
    manifest = SimpleNamespace(alembic_revision="rev1")

    async def pre_restore_backup(_session, _tenant_id):
        if fail_at == "pre_restore_backup":
            raise RuntimeError("boom-pre")
        return SimpleNamespace(id="pb1")

    def extract(*_a, **_kw):
        if fail_at == "extract":
            raise RuntimeError("boom-extract")
        return manifest, b"db-key-blob"

    def pg_restore(*_a, **_kw):
        if fail_at == "pg_restore":
            raise RuntimeError("boom-pg-restore")

    def alembic_upgrade():
        if fail_at == "alembic":
            raise RuntimeError("boom-alembic")

    async def rekey(*_a, **_kw):
        if fail_at == "rekey":
            raise RuntimeError("boom-rekey")

    def restage(*_a, **_kw):
        if fail_at == "restage":
            raise RuntimeError("boom-restage")

    async def regen(*_a, **_kw):
        if fail_at == "regen":
            raise RuntimeError("boom-regen")

    async def revoke(*_a, **_kw):
        pass

    async def audit(*_a, **_kw):
        pass

    monkeypatch.setattr(mod, "_create_pre_restore_backup", pre_restore_backup)
    monkeypatch.setattr(mod, "extract_archive", extract)
    monkeypatch.setattr(mod, "_pg_restore", pg_restore)
    monkeypatch.setattr(mod, "_alembic_upgrade_head", alembic_upgrade)
    monkeypatch.setattr(mod, "_maybe_rekey", rekey)
    monkeypatch.setattr(mod, "_restage_file_components", restage)
    monkeypatch.setattr(mod, "regenerate_all", regen)
    monkeypatch.setattr(mod, "revoke_all_refresh_tokens", revoke)
    monkeypatch.setattr(mod, "record_audit", audit)


@pytest.mark.asyncio
async def test_run_restore_success_marks_job_ok(tmp_path, monkeypatch):
    from app.services import maintenance
    _patch_steps(monkeypatch)
    job = _job()
    session = _JobSession(job)

    await mod._run_restore(session, tenant_id="t1", tenant_code="pbx1", ami=None,
                            restore_job_id="r1", archive_path=tmp_path / "x.ibk", passphrase="s3cret")

    assert job.status == "ok"
    assert job.progress == 100
    assert job.step == "done"
    assert job.pre_restore_backup_id == "pb1"
    assert job.result == {"alembic_revision": "rev1"}
    assert maintenance.state.enabled is False


@pytest.mark.asyncio
async def test_run_restore_disposes_engine_after_pg_restore_before_alembic(tmp_path, monkeypatch):
    """Bug: `pg_restore --clean` jadvallarni YANGI OID bilan qayta yaratadi, lekin
    ulashilgan SQLAlchemy `engine` pool'idagi BOSHQA (band qilinmagan) ulanishlar
    eski asyncpg tayyor-bayonot (prepared statement) keshini saqlab qoladi ->
    tiklashdan keyingi BIRINCHI so'rov shu ulanishga tushsa `InvalidCachedStatementError`
    bilan 500 qaytaradi (m4b-contract.md §4 band 4/5: tiklash SO'ROVI o'zi 500
    bermasligi kerak). Tuzatish: `_pg_restore()` muvaffaqiyatli bo'lgach, `_alembic_upgrade_head`dan
    OLDIN, `_db_engine.dispose()` chaqiriladi -- bo'sh ulanishlarni tashlab, keyingi
    tekshirishda yangi kesh bilan qayta ochadi (band qilingan ulanishga tegmaydi)."""
    order: list[str] = []
    _patch_steps(monkeypatch)

    def pg_restore(*_a, **_kw):
        order.append("pg_restore")

    def alembic_upgrade():
        order.append("alembic")

    monkeypatch.setattr(mod, "_pg_restore", pg_restore)
    monkeypatch.setattr(mod, "_alembic_upgrade_head", alembic_upgrade)
    disposed = AsyncMock(side_effect=lambda: order.append("dispose"))
    monkeypatch.setattr(mod, "_db_engine", SimpleNamespace(dispose=disposed))

    job = _job()
    session = _JobSession(job)

    await mod._run_restore(session, tenant_id="t1", tenant_code="pbx1", ami=None,
                            restore_job_id="r1", archive_path=tmp_path / "x.ibk", passphrase="s3cret")

    assert job.status == "ok"
    disposed.assert_awaited_once()
    assert order == ["pg_restore", "dispose", "alembic"]


@pytest.mark.asyncio
async def test_resolve_tenant_same_server_fast_path_skips_execute():
    """Oddiy (bir xil server) tiklashda `tenant_id` o'zgarmagan -- `session.get`
    tezkor yo'li yetarli, qo'shimcha `execute(select(Tenant))` so'ralmasligi kerak."""
    tenant = SimpleNamespace(id="t1", code="pbx1")

    class Session:
        async def get(self, _model, pk):
            return tenant if pk == "t1" else None

        async def execute(self, _stmt):
            raise AssertionError("oddiy holatda execute() chaqirilmasligi kerak")

    assert await mod._resolve_tenant(Session(), "t1") == ("t1", "pbx1")


@pytest.mark.asyncio
async def test_resolve_tenant_falls_back_to_sole_row_after_disaster_recovery():
    """Bug: falokatdan tiklashda (m4b-contract.md §4 band 5) BOSHQA serverda yangi
    (bo'sh) stack bootstrap qilinganda `tenant_id` TASODIFIY UUID oladi; `pg_restore`
    esa zaxiradagi ASL tenant qatorini (BOSHQA UUID) qo'yadi -- bootstrap tenant_id
    endi bazada YO'Q. Oldin bu holatda keyingi bosqich (`regenerate_all` ->
    `build_snapshot()`) "Tenant topilmadi" bilan ko'tarilib, tiklash ishi "regenerate"
    bosqichida HAR DOIM muvaffaqiyatsiz bo'lardi (falokatdan tiklash HAR DOIM shunday
    ishlaydi). Tuzatish: bootstrap id topilmasa, yagona (bitta-tenant) qatordan
    haqiqiy id/kod qayta olinadi."""
    restored_tenant = SimpleNamespace(id="orig-tenant-id", code="pbx1")

    class Session:
        async def get(self, _model, _pk):
            return None  # bootstrap tenant_id endi bazada yo'q

        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: restored_tenant))

    assert await mod._resolve_tenant(Session(), "fresh-bootstrap-id") == ("orig-tenant-id", "pbx1")


@pytest.mark.asyncio
async def test_resolve_tenant_raises_when_no_tenant_row_at_all():
    class Session:
        async def get(self, _model, _pk):
            return None

        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))

    with pytest.raises(ValueError):
        await mod._resolve_tenant(Session(), "missing")


@pytest.mark.asyncio
async def test_run_restore_passes_resolved_tenant_to_regenerate_after_disaster_recovery(tmp_path, monkeypatch):
    """`_run_restore` o'zi bootstrap `tenant_id`ni ko'r-ko'rona o'tkazmasligi, balki
    `_resolve_tenant()` natijasini keyingi bosqichlarga (`regenerate_all`) berishi
    kerak -- aks holda falokatdan tiklashda shu bosqich doim ko'tariladi."""
    _patch_steps(monkeypatch)
    received = {}

    async def regen(_session, *, tenant_id, tenant_code, ami):
        received["tenant_id"], received["tenant_code"] = tenant_id, tenant_code

    monkeypatch.setattr(mod, "regenerate_all", regen)

    job = _job()
    session = _JobSession(job, tenant_id="orig-tenant-id", tenant_code="pbx1")

    await mod._run_restore(session, tenant_id="fresh-bootstrap-id", tenant_code="fresh-code", ami=None,
                            restore_job_id="r1", archive_path=tmp_path / "x.ibk", passphrase="s3cret")

    assert received == {"tenant_id": "orig-tenant-id", "tenant_code": "pbx1"}
    assert job.status == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", ["pre_restore_backup", "extract", "pg_restore", "alembic", "rekey",
                                      "restage", "regen"])
async def test_run_restore_failure_marks_job_failed_and_disables_maintenance(tmp_path, monkeypatch, fail_at):
    from app.services import maintenance
    _patch_steps(monkeypatch, fail_at=fail_at)
    job = _job()
    session = _JobSession(job)

    await mod._run_restore(session, tenant_id="t1", tenant_code="pbx1", ami=None,
                            restore_job_id="r1", archive_path=tmp_path / "x.ibk", passphrase="s3cret")

    assert job.status == "failed"
    assert session.rollbacks == 1
    assert f"boom-{fail_at.replace('_', '-')}" in job.error or "boom" in job.error
    assert job.finished_at is not None
    assert maintenance.state.enabled is False


# ---------------------------------------------------------------- run_restore_job wrapper
class _FakeLock:
    def __init__(self):
        self.released = 0

    async def release(self):
        self.released += 1


class _FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_exc):
        return False


@pytest.mark.asyncio
async def test_run_restore_job_releases_lock_and_disables_maintenance(monkeypatch):
    from app.services import maintenance

    async def fake_run_restore(*_a, **_kw):
        maintenance.state.enabled = True  # _run_restore ichida yoqilgan holatni simulyatsiya qiladi

    monkeypatch.setattr(mod, "_run_restore", fake_run_restore)
    lock = _FakeLock()
    factory = _FakeSessionFactory(AsyncMock())

    await mod.run_restore_job(factory, None, lock, "r1", tenant_id="t1", tenant_code="pbx1",
                               ami=None, archive_path=None, passphrase="s3cret")

    assert lock.released == 1
    assert maintenance.state.enabled is False


# ---------------------------------------------------------------- audit muallifi (DR)
class _UserSession:
    def __init__(self, existing):
        self._existing = existing

    async def get(self, model, pk):
        return SimpleNamespace(id=pk) if model is mod.User and pk in self._existing else None


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id, existing, expected", [
    ("u1", {"u1"}, "u1"),     # shu server: muallif saqlanadi
    ("u-dr", {"u1"}, None),   # DR: vaqtinchalik admin tiklangan bazada yo'q
    (None, {"u1"}, None),
])
async def test_existing_user_id(user_id, existing, expected):
    assert await mod._existing_user_id(_UserSession(existing), user_id) == expected


@pytest.mark.parametrize(("kind", "expected"), [
    ("uploaded", "upload"), ("manual", "local"), ("scheduled", "local"), ("pre_restore", "local"),
])
def test_restore_source_is_upload_only_for_uploaded_backups(kind, expected):
    assert mod.restore_source(kind) == expected
