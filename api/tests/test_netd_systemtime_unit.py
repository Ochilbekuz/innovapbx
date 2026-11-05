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
    default_ntp_servers,
    detect_backend,
    is_valid_ntp_server,
    is_valid_timezone,
    parse_timedatectl_show,
    parse_timesyncd_conf,
    render_timesyncd_conf,
    validate_time_config,
)


TIMESYNCD_UNIT = "/lib/systemd/system/systemd-timesyncd.service"
SHOW_TIMESYNC = ["timedatectl", "show-timesync"]
DETECT_CONTAINER = ("systemd-detect-virt", "--container")
NTP_OFF = "Timezone=Asia/Tashkent\nNTP=no\nNTPSynchronized=no\n"
TIMESYNC_REPLY = "ServerName=0.asia.pool.ntp.org\nServerAddress=1.2.3.4\nNTPMessage={ Leap=0, Stratum=2 }\n"


class FakeExecutor:
    def __init__(self, files: dict[str, str] | None = None, run_ok: bool = True,
                 outputs: dict[tuple, str] | None = None, failing: tuple = (), hanging: tuple = ()):
        self.files = dict(files or {})
        self.hanging = set(hanging)
        self.run_ok = run_ok
        self.outputs = dict(outputs or {})
        self.failing = set(failing)
        self.commands: list[list[str]] = []

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def exists(self, path: str) -> bool:
        return path in self.files

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        if tuple(argv) in self.hanging:
            raise TimeoutError  # haqiqiy Executor.run timeout'da shunday qiladi
        if not self.run_ok or tuple(argv) in self.failing:
            return CommandResult(1, "", "xato")
        default = "Timezone=Europe/London\nNTP=yes\nNTPSynchronized=yes\n" if argv == ["timedatectl", "show"] else ""
        return CommandResult(0, self.outputs.get(tuple(argv), default), "")


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
    rendered = render_timesyncd_conf(["1.1.1.1", "ntp.local"], ["0.asia.pool.ntp.org"])
    assert parse_timesyncd_conf(rendered) == ["1.1.1.1", "ntp.local"]


def test_render_timesyncd_conf_puts_regional_pool_into_fallback():
    assert render_timesyncd_conf([], ["0.asia.pool.ntp.org", "1.asia.pool.ntp.org"]) == (
        "[Time]\nNTP=\nFallbackNTP=0.asia.pool.ntp.org 1.asia.pool.ntp.org\n")


@pytest.mark.parametrize("tz,zone", [
    ("Asia/Tashkent", "asia"), ("Europe/Moscow", "europe"), ("Africa/Cairo", "africa"),
    ("Australia/Sydney", "oceania"), ("Pacific/Auckland", "oceania"), ("America/New_York", "north-america"),
    ("America/Sao_Paulo", "south-america"), ("America/Argentina/Buenos_Aires", "south-america"),
])
def test_default_ntp_servers_follow_timezone_region(tz, zone):
    assert default_ntp_servers(tz) == [f"{i}.{zone}.pool.ntp.org" for i in range(4)]


@pytest.mark.parametrize("tz", ["UTC", "Etc/GMT+5", "Atlantic/Reykjavik"])
def test_default_ntp_servers_global_pool_when_region_unknown(tz):
    assert default_ntp_servers(tz) == [f"{i}.pool.ntp.org" for i in range(4)]


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
async def test_state_survives_hanging_timedatectl_show():
    """Host'da `timedatectl` qotsa ham sahifa ochilsin (2026-11-04: «uzoq yuklanib, yuklab bo'lmadi»)."""
    executor = FakeExecutor(files={TIMESYNCD_CONF_PATH: "[Time]\nNTP=1.1.1.1\n"}, hanging=(("timedatectl", "show"),))
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert state["timezone"] == "UTC"
    assert state["ntp_servers"] == ["1.1.1.1"]
    assert state["synced"] is False


@pytest.mark.asyncio
async def test_state_survives_hanging_show_timesync():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, hanging=(tuple(SHOW_TIMESYNC),))
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert state["timezone"] == "Europe/London"
    assert state["sync_server"] is None


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
    assert executor.files[TIMESYNCD_CONF_PATH] == (
        "[Time]\nNTP=1.1.1.1\nFallbackNTP=" + " ".join(default_ntp_servers("Asia/Tashkent")) + "\n")
    assert result["timezone"] == "Europe/London"  # state() dan o'qilgan (soxta timedatectl show)


