"""`pending.json` — saqlash/yuklash/tozalash + muddat tekshiruvi
(m8-network-contract.md bo'lim 2)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.netd.pending import PendingRecord, Snapshot, clear_pending, load_pending, save_pending

PATH = "/var/lib/innova/netd/pending.json"


class _Fs:
    def __init__(self):
        self.files: dict[str, str] = {}
        self.modes: dict[str, int] = {}

    def path(self, p: str) -> str:
        return p

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content
        self.modes[path] = mode


def _record() -> PendingRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return PendingRecord(
        id="abc123", applied_at=now, expires_at=now + timedelta(seconds=60),
        summary=["eth0: qayta ishga tushiriladi"],
        snapshot=Snapshot(interfaces="iface eth0 inet dhcp\n", resolv_conf="nameserver 1.1.1.1\n",
                           hostname="host1", hosts="127.0.1.1\thost1\n"),
        meta={"source": "api"},
    )


def test_load_pending_returns_none_when_absent():
    assert load_pending(_Fs(), PATH) is None


def test_save_then_load_roundtrips():
    fs = _Fs()
    record = _record()
    save_pending(fs, PATH, record)
    loaded = load_pending(fs, PATH)
    assert loaded == record


def test_save_writes_mode_0600():
    fs = _Fs()
    save_pending(fs, PATH, _record())
    assert fs.modes[PATH] == 0o600


def test_clear_pending_removes_file(monkeypatch):
    fs = _Fs()
    save_pending(fs, PATH, _record())
    monkeypatch.setattr("os.unlink", lambda p: fs.files.pop(p, None))
    clear_pending(fs, PATH)
    assert PATH not in fs.files


def test_clear_pending_is_noop_when_missing(monkeypatch):
    fs = _Fs()

    def _raise(_p):
        raise FileNotFoundError

    monkeypatch.setattr("os.unlink", _raise)
    clear_pending(fs, PATH)  # must not raise


def test_is_expired_before_and_after_deadline():
    record = _record()
    assert record.is_expired(record.expires_at - timedelta(seconds=1)) is False
    assert record.is_expired(record.expires_at) is True
    assert record.is_expired(record.expires_at + timedelta(seconds=1)) is True
