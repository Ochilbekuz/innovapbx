"""`app/netd/systemtime.py` — m12-contract.md B1 (sana/vaqt). Soxta `Executor`
(xotiradagi fayl tizimi) + soxta soat, HAQIQIY `timedatectl`/fayl yozuvsiz."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.netd.executor import CommandResult
from app.netd.service import NetdError
from app.netd.systemtime import (
    TIMESYNCD_CONF_PATH,
    TimeService,
    detect_backend,
    is_valid_ntp_server,
    is_valid_timezone,
    parse_timedatectl_show,
    parse_timesyncd_conf,
    render_timesyncd_conf,
    validate_time_config,
)


class FakeExecutor:
    def __init__(self, files: dict[str, str] | None = None, run_ok: bool = True):
        self.files = dict(files or {})
        self.run_ok = run_ok
        self.commands: list[list[str]] = []

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def exists(self, path: str) -> bool:
        return path in self.files

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        if not self.run_ok:
            return CommandResult(1, "", "xato")
        stdout = "Timezone=Europe/London\nNTP=yes\nNTPSynchronized=yes\n" if argv == ["timedatectl", "show"] else ""
        return CommandResult(0, stdout, "")


def _config(timezone_="Asia/Tashkent", ntp_servers=(), ntp_enabled=True):
    return SimpleNamespace(timezone=timezone_, ntp_servers=list(ntp_servers), ntp_enabled=ntp_enabled)


def _clock(when=datetime(2026, 1, 1, tzinfo=timezone.utc)):
    return lambda: when


# ------------------------------------------------------------------ validatsiya

def test_is_valid_timezone_accepts_iana_name_only():
    assert is_valid_timezone("Asia/Tashkent") is True
    assert is_valid_timezone("Mars/Base") is False
    assert is_valid_timezone(123) is False


@pytest.mark.parametrize("server", ["1.2.3.4", "ntp.example.com"])
def test_is_valid_ntp_server_accepts_ipv4_and_hostname(server):
    assert is_valid_ntp_server(server) is True


@pytest.mark.parametrize("server", ["", "not a host\n", "ntp.example.com\nrm -rf /"])
def test_is_valid_ntp_server_rejects_injection_attempts(server):
    assert is_valid_ntp_server(server) is False


def test_is_valid_ntp_server_rejects_non_string_truthy_values():
    # `int`/`bool` kabi string bo'lmagan "truthy" qiymatlar ham rad etilishi
    # SHART — `ipaddress.IPv4Address` butun sonni "qadoqlangan" IP sifatida
    # qabul qiladi (masalan `IPv4Address(123)` == `0.0.0.123`), shuning uchun
    # `isinstance(value, str)` tekshiruvi try/except'dan OLDIN kerak.
    assert is_valid_ntp_server(123) is False
    assert is_valid_ntp_server(True) is False


def test_validate_time_config_rejects_unknown_timezone():
    result = validate_time_config(_config(timezone_="Nowhere/Land"))
    assert not result.ok
    assert result.errors[0].field == "timezone"


def test_validate_time_config_rejects_too_many_ntp_servers():
    result = validate_time_config(_config(ntp_servers=["1.1.1.1"] * 6))
    assert not result.ok
    assert result.errors[0].field == "ntp_servers"


def test_validate_time_config_ntp_servers_boundary_at_max():
    assert validate_time_config(_config(ntp_servers=["1.1.1.1"] * 5)).ok  # aynan chegarada — OK
    result = validate_time_config(_config(ntp_servers=["1.1.1.1"] * 6))
    assert any(e.field == "ntp_servers" for e in result.errors)


def test_validate_time_config_ok_for_valid_input():
    result = validate_time_config(_config(ntp_servers=["1.1.1.1", "ntp.local"]))
    assert result.ok


# ------------------------------------------------------------------ render/parse

def test_render_and_parse_timesyncd_conf_roundtrip():
    rendered = render_timesyncd_conf(["1.1.1.1", "ntp.local"])
    assert parse_timesyncd_conf(rendered) == ["1.1.1.1", "ntp.local"]


def test_parse_timedatectl_show_extracts_key_values():
    props = parse_timedatectl_show("Timezone=UTC\nNTP=yes\n")
    assert props == {"Timezone": "UTC", "NTP": "yes"}


def test_detect_backend_prefers_chrony_then_timesyncd_then_none():
    assert detect_backend(FakeExecutor(files={"/etc/chrony/chrony.conf": ""})) == "chrony"
    assert detect_backend(FakeExecutor(files={"/lib/systemd/system/systemd-timesyncd.service": ""})) == "timesyncd"
    assert detect_backend(FakeExecutor()) == "none"


# ------------------------------------------------------------------ TimeService

@pytest.mark.asyncio
async def test_state_reports_parsed_timedatectl_and_ntp_servers():
    executor = FakeExecutor(files={TIMESYNCD_CONF_PATH: "[Time]\nNTP=1.1.1.1\n"})
    service = TimeService(executor, readonly=False, now_fn=_clock())
    state = await service.state()
    assert state["timezone"] == "Europe/London"
    assert state["ntp_servers"] == ["1.1.1.1"]
    assert state["ntp_enabled"] is True  # soxta `timedatectl show` "NTP=yes" qaytaradi
    assert state["synced"] is True
    assert state["readonly_reason"] is None


@pytest.mark.asyncio
async def test_state_readonly_reason_set_when_readonly():
    service = TimeService(FakeExecutor(), readonly=True, now_fn=_clock())
    state = await service.state()
    assert state["readonly_reason"]


@pytest.mark.asyncio
async def test_apply_readonly_raises_without_writing():
    executor = FakeExecutor()
    service = TimeService(executor, readonly=True, now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.apply(_config())
    assert exc.value.code == "readonly"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_apply_invalid_config_raises_without_writing():
    executor = FakeExecutor()
    service = TimeService(executor, readonly=False, now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.apply(_config(timezone_="Nowhere/Land"))
    assert exc.value.code == "invalid_config"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_apply_writes_conf_and_calls_timedatectl_set_commands():
    executor = FakeExecutor()
    service = TimeService(executor, readonly=False, now_fn=_clock())
    result = await service.apply(_config(ntp_servers=["1.1.1.1"], ntp_enabled=False))
    assert executor.commands == [
        ["timedatectl", "set-timezone", "Asia/Tashkent"],
        ["timedatectl", "set-ntp", "false"],
        ["timedatectl", "show"],  # apply() oxirida state() chaqiradi
    ]
    assert executor.files[TIMESYNCD_CONF_PATH] == "[Time]\nNTP=1.1.1.1\n"
    assert result["timezone"] == "Europe/London"  # state() dan o'qilgan (soxta timedatectl show)
