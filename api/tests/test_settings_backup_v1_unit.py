"""`app/api/v1/settings_backup.py` — M4b §2: `/settings/backup` GET/PUT,
`/settings/backup/passphrase`, `/settings/backup/targets/{target}/test`,
`/settings/backup/targets/sftp/trust`. DB/tarmoqsiz: soxta sessiya,
`get_settings_row`/`encrypt_secret`/`decrypt_secret`/`test_s3`/`test_sftp`
monkeypatch (alembic/sql/0021_m4b_backup.sql'dagi sukut qiymatlar bilan bir xil)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import settings_backup as sb
from app.core.errors import ApiError
from app.schemas_backup import (
    BackupLocalTargetIn,
    BackupS3TargetIn,
    BackupScheduleIn,
    BackupSftpTargetIn,
    BackupTargetsIn,
    TrustSftpHostKeyPayload,
    UpdateBackupPassphrasePayload,
    UpdateBackupSettingsPayload,
)

USER = SimpleNamespace(id="u1", tenant_id="t1")
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


def _cfg(**overrides):
    cfg = {
        "passphrase_enc": None,
        "schedule": {"enabled": False, "frequency": "daily", "weekday": 1, "time": "03:00",
                     "components": ["config", "history", "sounds", "voicemail", "certs"]},
        "targets": {
            "local": {"keep_last": 7},
            "s3": {"enabled": False, "endpoint": "", "region": "", "bucket": "", "prefix": "",
                   "access_key": "", "secret_key_enc": None, "path_style": False, "keep_last": 14},
            "sftp": {"enabled": False, "host": "", "port": 22, "user": "", "password_enc": None,
                     "key_enc": None, "folder": "/backups", "host_key_fp": None, "keep_last": 7},
        },
        "last_scheduled_at": None, "last_scheduled_ok_at": None, "last_stale_alert_at": None,
    }
    cfg.update(overrides)
    return cfg


def _row(**cfg_overrides):
    return SimpleNamespace(backup=_cfg(**cfg_overrides), updated_at=OLD)


class _Session:
    def __init__(self, row):
        self.row = row
        self.flushes = self.commits = self.refreshed = 0

    async def flush(self):
        self.flushes += 1

    async def refresh(self, _obj):
        self.refreshed += 1

    async def commit(self):
        self.commits += 1


@pytest.fixture
def env(monkeypatch):
    state: dict = {"audit": []}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(sb, "record_audit", fake_audit)
    return state


def _patch_row(monkeypatch, row):
    async def fake_get_settings_row(_session, _tenant_id):
        return row

    monkeypatch.setattr(sb, "get_settings_row", fake_get_settings_row)


# ------------------------------------------------------------------ GET
@pytest.mark.asyncio
async def test_get_backup_settings_maps_has_flags(monkeypatch):
    row = _row(passphrase_enc="enc-pass")
    row.backup["targets"]["s3"]["secret_key_enc"] = "enc-s3"
    row.backup["targets"]["sftp"]["password_enc"] = "enc-pw"
    _patch_row(monkeypatch, row)
    session = _Session(row)
    out = await sb.get_backup_settings(session=session, user=USER)
    assert out.has_passphrase is True
    assert out.targets.s3.has_secret_key is True
    assert out.targets.sftp.has_password is True
    assert out.targets.sftp.has_key is False


# ------------------------------------------------------------------ PUT
@pytest.mark.asyncio
async def test_update_backup_settings_stale_raises_409(monkeypatch, env):
    row = _row()
    row.updated_at = NOW
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sb.update_backup_settings(payload, session=session, user=USER)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_update_backup_settings_merges_schedule(monkeypatch, env):
    row = _row()
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        schedule=BackupScheduleIn(enabled=True, frequency="weekly", weekday=2, time="04:00",
                                   components=["config"]),
        updated_at=OLD,
    )
    out = await sb.update_backup_settings(payload, session=session, user=USER)
    assert out.schedule.enabled is True and out.schedule.frequency == "weekly"
    assert session.commits == 1 and session.refreshed == 1
    assert env["audit"][0]["diff"]["schedule"]["frequency"] == "weekly"


@pytest.mark.asyncio
async def test_update_backup_settings_s3_secret_key_encrypted_when_given(monkeypatch, env):
    row = _row()
    _patch_row(monkeypatch, row)

    async def fake_encrypt(_session, plaintext):
        return f"enc:{plaintext}"

    monkeypatch.setattr(sb, "encrypt_secret", fake_encrypt)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        targets=BackupTargetsIn(s3=BackupS3TargetIn(
            enabled=True, endpoint="s3.example.com", region="eu", bucket="b", prefix="p",
            access_key="AK", path_style=True, keep_last=10, secret_key="topsecret")),
        updated_at=OLD,
    )
    out = await sb.update_backup_settings(payload, session=session, user=USER)
    assert out.targets.s3.has_secret_key is True
    assert row.backup["targets"]["s3"]["secret_key_enc"] == "enc:topsecret"
    # audit diff'da ochiq sir yo'q
    assert "secret_key" not in env["audit"][0]["diff"]["targets.s3"]
    assert "secret_key_enc" not in env["audit"][0]["diff"]["targets.s3"]


@pytest.mark.asyncio
async def test_update_backup_settings_s3_keeps_old_secret_when_omitted(monkeypatch, env):
    row = _row()
    row.backup["targets"]["s3"]["secret_key_enc"] = "already-enc"
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        targets=BackupTargetsIn(s3=BackupS3TargetIn(
            enabled=True, endpoint="s3.example.com", region="eu", bucket="b", prefix="p",
            access_key="AK", path_style=True, keep_last=10)),
        updated_at=OLD,
    )
    await sb.update_backup_settings(payload, session=session, user=USER)
    assert row.backup["targets"]["s3"]["secret_key_enc"] == "already-enc"


@pytest.mark.asyncio
async def test_update_backup_settings_sftp_resets_host_key_fp_on_host_change(monkeypatch, env):
    row = _row()
    row.backup["targets"]["sftp"]["host"] = "old.example.com"
    row.backup["targets"]["sftp"]["host_key_fp"] = "SHA256:abc"
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        targets=BackupTargetsIn(sftp=BackupSftpTargetIn(
            enabled=True, host="new.example.com", port=22, user="u", folder="/b", keep_last=7)),
        updated_at=OLD,
    )
    out = await sb.update_backup_settings(payload, session=session, user=USER)
    assert out.targets.sftp.host_key_fp is None


@pytest.mark.asyncio
async def test_update_backup_settings_sftp_keeps_host_key_fp_when_host_unchanged(monkeypatch, env):
    row = _row()
    row.backup["targets"]["sftp"]["host"] = "same.example.com"
    row.backup["targets"]["sftp"]["host_key_fp"] = "SHA256:abc"
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        targets=BackupTargetsIn(sftp=BackupSftpTargetIn(
            enabled=True, host="same.example.com", port=22, user="u", folder="/b", keep_last=7)),
        updated_at=OLD,
    )
    out = await sb.update_backup_settings(payload, session=session, user=USER)
    assert out.targets.sftp.host_key_fp == "SHA256:abc"


@pytest.mark.asyncio
async def test_update_backup_settings_local_keep_last(monkeypatch, env):
    row = _row()
    _patch_row(monkeypatch, row)
    session = _Session(row)
    payload = UpdateBackupSettingsPayload(
        targets=BackupTargetsIn(local=BackupLocalTargetIn(keep_last=30)), updated_at=OLD)
    out = await sb.update_backup_settings(payload, session=session, user=USER)
    assert out.targets.local.keep_last == 30


# ------------------------------------------------------------------ passphrase
@pytest.mark.asyncio
async def test_update_passphrase_first_time_no_current_required(monkeypatch, env):
    row = _row(passphrase_enc=None)
    _patch_row(monkeypatch, row)

    async def fake_encrypt(_session, plaintext):
        return f"enc:{plaintext}"

    monkeypatch.setattr(sb, "encrypt_secret", fake_encrypt)
    session = _Session(row)
    out = await sb.update_backup_passphrase(
        UpdateBackupPassphrasePayload(passphrase="new-strong-pass"), session=session, user=USER)
    assert out == {"ok": True}
    assert row.backup["passphrase_enc"] == "enc:new-strong-pass"


@pytest.mark.asyncio
async def test_update_passphrase_requires_current_when_already_set(monkeypatch, env):
    row = _row(passphrase_enc="old-enc")
    _patch_row(monkeypatch, row)
    session = _Session(row)
    with pytest.raises(ApiError) as e:
        await sb.update_backup_passphrase(
            UpdateBackupPassphrasePayload(passphrase="new-strong-pass"), session=session, user=USER)
    assert (e.value.status_code, e.value.field) == (422, "current")


@pytest.mark.asyncio
async def test_update_passphrase_rejects_wrong_current(monkeypatch, env):
    row = _row(passphrase_enc="old-enc")
    _patch_row(monkeypatch, row)

    async def fake_decrypt(_session, _enc):
        return "correct-old-pass"

    monkeypatch.setattr(sb, "decrypt_secret", fake_decrypt)
    session = _Session(row)
    with pytest.raises(ApiError) as e:
        await sb.update_backup_passphrase(
            UpdateBackupPassphrasePayload(passphrase="new-strong-pass", current="wrong"),
            session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "bad_passphrase")


@pytest.mark.asyncio
async def test_update_passphrase_accepts_correct_current(monkeypatch, env):
    row = _row(passphrase_enc="old-enc")
    _patch_row(monkeypatch, row)

    async def fake_decrypt(_session, _enc):
        return "correct-old-pass"

    async def fake_encrypt(_session, plaintext):
        return f"enc:{plaintext}"

    monkeypatch.setattr(sb, "decrypt_secret", fake_decrypt)
    monkeypatch.setattr(sb, "encrypt_secret", fake_encrypt)
    session = _Session(row)
    out = await sb.update_backup_passphrase(
        UpdateBackupPassphrasePayload(passphrase="new-strong-pass", current="correct-old-pass"),
        session=session, user=USER)
    assert out == {"ok": True}
    assert row.backup["passphrase_enc"] == "enc:new-strong-pass"


# ------------------------------------------------------------------ targets test
@pytest.mark.asyncio
async def test_test_backup_target_s3_ok(monkeypatch):
    row = _row()
    _patch_row(monkeypatch, row)

    async def fake_s3_target(_session, _cfg):
        return "s3-target"

    async def fake_test_s3(target):
        assert target == "s3-target"
        return True, None

    monkeypatch.setattr(sb, "s3_target_from_settings", fake_s3_target)
    monkeypatch.setattr(sb, "test_s3", fake_test_s3)
    session = _Session(row)
    out = await sb.test_backup_target("s3", session=session, user=USER)
    assert out.ok is True and out.error is None and out.host_key_fp is None


@pytest.mark.asyncio
async def test_test_backup_target_sftp_returns_host_key_fp(monkeypatch):
    row = _row()
    _patch_row(monkeypatch, row)

    async def fake_sftp_target(_session, _cfg):
        return "sftp-target"

    async def fake_test_sftp(target):
        assert target == "sftp-target"
        return False, "host_key_mismatch", "SHA256:newfp"

    monkeypatch.setattr(sb, "sftp_target_from_settings", fake_sftp_target)
    monkeypatch.setattr(sb, "test_sftp", fake_test_sftp)
    session = _Session(row)
    out = await sb.test_backup_target("sftp", session=session, user=USER)
    assert out.ok is False and out.error == "host_key_mismatch" and out.host_key_fp == "SHA256:newfp"


# ------------------------------------------------------------------ sftp trust
@pytest.mark.asyncio
async def test_trust_sftp_host_key_persists_fp(monkeypatch, env):
    row = _row()
    _patch_row(monkeypatch, row)
    session = _Session(row)
    out = await sb.trust_sftp_host_key(
        TrustSftpHostKeyPayload(host_key_fp="SHA256:newfp"), session=session, user=USER)
    assert out == {"ok": True}
    assert row.backup["targets"]["sftp"]["host_key_fp"] == "SHA256:newfp"
    assert session.commits == 1