@pytest.mark.asyncio
async def test_apply_with_ntp_restarts_timesyncd_to_pick_new_servers():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""})
    service = TimeService(executor, readonly=False, now_fn=_clock())
    await service.apply(_config(ntp_enabled=True))
    assert ["systemctl", "restart", "systemd-timesyncd"] in executor.commands


@pytest.mark.asyncio
async def test_apply_failed_set_timezone_raises_and_stops():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, failing=(("timedatectl", "set-timezone", "Asia/Tashkent"),
                                                                  DETECT_CONTAINER))
    service = TimeService(executor, readonly=False, now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.apply(_config())
    assert exc.value.code == "command_failed"
    assert executor.commands == [list(DETECT_CONTAINER), ["timedatectl", "set-timezone", "Asia/Tashkent"]]


@pytest.mark.asyncio
async def test_state_reports_regional_defaults_and_current_sync_server():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, outputs={tuple(SHOW_TIMESYNC): TIMESYNC_REPLY})
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert state["default_ntp_servers"] == default_ntp_servers("Europe/London")
    assert state["sync_server"] == "0.asia.pool.ntp.org"


@pytest.mark.asyncio
async def test_state_sync_server_none_without_timesyncd():
    executor = FakeExecutor(outputs={tuple(SHOW_TIMESYNC): TIMESYNC_REPLY})
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert state["sync_server"] is None
    assert SHOW_TIMESYNC not in executor.commands


# ------------------------------------------------------------------ sync_now («Hozir sinxronlash»)

async def _no_sleep(_seconds):
    return None


def _sync_service(executor, readonly=False):
    return TimeService(executor, readonly=readonly, now_fn=_clock(), sleep_fn=_no_sleep)


@pytest.mark.asyncio
async def test_sync_now_restarts_timesyncd_and_waits_for_ntp_reply():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, outputs={tuple(SHOW_TIMESYNC): TIMESYNC_REPLY})
    state = await _sync_service(executor).sync_now()
    restart = executor.commands.index(["systemctl", "restart", "systemd-timesyncd"])
    assert SHOW_TIMESYNC in executor.commands[restart + 1:]  # javob qayta ishga tushgandan KEYIN kutiladi
    assert state["sync_server"] == "0.asia.pool.ntp.org"


@pytest.mark.asyncio
async def test_sync_now_without_ntp_reply_raises_sync_failed():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""},
                            outputs={tuple(SHOW_TIMESYNC): "ServerName=x\nNTPMessage=\n"})
    with pytest.raises(NetdError) as exc:
        await _sync_service(executor).sync_now()
    assert exc.value.code == "sync_failed"
    assert executor.commands.count(SHOW_TIMESYNC) > 1  # bir necha marta kutdi


@pytest.mark.asyncio
async def test_sync_now_requires_ntp_enabled():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""},
                            outputs={("timedatectl", "show"): "Timezone=UTC\nNTP=no\n"})
    with pytest.raises(NetdError) as exc:
        await _sync_service(executor).sync_now()
    assert exc.value.code == "ntp_disabled"
    assert ["systemctl", "restart", "systemd-timesyncd"] not in executor.commands


@pytest.mark.asyncio
async def test_sync_now_readonly_raises_without_commands():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""})
    with pytest.raises(NetdError) as exc:
        await _sync_service(executor, readonly=True).sync_now()
    assert exc.value.code == "readonly"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_sync_now_chrony_restarts_chrony():
    executor = FakeExecutor(files={"/etc/chrony/chrony.conf": ""})
    await _sync_service(executor).sync_now()
    assert ["systemctl", "restart", "chrony"] in executor.commands


@pytest.mark.asyncio
async def test_sync_now_without_sync_service_unavailable():
    with pytest.raises(NetdError) as exc:
        await _sync_service(FakeExecutor()).sync_now()
    assert exc.value.code == "ntp_unavailable"


@pytest.mark.asyncio
async def test_sync_now_failed_restart_raises_command_failed():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, failing=(("systemctl", "restart", "systemd-timesyncd"),))
    with pytest.raises(NetdError) as exc:
        await _sync_service(executor).sync_now()
    assert exc.value.code == "command_failed"


