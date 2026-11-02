"""`app/services/backup_job.py` — DBsiz/tarmoqsiz qismlar TO'LIQ; DB/tarmoqli qismlar
(`_upload_one`/`_apply_retention`/`create_backup_record`) `AsyncMock` soxta sessiya bilan
(filial mantiq: muvaffaqiyat/xato/retention) — haqiqiy Postgres `pg_dump`/tarmoq sinovlari
`run_backup_job`/`dump_database` uchun shu faylda YO'Q (bu loyihada kerak bo'lsa `live` orqali)."""
from __future__ import annotations

import json
import tarfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.models import Backup, BackupCopy
from app.services import backup_job as bj
from app.services import backup_parts
from app.services.backup_container import FrameReader
from app.services.backup_dbkey import decrypt_db_key
from app.services.backup_format import ArchiveReader
from app.services.backup_manifest import Manifest
from app.services.backup_targets import BackupTargetError


def test_new_backup_file_name():
    now = datetime(2026, 10, 29, 12, 34, 56, tzinfo=timezone.utc)
    assert bj.new_backup_file_name("pbx1", now, "abcd1234") == "innova-pbx1-20261029-123456-abcd1234.ibk"


def test_sha256_file_matches_hashlib(tmp_path):
    import hashlib
    path = tmp_path / "x.bin"
    path.write_bytes(b"hello world")
    assert bj.sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_stage_file_component_tars_existing_dir(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hi")
    dest = tmp_path / "out.tar"
    bj.stage_file_component(src, dest)
    with tarfile.open(dest) as tar:
        assert "./a.txt" in tar.getnames()


def test_stage_file_component_missing_dir_writes_empty_tar(tmp_path):
    dest = tmp_path / "out.tar"
    bj.stage_file_component(tmp_path / "missing", dest)
    with tarfile.open(dest) as tar:
        assert tar.getnames() == []


def test_stage_file_component_dereferences_absolute_symlink(tmp_path):
    """Bug: `moh.py`/`voicemail.py` MOH/salomlashuv havolalarini ABSOLYUT yo'l
    bilan yaratadi (`link.symlink_to(target)`). Havola SIFATIDA saqlansa, Python
    3.12 `tarfile` xavfsiz `data` filtri tiklashda `AbsoluteLinkError` bilan rad
    etadi (PEP 706) — tiklash ishi HAR DOIM `restage_files`da muvaffaqiyatsiz
    bo'lardi. `dereference=True` -- havola emas, fayl MAZMUNI saqlanadi."""
    src = tmp_path / "src"
    src.mkdir()
    real = tmp_path / "outside-real.wav"
    real.write_bytes(b"audio-bytes")
    (src / "link.wav").symlink_to(real)
    dest = tmp_path / "out.tar"
    bj.stage_file_component(src, dest)
    with tarfile.open(dest) as tar:
        member = tar.getmember("./link.wav")
        assert not member.issym(), "havola EMAS, fayl mazmuni saqlanishi kerak"
        assert tar.extractfile(member).read() == b"audio-bytes"
        # xavfsiz "data" filtri bilan tiklash endi muvaffaqiyatli bo'lishi kerak
        out = tmp_path / "restored"
        out.mkdir()
        tar.extractall(out, filter="data")
    assert (out / "link.wav").read_bytes() == b"audio-bytes"


def test_stage_file_component_skips_dangling_symlink_keeps_rest(tmp_path, caplog):
    """Bug (m4b isbot): MOH audio fayli o'chirilgach sinf papkasida havola qoladi --
    `dereference=True` `FileNotFoundError` berib BUTUN zaxirani (shu jumladan pre_restore)
    `failed` qilardi. Endi faqat o'sha havola tashlanadi, qolgan hammasi saqlanadi."""
    src = tmp_path / "src"
    (src / "moh" / "cls").mkdir(parents=True)
    (src / "moh" / "cls" / "gone.wav").symlink_to(tmp_path / "deleted.wav")
    (src / "moh" / "cls" / "b.wav").write_bytes(b"b")
    (src / "a.wav").write_bytes(b"a")
    dest = tmp_path / "out.tar"
    with caplog.at_level("WARNING", logger="innova.backup_job"):
        bj.stage_file_component(src, dest)
    with tarfile.open(dest) as tar:
        assert tar.getnames() == [".", "./moh", "./a.wav", "./moh/cls", "./moh/cls/b.wav"]
        assert tar.extractfile("./moh/cls/b.wav").read() == b"b"
    assert "gone.wav" in caplog.text


def test_stage_file_component_follows_symlinked_dir(tmp_path):
    outside = tmp_path / "spool"
    outside.mkdir()
    (outside / "msg.wav").write_bytes(b"m")
    src = tmp_path / "src"
    src.mkdir()
    (src / "box").symlink_to(outside)
    dest = tmp_path / "out.tar"
    bj.stage_file_component(src, dest)
    with tarfile.open(dest) as tar:
        assert tar.getmember("./box").isdir()
        assert tar.extractfile("./box/msg.wav").read() == b"m"


def test_stage_all_parts_only_selected_and_existing_components(tmp_path, monkeypatch):
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    (sounds / "a.wav").write_bytes(b"x")
    monkeypatch.setitem(backup_parts.FILE_COMPONENTS, "sounds", str(sounds))
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    parts = bj.stage_all_parts(stage_dir, ["config", "sounds"])
    assert [name for name, _ in parts] == ["sounds.tar"]


def test_write_archive_round_trip(tmp_path):
    part_a = tmp_path / "a.bin"
    part_a.write_bytes(b"part-a-bytes")
    part_b = tmp_path / "b.bin"
    part_b.write_bytes(b"")
    ibk = tmp_path / "out.ibk"

    manifest, _archive_sha = bj.write_archive(
        ibk, "s3cret-passphrase", "the-db-key", alembic_revision="rev1",
        components=["config", "sounds"], parts=[("a.bin", part_a), ("b.bin", part_b)],
        source_host="test-host",
    )

    assert manifest.alembic_revision == "rev1"
    assert manifest.source_host == "test-host"
    assert [p.name for p in manifest.parts] == ["a.bin", "b.bin"]

    with ibk.open("rb") as fh:
        reader = ArchiveReader(fh, "s3cret-passphrase")
        frames = FrameReader(reader.read_chunks())

        name, size = frames.read_header()
        assert name == "manifest.json"
        assert Manifest.from_dict(json.loads(frames.read_exact(size))) == manifest

        name, size = frames.read_header()
        assert (name, frames.read_exact(size)) == ("a.bin", b"part-a-bytes")

        name, size = frames.read_header()
        assert (name, frames.read_exact(size)) == ("b.bin", b"")

        name, size = frames.read_header()
        assert name == "db_key.enc"
        assert decrypt_db_key("s3cret-passphrase", frames.read_exact(size)) == "the-db-key"

        assert frames.read_header() is None


def test_own_local_items_filters_pattern(tmp_path):
    (tmp_path / "innova-host-20260101-000000-aaaa1111.ibk").write_bytes(b"")
    (tmp_path / "not-mine.ibk").write_bytes(b"")
    items = bj._own_local_items(tmp_path)
    assert [item.id for item in items] == ["innova-host-20260101-000000-aaaa1111.ibk"]


@pytest.mark.asyncio
async def test_create_backup_record_requires_passphrase():
    session = AsyncMock()
    settings_row = AsyncMock()
    settings_row.backup = {"passphrase_enc": None}
    session.get.return_value = settings_row
    with pytest.raises(bj.PassphraseRequiredError):
        await bj.create_backup_record(session, tenant_id="t1", kind="manual",
                                       components=["config"], created_by=None)


@pytest.mark.asyncio
async def test_create_backup_record_creates_running_backup():
    session = AsyncMock()
    settings_row = AsyncMock()
    settings_row.backup = {"passphrase_enc": "enc"}
    session.get.return_value = settings_row
    backup = await bj.create_backup_record(session, tenant_id="t1", kind="manual",
                                            components=["config", "sounds"], created_by="u1")
    assert backup.status == "running"
    assert backup.components == ["config", "sounds"]
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_backup_record_rejects_missing_config():
    session = AsyncMock()
    settings_row = AsyncMock()
    settings_row.backup = {"passphrase_enc": "enc"}
    session.get.return_value = settings_row
    with pytest.raises(ValueError):
        await bj.create_backup_record(session, tenant_id="t1", kind="manual",
                                       components=["sounds"], created_by=None)


@pytest.mark.asyncio
async def test_upload_one_success_runs_retention(tmp_path):
    local = tmp_path / "x.ibk"
    local.write_bytes(b"1234")
    backup = Backup(id="b1", tenant_id="t1", kind="manual", status="running",
                     components=["config"], file_name="innova-h-20260101-000000-aaaa1111.ibk")
    session = AsyncMock()
    session.execute.return_value = AsyncMock(scalar_one_or_none=lambda: None)
    upload = AsyncMock(return_value="remote/key.ibk")
    deleted: list[str] = []

    async def delete_one(remote_id: str) -> None:
        deleted.append(remote_id)

    old_item = bj.RetentionItem(id="old-remote.ibk", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    new_item = bj.RetentionItem(id="remote/key.ibk", created_at=datetime.now(timezone.utc))
    list_own = AsyncMock(return_value=[old_item, new_item])

    ok = await bj._upload_one(session, backup, "s3", local, upload, 1, list_own, delete_one)

    assert ok is True
    assert deleted == ["old-remote.ibk"]
    upload.assert_awaited_once_with(local, backup.file_name)


@pytest.mark.asyncio
async def test_upload_one_failure_sets_copy_failed_no_retention(tmp_path):
    local = tmp_path / "x.ibk"
    local.write_bytes(b"1234")
    backup = Backup(id="b1", tenant_id="t1", kind="manual", status="running",
                     components=["config"], file_name="innova-h.ibk")
    session = AsyncMock()
    upload = AsyncMock(side_effect=BackupTargetError("boom"))
    list_own = AsyncMock()
    delete_one = AsyncMock()

    ok = await bj._upload_one(session, backup, "sftp", local, upload, 7, list_own, delete_one)

    assert ok is False
    list_own.assert_not_called()
    delete_one.assert_not_called()
    added_copy = session.add.call_args.args[0]
    assert added_copy.status == "failed"
    assert added_copy.error == "boom"


@pytest.mark.asyncio
async def test_apply_retention_marks_matching_copy_deleted():
    session = AsyncMock()
    matching_copy = BackupCopy(id="c1", backup_id="b1", target="local", status="ok", remote_path="old.ibk")
    session.execute.return_value = AsyncMock(scalar_one_or_none=lambda: matching_copy)
    deleted: list[str] = []

    async def delete_one(remote_id: str) -> None:
        deleted.append(remote_id)

    items = [
        bj.RetentionItem(id="old.ibk", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
        bj.RetentionItem(id="new.ibk", created_at=datetime.now(timezone.utc)),
    ]
    await bj._apply_retention(session, "local", items, 1, delete_one)

    assert deleted == ["old.ibk"]
    assert matching_copy.status == "deleted"


@pytest.mark.asyncio
async def test_apply_retention_skips_delete_error_without_raising():
    session = AsyncMock()

    async def delete_one(remote_id: str) -> None:
        raise BackupTargetError("network")

    items = [bj.RetentionItem(id="old.ibk", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
             bj.RetentionItem(id="new.ibk", created_at=datetime.now(timezone.utc))]
    await bj._apply_retention(session, "local", items, 1, delete_one)
    session.execute.assert_not_called()


@pytest.mark.parametrize("kind, expected", [
    ("manual", True), ("scheduled", True), ("uploaded", True), ("pre_restore", False),
])
def test_uploads_to_remotes_skips_only_pre_restore(kind, expected):
    assert bj.uploads_to_remotes(kind) is expected


# ---------------------------------------------------------------- _upload_to_remote_targets
def _remote_cfg(s3: bool, sftp: bool) -> dict:
    return {"targets": {"s3": {"enabled": s3}, "sftp": {"enabled": sftp}}}


def _patch_remote_targets(monkeypatch, results: dict[str, bool]):
    """`_upload_one` soxtasi: nishon nomi -> natija; har chaqiriqda yuklash/ro'yxat/o'chirish
    lambda'larini ham chaqirib, ular TO'G'RI nishonga bog'langanini yozib oladi."""
    calls: list[tuple] = []
    s3_target, sftp_target = object(), object()

    async def s3_from(_s, _cfg):
        return SimpleNamespace(keep_last=3, t=s3_target)

    async def sftp_from(_s, _cfg):
        return SimpleNamespace(keep_last=5, t=sftp_target)

    def fake_target_fn(op):
        async def fn(target, *args):
            calls.append((op, target.t, args))
        return fn

    for op in ("upload_s3", "list_own_s3", "delete_s3", "upload_sftp", "list_own_sftp", "delete_sftp"):
        monkeypatch.setattr(bj, op, fake_target_fn(op))
    monkeypatch.setattr(bj, "s3_target_from_settings", s3_from)
    monkeypatch.setattr(bj, "sftp_target_from_settings", sftp_from)

    async def fake_upload_one(_session, _backup, name, path, upload, keep_last, list_own, delete_one):
        await upload(path, "f.ibk")
        await list_own()
        await delete_one("old.ibk")
        calls.append(("keep_last", name, keep_last))
        return results[name]

    monkeypatch.setattr(bj, "_upload_one", fake_upload_one)
    return calls, s3_target, sftp_target


@pytest.mark.asyncio
@pytest.mark.parametrize("s3, sftp, results, expected", [
    (False, False, {}, False),
    (True, False, {"s3": True}, False),
    (True, False, {"s3": False}, True),
    (False, True, {"sftp": False}, True),
    (True, True, {"s3": True, "sftp": True}, False),
    (True, True, {"s3": False, "sftp": True}, True),
    (True, True, {"s3": True, "sftp": False}, True),
])
async def test_upload_to_remote_targets_any_failed(monkeypatch, tmp_path, s3, sftp, results, expected):
    calls, _, _ = _patch_remote_targets(monkeypatch, results)
    got = await bj._upload_to_remote_targets(AsyncMock(), object(), _remote_cfg(s3, sftp), tmp_path / "x.ibk")
    assert got is expected
    assert [c[1] for c in calls if c[0] == "keep_last"] == [n for n, on in (("s3", s3), ("sftp", sftp)) if on]


@pytest.mark.asyncio
async def test_upload_to_remote_targets_binds_each_target(monkeypatch, tmp_path):
    calls, s3_t, sftp_t = _patch_remote_targets(monkeypatch, {"s3": True, "sftp": True})
    path = tmp_path / "x.ibk"
    await bj._upload_to_remote_targets(AsyncMock(), object(), _remote_cfg(True, True), path)
    assert calls == [
        ("upload_s3", s3_t, (path, "f.ibk")), ("list_own_s3", s3_t, ()), ("delete_s3", s3_t, ("old.ibk",)),
        ("keep_last", "s3", 3),
        ("upload_sftp", sftp_t, (path, "f.ibk")), ("list_own_sftp", sftp_t, ()),
        ("delete_sftp", sftp_t, ("old.ibk",)), ("keep_last", "sftp", 5),
    ]


# ---------------------------------------------------------------- _run_backup_job
class _RunSession:
    def __init__(self, backup: Backup, backup_cfg: dict):
        self._rows = {Backup: backup, bj.SystemSettings: SimpleNamespace(backup=backup_cfg)}
        self.added: list = []
        self.commits = 0
        self.flushes = 0

    async def get(self, model, _key):
        return self._rows[model]

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def _patch_run(monkeypatch, tmp_path, *, dump_error: Exception | None = None, remote_failed: bool = False):
    events: list[tuple] = []
    monkeypatch.setattr(bj.settings, "backups_dir", str(tmp_path / "bk"))
    monkeypatch.setattr(type(bj.settings), "require_db_key", lambda _self: "db-key")

    async def fake_decrypt(_s, enc):
        return f"pass-of-{enc}"

    def fake_dump(dest, components):
        if dump_error is not None:
            raise dump_error
        dest.write_bytes(b"dump")

    async def fake_rev(_s):
        return "rev9"

    def fake_write(ibk, passphrase, db_key, *, alembic_revision, components, parts):
        ibk.write_bytes(b"12345")
        events.append(("write", passphrase, db_key, alembic_revision, components, [n for n, _ in parts]))
        return SimpleNamespace(to_dict=lambda: {"m": 1}), "sha-x"

    async def fake_retention(_s, target, items, keep_last, delete_one):
        events.append(("retention", target, keep_last))

    async def fake_remote(_s, backup, cfg, ibk_path):
        events.append(("remote", ibk_path.name == backup.file_name))
        return remote_failed

    async def fake_alert(_s, tenant_id, detail):
        events.append(("alert", tenant_id, detail))

    monkeypatch.setattr(bj, "decrypt_secret", fake_decrypt)
    monkeypatch.setattr(bj, "dump_database", fake_dump)
    monkeypatch.setattr(bj, "stage_all_parts", lambda _d, _c: [("sounds.tar", tmp_path / "s.tar")])
    monkeypatch.setattr(bj, "current_alembic_revision", fake_rev)
    monkeypatch.setattr(bj, "write_archive", fake_write)
    monkeypatch.setattr(bj, "_apply_retention", fake_retention)
    monkeypatch.setattr(bj, "_upload_to_remote_targets", fake_remote)
    monkeypatch.setattr(bj, "_alert_backup_failed", fake_alert)
    return events


def _run_fixture(kind: str = "manual"):
    backup = Backup(id="b1", tenant_id="t1", kind=kind, status="running", components=["config", "sounds"])
    cfg = {"passphrase_enc": "enc1", "targets": {"local": {"keep_last": 4}}}
    return backup, _RunSession(backup, cfg)


@pytest.mark.asyncio
async def test_run_backup_job_success_sets_ok_and_local_copy(monkeypatch, tmp_path):
    events = _patch_run(monkeypatch, tmp_path)
    backup, session = _run_fixture()
    await bj._run_backup_job(session, "b1", "t1")

    assert backup.status == "ok" and backup.finished_at is not None
    assert backup.sha256 == "sha-x" and backup.size_bytes == 5 and backup.manifest == {"m": 1}
    assert (tmp_path / "bk" / backup.file_name).exists()
    assert events == [
        ("write", "pass-of-enc1", "db-key", "rev9", ["config", "sounds"], ["database.dump", "sounds.tar"]),
        ("retention", "local", 4), ("remote", True),
    ]
    (local_copy,) = session.added
    assert (local_copy.target, local_copy.status, local_copy.remote_path, local_copy.size_bytes) == (
        "local", "ok", backup.file_name, 5)
    assert session.flushes == 1 and session.commits == 1


@pytest.mark.asyncio
async def test_run_backup_job_remote_failure_is_partial_with_alert(monkeypatch, tmp_path):
    events = _patch_run(monkeypatch, tmp_path, remote_failed=True)
    backup, session = _run_fixture()
    await bj._run_backup_job(session, "b1", "t1")
    assert backup.status == "partial"
    assert events[-1] == ("alert", "t1", "masofaviy nishonga yuklashda xato (partial)")


@pytest.mark.asyncio
async def test_run_backup_job_pre_restore_stays_local(monkeypatch, tmp_path):
    events = _patch_run(monkeypatch, tmp_path, remote_failed=True)
    backup, session = _run_fixture(kind="pre_restore")
    await bj._run_backup_job(session, "b1", "t1")
    assert backup.status == "ok"
    assert [e[0] for e in events] == ["write", "retention"]


@pytest.mark.asyncio
async def test_run_backup_job_local_failure_marks_failed_and_alerts(monkeypatch, tmp_path):
    events = _patch_run(monkeypatch, tmp_path, dump_error=RuntimeError("pg_dump boom " + "x" * 600))
    backup, session = _run_fixture()
    await bj._run_backup_job(session, "b1", "t1")

    assert backup.status == "failed" and backup.finished_at is not None
    assert backup.error.startswith("pg_dump boom") and len(backup.error) == 500
    assert backup.file_name is None and session.added == []
    assert list((tmp_path / "bk").glob("*.ibk")) == []
    assert events == [("alert", "t1", backup.error)]
    assert session.commits == 1
