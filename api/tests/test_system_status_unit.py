"""`GET /system/status` — disk/internet/SIP sof qoidalari va parsing, bazasiz/AMI'siz
(`_CmdAmi` — komandaga qarab javob beradi, `_FakeAmi`dan farqli — bu yerda `pjsip show
transports`, `core show uptime`, `pjsip show endpoints` ALOHIDA javob qaytarishi kerak)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import system_status as ss
from tests._async_helpers import const_async as _const_async

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)

# Jonli tasdiqlangan (`innova-m0-asterisk-1`, Asterisk 22, 2026-11-02): `pjsip show transports`.
_TRANSPORTS_SAMPLE = (
    "Transport:  <TransportId........>  <Type>  <cos>  <tos>  <BindAddress....................>\n"
    "==========================================================================================\n"
    "\n"
    "Transport:  transport-tcp             tcp      0      0  0.0.0.0:5060\n"
    "Transport:  transport-udp             udp      0      0  0.0.0.0:5060\n"
    "Transport:  transport-wss             wss      0      0  0.0.0.0:5060\n"
    "\n"
    "Objects found: 3\n"
)

_ENDPOINTS_SAMPLE = (
    "Contact:  101/sip:x@172.21.0.5:59158;trans 0fb0660acf NonQual  -nan\n"
    "Contact:  102/sip:y@172.21.0.5:59159;trans 0fb0660acf Unavail  -nan\n"
)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.value or []))


class _FakeSession:
    def __init__(self, numbers: list[str]) -> None:
        self.numbers = numbers

    async def execute(self, stmt, params=None):
        return _Result(self.numbers)


class _CmdAmi:
    """Buyruqga qarab javob — `sip_status` bir nechta TURLI AMI buyrug'ini chaqiradi
    (`core show uptime`, `pjsip show transports`, `pjsip show endpoints`)."""

    def __init__(self, responses: dict[str, str | None], error: Exception | None = None) -> None:
        self.responses, self.error, self.commands = responses, error, []

    async def ensure_connected(self) -> None:
        if self.error:
            raise self.error

    async def action(self, action: str, **fields) -> dict:
        self.commands.append((action, fields))
        return {"Output": self.responses.get(fields.get("Command", ""))}


# --------------------------------------------------------------- disk: scan_dir_sync
def test_scan_dir_sync_counts_recursively(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"12345")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"1234567")
    total_bytes, total_files = ss.scan_dir_sync(str(tmp_path))
    assert (total_bytes, total_files) == (12, 2)


def test_scan_dir_sync_missing_dir_returns_zero():
    assert ss.scan_dir_sync("/no/such/innova-dir") == (0, 0)


# --------------------------------------------------------------- disk: disk_categories
@pytest.mark.asyncio
async def test_disk_categories_matches_defs_and_cleanable(tmp_path):
    (tmp_path / "recordings").mkdir()
    (tmp_path / "recordings" / "a.wav").write_bytes(b"1234")
    (tmp_path / "backups").mkdir()
    (tmp_path / "migrations").mkdir()
    (tmp_path / "voicemail").mkdir()
    (tmp_path / "log").mkdir()
    settings = SimpleNamespace(
        recordings_dir=str(tmp_path / "recordings"), backups_dir=str(tmp_path / "backups"),
        migrations_dir=str(tmp_path / "migrations"), voicemail_spool_dir=str(tmp_path / "voicemail"),
        security_log_path=str(tmp_path / "log" / "security.log"),
    )
    categories = await ss.disk_categories(settings)
    by_key = {c.key: c for c in categories}
    assert by_key["recordings"].bytes == 4 and by_key["recordings"].files == 1 and by_key["recordings"].cleanable
    assert by_key["backups"].cleanable and by_key["migrations"].cleanable
    assert not by_key["voicemail"].cleanable and not by_key["logs"].cleanable
    assert {c.key for c in categories} == {"recordings", "backups", "migrations", "voicemail", "logs"}


# --------------------------------------------------------------- disk: disk_status_out
def test_disk_status_out_computes_pct_and_gb():
    gb = 1024 ** 3
    out = ss.disk_status_out(100 * gb, 25 * gb, [])
    assert out.total_gb == 100.0 and out.free_gb == 25.0 and out.used_gb == 75.0 and out.used_pct == 75


def test_disk_status_out_zero_total_is_zero_pct():
    assert ss.disk_status_out(0, 0, []).used_pct == 0


# --------------------------------------------------------------- SIP: parse_transports
def test_parse_transports_skips_header_and_parses_rows():
    transports = ss.parse_transports(_TRANSPORTS_SAMPLE)
    assert [t.name for t in transports] == ["transport-tcp", "transport-udp", "transport-wss"]
    assert transports[0].protocol == "tcp" and transports[0].bind == "0.0.0.0:5060"


def test_parse_transports_empty_output():
    assert ss.parse_transports("") == []


# --------------------------------------------------------------- internet: check_internet
@pytest.mark.asyncio
async def test_check_internet_primary_ok(monkeypatch):
    monkeypatch.setattr(ss, "dns_ok", _const_async(True))
    monkeypatch.setattr(ss, "tcp_latency_ms", _only_primary_ok)
    out = await ss.check_internet()
    assert out.up and out.dns_ok and out.latency_ms == 12 and out.target == "1.1.1.1:443" and out.error is None


@pytest.mark.asyncio
async def test_check_internet_falls_back(monkeypatch):
    monkeypatch.setattr(ss, "dns_ok", _const_async(True))
    monkeypatch.setattr(ss, "tcp_latency_ms", _only_fallback_ok)
    out = await ss.check_internet()
    assert out.up and out.latency_ms == 30 and out.target == "8.8.8.8:53" and out.error is None


@pytest.mark.asyncio
async def test_check_internet_all_down(monkeypatch):
    monkeypatch.setattr(ss, "dns_ok", _const_async(False))
    monkeypatch.setattr(ss, "tcp_latency_ms", _const_async(None))
    out = await ss.check_internet()
    assert not out.up and not out.dns_ok and out.latency_ms is None and out.error


async def _only_primary_ok(host, port):
    return 12 if (host, port) == ("1.1.1.1", 443) else None


async def _only_fallback_ok(host, port):
    return 30 if (host, port) == ("8.8.8.8", 53) else None


# --------------------------------------------------------------- SIP: sip_status
@pytest.mark.asyncio
async def test_sip_status_counts_online_and_transports():
    ami = _CmdAmi({
        "core show uptime": "System uptime: 1 day, 0 hours, 0 minutes, 0 seconds",
        "pjsip show transports": _TRANSPORTS_SAMPLE,
        "pjsip show endpoints": _ENDPOINTS_SAMPLE,
    })
    out = await ss.sip_status(ami, _FakeSession(["101", "102"]), "t")
    assert out.asterisk_up is True
    assert len(out.transports) == 3
    assert out.endpoints_total == 2 and out.endpoints_online == 1


@pytest.mark.asyncio
async def test_sip_status_ami_down_reports_unknown():
    ami = _CmdAmi({}, error=ConnectionError("no ami"))
    out = await ss.sip_status(ami, _FakeSession(["101"]), "t")
    assert out.asterisk_up is False and out.transports == []
    assert out.endpoints_total == 1 and out.endpoints_online == 0


@pytest.mark.asyncio
async def test_sip_status_no_extensions_skips_endpoint_states():
    ami = _CmdAmi({"core show uptime": "System uptime: 1s"})
    out = await ss.sip_status(ami, _FakeSession([]), "t")
    assert out.endpoints_total == 0 and out.endpoints_online == 0
