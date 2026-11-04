"""NetdService — commit-confirm holati (apply/confirm/rollback/muddat/qayta
ishga tushganda tiklash). Soxta `Executor` (xotiradagi fayl tizimi) + inyeksiya
qilinadigan soat (`now_fn`) orqali, HAQIQIY vaqt kutilmaydi."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.netd import dns as dns_mod
from app.netd import live as live_mod
from app.netd.backend import INTERFACES_PATH, NETPLAN_DIR
from app.netd.executor import CommandResult
from app.netd.service import NetdError, NetdService
from app.netd.settings import NetdSettings

DHCP_TEXT = "auto lo\niface lo inet loopback\n\nauto eth0\niface eth0 inet dhcp\n"

ETH0_LIVE = live_mod.LiveInterface(
    name="eth0", mac="aa:bb:cc:dd:ee:ff", kind="ethernet", oper_state="up",
    carrier=True, speed_mbps=1000, mtu=1500, live_ipv4=["10.0.0.5/24"], live_ipv6=[],
)


class FakeExecutor:
    def __init__(self, files: dict[str, str] | None = None, dirs: dict[str, list[str]] | None = None):
        self.files = dict(files or {})
        self.dirs = dict(dirs or {})
        self.commands: list[list[str]] = []

    def path(self, p: str) -> str:
        return p

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def is_symlink(self, path: str) -> bool:
        return False

    def exists(self, path: str) -> bool:
        return path in self.files or path in self.dirs

    def listdir(self, path: str) -> list[str]:
        return self.dirs.get(path, [])

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        return CommandResult(0, "", "")


def _ifupdown_executor(text: str = DHCP_TEXT) -> FakeExecutor:
    return FakeExecutor(files={INTERFACES_PATH: text, "/etc/hostname": "oldhost\n",
                                "/etc/hosts": "127.0.0.1\tlocalhost\n127.0.1.1\toldhost\n"})


def _settings(**overrides) -> NetdSettings:
    base = dict(readonly=False, pending_path="/var/lib/innova/netd/pending.json")
    base.update(overrides)
    return NetdSettings(**base)


def _static_config(address="10.0.0.9/24", hostname="oldhost", timeout_s=60, dns_servers=(), dns_search=()):
    return SimpleNamespace(
        hostname=hostname,
        interfaces=[SimpleNamespace(name="eth0", mode="static", address=address, gateway=None, mtu=None)],
        routes=[], dns=SimpleNamespace(servers=list(dns_servers), search=list(dns_search)), timeout_s=timeout_s,
    )


@pytest.fixture(autouse=True)
def _no_real_live(monkeypatch):
    async def fake_interfaces(executor):
        return [ETH0_LIVE]

    async def fake_routes(executor):
        return []

    async def fake_default_gw(executor):
        return live_mod.DefaultGateway(None, None)

    monkeypatch.setattr(live_mod, "gather_interfaces", fake_interfaces)
    monkeypatch.setattr(live_mod, "gather_routes", fake_routes)
    monkeypatch.setattr(live_mod, "gather_default_gateway", fake_default_gw)


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _clock() -> Clock:
    return Clock(datetime(2026, 1, 1, tzinfo=timezone.utc))


@pytest.mark.asyncio
async def test_state_reports_netplan_readonly():
    executor = FakeExecutor(dirs={NETPLAN_DIR: ["01-netcfg.yaml"]})
    service = NetdService(executor, _settings())
    state = await service.state()
    assert state["backend"] == "netplan"
    assert state["editable"] is False
    assert state["readonly_reason"]


@pytest.mark.asyncio
async def test_validate_returns_errors_for_invalid_config_without_writing_anything():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings())
    bad = _static_config(address=None)
    result = await service.validate(bad)
    assert result == {"ok": False, "errors": [{"field": "interfaces[0].address",
                                                 "message": "Statik interfeys uchun manzil majburiy"}],
                       "warnings": [], "diff": []}
    assert executor.files[INTERFACES_PATH] == DHCP_TEXT  # validate hech narsa yozmaydi


@pytest.mark.asyncio
async def test_validate_returns_diff_and_warnings_for_valid_config():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings())
    result = await service.validate(_static_config(), request_host="10.0.0.5")
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["diff"], "o'zgarish diffi bo'sh bo'lmasligi kerak (dhcp -> static)"
    assert result["warnings"] == [
        "Siz ulangan manzil o'zgaradi. Yangi manzil: http://10.0.0.9/ — "
        "60 s ichida o'sha yerdan kirib tasdiqlang"
    ]
    assert executor.files[INTERFACES_PATH] == DHCP_TEXT  # validate hech narsa yozmaydi


@pytest.mark.asyncio
async def test_apply_rejected_when_readonly():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(readonly=True))
    with pytest.raises(NetdError) as exc:
        await service.apply(_static_config())
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_apply_rejects_invalid_config():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings())
    bad = _static_config(address=None)
    with pytest.raises(NetdError) as exc:
        await service.apply(bad)
    assert exc.value.code == "invalid_config"
    assert any(f["field"] == "interfaces[0].address" for f in exc.value.fields)


@pytest.mark.asyncio
async def test_apply_opens_pending_and_rewrites_interfaces():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    state = await service.apply(_static_config())
    assert state["pending"] is not None
    assert "10.0.0.9/24" in executor.files[INTERFACES_PATH]
    assert ["ifdown", "--force", "eth0"] in executor.commands
    assert ["ifup", "eth0"] in executor.commands


@pytest.mark.asyncio
async def test_apply_writes_resolv_conf_when_dns_changes():
    executor = _ifupdown_executor()
    executor.files[dns_mod.RESOLV_PATH] = "nameserver 8.8.8.8\n"  # haqiqiy fayl (symlink emas) -> tahrirlanadi
    service = NetdService(executor, _settings(), now_fn=_clock())
    await service.apply(_static_config(dns_servers=["1.1.1.1"], dns_search=["corp.local"]))
    assert executor.files[dns_mod.RESOLV_PATH] == "nameserver 1.1.1.1\nsearch corp.local\n"


@pytest.mark.asyncio
async def test_apply_leaves_resolv_conf_untouched_when_dns_unchanged():
    executor = _ifupdown_executor()
    executor.files[dns_mod.RESOLV_PATH] = "nameserver 8.8.8.8\n"
    service = NetdService(executor, _settings(), now_fn=_clock())
    await service.apply(_static_config(dns_servers=["8.8.8.8"]))
    assert executor.files[dns_mod.RESOLV_PATH] == "nameserver 8.8.8.8\n"


@pytest.mark.asyncio
async def test_rollback_does_not_rewrite_resolv_conf_when_dns_unchanged():
    """M8 integratsiya sinovida topilgan haqiqiy xato: `_restore_hostname_dns`
    DNS o'zgarmagan bo'lsa ham `/etc/resolv.conf`ni SHARTSIZ qayta yozardi —
    oddiy faylda zararsiz, lekin ba'zi fayl tizimlarida (masalan maxsus
    bind-mount) keraksiz yozuv xatoga olib kelishi mumkin edi."""
    executor = _ifupdown_executor()
    executor.files[dns_mod.RESOLV_PATH] = "nameserver 8.8.8.8\n"
    service = NetdService(executor, _settings(), now_fn=_clock())
    applied = await service.apply(_static_config(dns_servers=["8.8.8.8"]))  # dns o'zgarmaydi
    executor.commands.clear()
    original_dns_text = executor.files[dns_mod.RESOLV_PATH]

    class _NoWriteOnUnchanged(FakeExecutor):
        def write_text_atomic(self, path, content, mode=0o644):
            if path == dns_mod.RESOLV_PATH and content == original_dns_text:
                raise AssertionError("DNS o'zgarmagan bo'lsa qayta yozilmasligi kerak")
            super().write_text_atomic(path, content, mode)

    service.executor = _NoWriteOnUnchanged(files=dict(executor.files), dirs=dict(executor.dirs))
    service.executor.files[dns_mod.RESOLV_PATH] = original_dns_text
    await service.rollback(applied["pending"]["id"])
    assert service.executor.files[dns_mod.RESOLV_PATH] == original_dns_text


@pytest.mark.asyncio
async def test_apply_rejected_when_pending_already_exists():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    await service.apply(_static_config())
    with pytest.raises(NetdError) as exc:
        await service.apply(_static_config(address="10.0.0.10/24"))
    assert exc.value.code == "pending_exists"


@pytest.mark.asyncio
async def test_confirm_clears_pending_and_keeps_change():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    applied = await service.apply(_static_config())
    confirmed = await service.confirm(applied["pending"]["id"])
    assert confirmed["pending"] is None
    assert confirmed["last_result"]["kind"] == "confirmed"
    assert "10.0.0.9/24" in executor.files[INTERFACES_PATH]


@pytest.mark.asyncio
async def test_manual_rollback_restores_original_text():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    applied = await service.apply(_static_config())
    rolled = await service.rollback(applied["pending"]["id"])
    assert rolled["pending"] is None
    assert rolled["last_result"]["kind"] == "rolled_back"
    assert executor.files[INTERFACES_PATH] == DHCP_TEXT


@pytest.mark.asyncio
async def test_pending_auto_rolls_back_after_deadline():
    executor = _ifupdown_executor()
    clock = _clock()
    service = NetdService(executor, _settings(), now_fn=clock)
    await service.apply(_static_config(timeout_s=60))
    clock.advance(61)
    state = await service.state()
    assert state["pending"] is None
    assert state["last_result"]["kind"] == "rolled_back"
    assert executor.files[INTERFACES_PATH] == DHCP_TEXT


@pytest.mark.asyncio
async def test_startup_recover_rolls_back_pending_found_on_disk():
    executor = _ifupdown_executor()
    clock = _clock()
    first = NetdService(executor, _settings(), now_fn=clock)
    await first.apply(_static_config())
    assert "10.0.0.9/24" in executor.files[INTERFACES_PATH]
    restarted = NetdService(executor, _settings(), now_fn=clock)
    assert restarted.pending is not None
    await restarted.startup_recover()
    assert restarted.pending is None
    assert executor.files[INTERFACES_PATH] == DHCP_TEXT


# ---------------------------------------------------------------- M12 B1/B2/B3 fasad
# `self.time`/`self.power`/`self.firewall` o'z testlarida chuqur tekshirilgan
# (`test_netd_systemtime_unit.py`, `test_netd_power_unit.py`,
# `test_netd_firewall_unit.py`) — bu yerda faqat `NetdService` fasad
# metodlari TO'G'RI kichik servisga yo'naltirilganini tasdiqlaymiz.

@pytest.mark.asyncio
async def test_time_state_delegates_to_time_service():
    service = NetdService(_ifupdown_executor(), _settings(), now_fn=_clock())
    state = await service.time_state()
    assert "timezone" in state


@pytest.mark.asyncio
async def test_time_apply_delegates_to_time_service():
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    config = SimpleNamespace(timezone="Asia/Tashkent", ntp_servers=[], ntp_enabled=True)
    await service.time_apply(config)
    assert ["timedatectl", "set-timezone", "Asia/Tashkent"] in executor.commands


@pytest.mark.asyncio
async def test_time_sync_delegates_to_time_service():
    # Soxta `timedatectl show` bo'sh (NTP=yes emas) -> TimeService.sync_now `ntp_disabled`.
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.time_sync()
    assert exc.value.code == "ntp_disabled"
    assert ["timedatectl", "show"] in executor.commands


@pytest.mark.asyncio
async def test_power_state_delegates_to_power_service():
    service = NetdService(_ifupdown_executor(), _settings(), now_fn=_clock())
    state = await service.power_state()
    assert state == {"readonly_reason": None}


@pytest.mark.asyncio
async def test_power_execute_readonly_delegates_to_power_service():
    service = NetdService(_ifupdown_executor(), _settings(readonly=True), now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.power_execute("reboot")
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_firewall_state_delegates_to_firewall_service_with_its_own_pending_path():
    service = NetdService(_ifupdown_executor(), _settings(), now_fn=_clock())
    state = await service.firewall_state()
    assert state["pending"] is None
    assert len(state["services"]) == 4


@pytest.mark.asyncio
async def test_firewall_pending_is_fully_independent_from_network_pending():
    """Tarmoq `pending.json`'ini ochiq qoldirib, firewall'ni qo'llash/tasdiqlash
    bir-biriga HECH QANDAY TA'SIR qilmasligi kerak (mustaqil holat fayllari)."""
    executor = _ifupdown_executor()
    service = NetdService(executor, _settings(), now_fn=_clock())
    network_applied = await service.apply(_static_config())
    assert network_applied["pending"] is not None

    firewall_config = SimpleNamespace(
        services=[SimpleNamespace(name=n, mode="all", allow=[]) for n in ("ssh", "web", "sip", "rtp")],
        blocked_cidrs=[], timeout_s=120,
    )
    firewall_applied = await service.firewall_apply(firewall_config)
    assert firewall_applied["pending"] is not None
    assert firewall_applied["pending"]["id"] != network_applied["pending"]["id"]

    confirmed = await service.confirm(network_applied["pending"]["id"])
    assert confirmed["pending"] is None
    firewall_state = await service.firewall_state()
    assert firewall_state["pending"] is not None  # tarmoq tasdiqlangani firewall'ga ta'sir qilmadi