def test_state_reads_fit_inside_api_client_timeout():
    """`state()` uchta o'qish buyrug'ini (show, show-timesync, detect-virt) ketma-ket kutadi; jami API→netd mijoz chegarasidan oshsa
    mijoz uziladi va sahifa «yuklab bo'lmadi» bo'ladi."""
    from app.netd.systemtime import READ_TIMEOUT_S
    from app.services.netd_client import NetdClient
    assert 3 * READ_TIMEOUT_S < NetdClient("/x").timeout


# ------------------------------------------------------------- NTP imkonsiz holatlar
# 2026-11-05: Proxmox LXC'da «NTP yoqilgan» saqlanmasdi — `timedatectl set-ntp true` rc=0,
# lekin systemd-timesyncd `ConditionVirtualization=!container` tufayli ishga tushmaydi
# (NTP=no qoladi), panel esa «Saqlandi» deb jim turardi.

def _lxc_executor(**kwargs):
    return FakeExecutor(files={TIMESYNCD_UNIT: ""}, outputs={DETECT_CONTAINER: "lxc\n",
                                                            ("timedatectl", "show"): NTP_OFF}, **kwargs)


@pytest.mark.asyncio
async def test_state_in_container_explains_why_ntp_is_unavailable():
    state = await TimeService(_lxc_executor(), readonly=False, now_fn=_clock()).state()
    assert state["ntp_enabled"] is False
    assert "lxc" in state["ntp_unavailable_reason"]
    assert "host" in state["ntp_unavailable_reason"]


@pytest.mark.asyncio
async def test_state_on_vm_has_no_ntp_unavailable_reason():
    # Haqiqiy `systemd-detect-virt --container` konteyner bo'lmasa "none" + rc=1 qaytaradi.
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, failing=(DETECT_CONTAINER,))
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert state["ntp_unavailable_reason"] is None


@pytest.mark.asyncio
async def test_state_without_sync_service_explains_ntp_is_unavailable():
    executor = FakeExecutor()
    state = await TimeService(executor, readonly=False, now_fn=_clock()).state()
    assert "timesyncd" in state["ntp_unavailable_reason"]
    assert list(DETECT_CONTAINER) not in executor.commands


@pytest.mark.asyncio
async def test_apply_enabling_ntp_in_container_is_rejected_before_any_change():
    executor = _lxc_executor()
    with pytest.raises(NetdError) as exc:
        await TimeService(executor, readonly=False, now_fn=_clock()).apply(_config(ntp_enabled=True))
    assert exc.value.code == "ntp_unavailable"
    assert "lxc" in exc.value.message
    assert executor.commands == [list(DETECT_CONTAINER)]
    assert TIMESYNCD_CONF_PATH not in executor.files


@pytest.mark.asyncio
async def test_apply_timezone_without_ntp_in_container_still_works():
    executor = _lxc_executor()
    await TimeService(executor, readonly=False, now_fn=_clock()).apply(_config(ntp_enabled=False))
    assert ["timedatectl", "set-timezone", "Asia/Tashkent"] in executor.commands
    assert ["timedatectl", "set-ntp", "false"] in executor.commands


@pytest.mark.asyncio
async def test_apply_raises_when_ntp_service_does_not_come_up():
    """Konteyner emas, lekin xizmat baribir ishga tushmadi (masalan CAP_SYS_TIME yo'q) —
    jim «Saqlandi» emas, aniq xato."""
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, failing=(DETECT_CONTAINER,),
                            outputs={("timedatectl", "show"): NTP_OFF})
    service = TimeService(executor, readonly=False, now_fn=_clock(), sleep_fn=_no_sleep)
    with pytest.raises(NetdError) as exc:
        await service.apply(_config(ntp_enabled=True))
    assert exc.value.code == "ntp_not_started"
    assert "systemd-timesyncd" in exc.value.message
    assert ["systemctl", "restart", "systemd-timesyncd"] in executor.commands


@pytest.mark.asyncio
async def test_apply_ntp_succeeds_once_service_reports_active():
    executor = FakeExecutor(files={TIMESYNCD_UNIT: ""}, failing=(DETECT_CONTAINER,))
    state = await TimeService(executor, readonly=False, now_fn=_clock(), sleep_fn=_no_sleep).apply(
        _config(ntp_enabled=True))
    assert state["ntp_enabled"] is True


@pytest.mark.asyncio
async def test_sync_now_in_container_says_ntp_unavailable_not_disabled():
    with pytest.raises(NetdError) as exc:
        await TimeService(_lxc_executor(), readonly=False, now_fn=_clock(), sleep_fn=_no_sleep).sync_now()
    assert exc.value.code == "ntp_unavailable"
