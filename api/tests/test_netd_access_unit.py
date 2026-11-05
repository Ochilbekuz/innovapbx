"""`app/netd/access.py` — SSH/Veb port boshqaruvi (M12 B4). Soxta `Executor`
(xotiradagi fayl tizimi) + soxta soat — HAQIQIY `systemctl`/`sshd`/`ss`/`nft`/
`docker` HECH QACHON chaqirilmaydi (2026-11-04 insident: avvalgi test
server'ni qayta yukladi — bu test shunga qarshi himoya)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from app.netd.access import (
    ENV_PATH,
    PORTS_NFT_PATH,
    SSH_SOCKET_DROPIN_PATH,
    SSHD_DROPIN_PATH,
    SSHD_MAIN_CONFIG_PATH,
    AccessService,
    FieldError,
    has_sshd_config_d_include,
    nftables_conf_is_innova,
    parse_env,
    parse_passwd_login_users,
    parse_sshd_config_fallback,
    parse_sshd_dash_t,
    parse_ss_listen_ports,
    render_ports_nft,
    render_ssh_socket_dropin,
    render_sshd_port_dropin,
    set_env_vars,
    validate_ssh_port,
    validate_web_ports,
)
from app.netd.errors import NetdError
from app.netd.executor import COMPOSE_WEB_ARGV, CommandResult, NFTABLES_CONF_PATH

PASSWD = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
    "innova:x:1000:1000:Innova:/home/innova:/bin/bash\n"
    "sync:x:1001:1001:sync:/home/sync:/bin/false\n"
)
INNOVA_NFTABLES = "# Innova PBX host firewall\ntable inet innova {\n  include \"/etc/innova/ports.nft\"\n}\n"
SSHD_MAIN_WITH_INCLUDE = "Include /etc/ssh/sshd_config.d/*.conf\n"


class FakeExecutor:
    """Xotiradagi fayl tizimi + soxta buyruq javoblari. `sshd -T` javobi
    JORIY drop-in matnidagi `Port` qatorlariga qarab HISOBLANADI — real
    `Include` ustunligini taqlid qiladi (`ignore_dropin_ports=True` bilan
    o'chirilib, asosiy konfiguratsiya ustunlik qilgan holat sinaladi)."""

    def __init__(self, files: dict[str, str] | None = None, *, ignore_dropin_ports: bool = False,
                 password_auth: bool = True, root_login: str = "no", ssh_active: bool = True,
                 ssh_socket_active: bool = False, listening_ports: tuple[int, ...] = (22,),
                 sshd_check_ok: bool = True, nft_check_ok: bool = True, nft_apply_ok: bool = True,
                 compose_ok: bool = True, base_ports: tuple[int, ...] = (22,)):
        self.files = dict(files or {})
        self._ignore_dropin_ports = ignore_dropin_ports
        self._base_ports = list(base_ports)
        self.password_auth = password_auth
        self.root_login = root_login
        self.ssh_active = ssh_active
        self.ssh_socket_active = ssh_socket_active
        self.listening_ports = list(listening_ports)
        self.sshd_check_ok = sshd_check_ok
        self.nft_check_ok = nft_check_ok
        self.nft_apply_ok = nft_apply_ok
        self.compose_ok = compose_ok
        self.commands: list[list[str]] = []

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def _effective_ports(self) -> list[int]:
        if self._ignore_dropin_ports:
            return self._base_ports
        dropin = self.files.get(SSHD_DROPIN_PATH) or ""
        found = [int(p) for p in re.findall(r"^Port (\d+)", dropin, re.MULTILINE)]
        return sorted(set(found)) or self._base_ports

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        if argv == ["systemctl", "is-active", "ssh"]:
            return CommandResult(0, "active" if self.ssh_active else "inactive", "")
        if argv == ["systemctl", "is-active", "ssh.socket"]:
            return CommandResult(0, "active" if self.ssh_socket_active else "inactive", "")
        if argv == ["sshd", "-T"]:
            lines = [f"port {p}" for p in self._effective_ports()]
            lines.append(f"passwordauthentication {'yes' if self.password_auth else 'no'}")
            lines.append(f"permitrootlogin {self.root_login}")
            return CommandResult(0, "\n".join(lines), "")
        if argv == ["sshd", "-t"]:
            return CommandResult(0, "", "") if self.sshd_check_ok else CommandResult(1, "", "sintaksis xato")
        if argv == ["ss", "-Hltn"]:
            text = "\n".join(f"LISTEN 0 128 0.0.0.0:{p} 0.0.0.0:*" for p in self.listening_ports)
            return CommandResult(0, text, "")
        if argv[:2] == ["nft", "-c"]:
            return CommandResult(0, "", "") if self.nft_check_ok else CommandResult(1, "", "nft sintaksis xato")
        if argv[:2] == ["nft", "-f"]:
            return CommandResult(0, "", "") if self.nft_apply_ok else CommandResult(1, "", "nft qo'llash xato")
        if argv == list(COMPOSE_WEB_ARGV):
            return CommandResult(0, "", "") if self.compose_ok else CommandResult(1, "", "docker xato")
        return CommandResult(0, "", "")


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _clock() -> Clock:
    return Clock(datetime(2026, 1, 1, tzinfo=timezone.utc))


def _files(**overrides) -> dict[str, str]:
    base = {SSHD_MAIN_CONFIG_PATH: SSHD_MAIN_WITH_INCLUDE, "/etc/passwd": PASSWD, NFTABLES_CONF_PATH: INNOVA_NFTABLES}
    base.update(overrides)
    return base


def _service(**kwargs) -> AccessService:
    kwargs.setdefault("readonly", False)
    kwargs.setdefault("pending_path", "/var/lib/innova/netd/access_pending.json")
    kwargs.setdefault("now_fn", _clock())
    executor = kwargs.pop("executor", None) or FakeExecutor(_files())
    return AccessService(executor, **kwargs)


# --------------------------------------------------------------------- pure funksiyalar

def test_validate_ssh_port_rejects_out_of_range():
    errors = validate_ssh_port(70000, web_ports=(80, 443))
    assert errors == [FieldError("port", "1..65535 oralig'ida butun son bo'lishi kerak")]


def test_validate_ssh_port_rejects_reserved_and_rtp():
    errors = validate_ssh_port(5060, web_ports=(80, 443))
    assert any("Tizim xizmati" in e.message for e in errors)
    errors = validate_ssh_port(15000, web_ports=(80, 443))
    assert any("RTP" in e.message for e in errors)


def test_validate_ssh_port_rejects_web_conflict():
    errors = validate_ssh_port(80, web_ports=(80, 443))
    assert any("Veb port" in e.message for e in errors)


def test_validate_ssh_port_accepts_valid_port():
    assert validate_ssh_port(2222, web_ports=(80, 443)) == []


def test_validate_web_ports_rejects_same_http_https():
    errors = validate_web_ports(8080, 8080, ssh_port=22)
    assert any(e.field == "https_port" for e in errors)


def test_validate_web_ports_rejects_ssh_conflict():
    errors = validate_web_ports(22, 443, ssh_port=22)
    assert any("SSH porti" in e.message for e in errors)


def test_validate_web_ports_accepts_valid_pair():
    assert validate_web_ports(8080, 8443, ssh_port=22) == []


def test_parse_ss_listen_ports():
    text = "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\nLISTEN 0 128 127.0.0.1:5432 0.0.0.0:*\n"
    assert parse_ss_listen_ports(text) == [22, 5432]


def test_parse_sshd_dash_t_extracts_port_and_auth():
    result = parse_sshd_dash_t("port 2222\npasswordauthentication no\npermitrootlogin prohibit-password\n")
    assert result == {"ports": [2222], "password_auth": False, "root_login": "prohibit-password"}


def test_parse_sshd_config_fallback_dropin_overrides_main():
    result = parse_sshd_config_fallback("Port 22\nPasswordAuthentication no\n", "Port 2222\n")
    assert result["ports"] == [2222]
    assert result["password_auth"] is False


def test_parse_passwd_login_users_filters_system_and_nologin():
    assert parse_passwd_login_users(PASSWD) == ["innova"]


def test_nftables_conf_is_innova():
    assert nftables_conf_is_innova(INNOVA_NFTABLES) is True
    assert nftables_conf_is_innova("table inet filter {}\n") is False
    assert nftables_conf_is_innova(None) is False


def test_has_sshd_config_d_include():
    assert has_sshd_config_d_include(SSHD_MAIN_WITH_INCLUDE) is True
    assert has_sshd_config_d_include("Port 22\n") is False


def test_render_sshd_port_dropin_sorts_and_dedupes():
    assert render_sshd_port_dropin([2222, 22, 22]) == (
        "# Innova PBX — netd avtomatik yaratadi, qo'lda tahrir qilinmasin.\nPort 22\nPort 2222\n")


def test_render_ssh_socket_dropin():
    # Bo'sh `ListenStream=` — paketdagi asl `ListenStream=22` ni bekor qiladi; usiz systemd
    # ro'yxatga QO'SHADI va eski port tasdiqdan keyin ham ochiq qolardi.
    assert render_ssh_socket_dropin([22, 2222]) == "[Socket]\nListenStream=\nListenStream=22\nListenStream=2222\n"


def test_render_ports_nft():
    assert render_ports_nft([2222, 22]) == (
        "# Innova PBX — netd avtomatik yaratadi, qo'lda tahrir qilinmasin.\ndefine INNOVA_SSH_PORTS = { 22, 2222 }\n")


def test_parse_env():
    assert parse_env("# izoh\nWEB_HOST_PORT=80\nWEB_HTTPS_PORT=443\n") == {
        "WEB_HOST_PORT": "80", "WEB_HTTPS_PORT": "443"}


def test_set_env_vars_updates_existing_and_appends_new():
    out = set_env_vars("WEB_HOST_PORT=80\n# izoh\n", {"WEB_HOST_PORT": "8080", "WEB_HTTPS_PORT": "8443"})
    assert out == "WEB_HOST_PORT=8080\n# izoh\nWEB_HTTPS_PORT=8443\n"


# --------------------------------------------------------------------- state()

@pytest.mark.asyncio
async def test_state_reports_readonly_reason_when_readonly():
    state = await _service(readonly=True).state()
    assert state["readonly_reason"]


@pytest.mark.asyncio
async def test_state_assembles_ssh_and_web_and_host_firewall_innova():
    service = _service(executor=FakeExecutor(_files(**{ENV_PATH: "WEB_HOST_PORT=80\nWEB_HTTPS_PORT=443\n"})))
    state = await service.state()
    assert state["ssh"]["port"] == 22
    assert state["ssh"]["active"] is True
    assert state["ssh"]["login_users"] == ["innova"]
    assert state["ssh"]["host_firewall"] == "innova"
    assert state["web"] == {"http_port": 80, "https_port": 443}
    assert state["pending"] is None
    assert state["last_result"] is None


@pytest.mark.asyncio
async def test_state_host_firewall_external_when_signature_missing():
    service = _service(executor=FakeExecutor(_files(**{NFTABLES_CONF_PATH: "table inet filter {}\n"})))
    state = await service.state()
    assert state["ssh"]["host_firewall"] == "external"


# --------------------------------------------------------------------- ssh_apply()

@pytest.mark.asyncio
async def test_ssh_apply_opens_pending_with_both_ports_listening():
    executor = FakeExecutor(_files())
    service = _service(executor=executor, now_fn=_clock())
    result = await service.ssh_apply(2222)
    assert set(result.keys()) == {"pending_id", "expires_at", "warnings"}
    assert result["warnings"] == []
    dropin = executor.files[SSHD_DROPIN_PATH]
    assert "Port 22" in dropin and "Port 2222" in dropin
    assert service.pending.kind == "ssh"
    assert service.pending.old_ports == [22] and service.pending.new_ports == [2222]
    assert ["nft", "-f", NFTABLES_CONF_PATH] in executor.commands


@pytest.mark.asyncio
async def test_ssh_apply_rejects_same_port():
    with pytest.raises(NetdError) as exc:
        await _service().ssh_apply(22)
    assert exc.value.code == "invalid_config"


@pytest.mark.asyncio
async def test_ssh_apply_rejects_web_port_conflict():
    executor = FakeExecutor(_files(**{ENV_PATH: "WEB_HOST_PORT=2222\nWEB_HTTPS_PORT=443\n"}))
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(2222)
    assert exc.value.code == "invalid_config"
    assert exc.value.fields[0]["field"] == "port"


@pytest.mark.asyncio
async def test_ssh_apply_rejects_other_listener_conflict():
    executor = FakeExecutor(_files(), listening_ports=(22, 9999))
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(9999)
    assert exc.value.code == "invalid_config"


@pytest.mark.asyncio
async def test_ssh_apply_unsupported_without_include_directive():
    executor = FakeExecutor(_files(**{SSHD_MAIN_CONFIG_PATH: "Port 22\n"}))
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(2222)
    assert exc.value.code == "unsupported"


@pytest.mark.asyncio
async def test_ssh_apply_readonly_raises_without_writing():
    executor = FakeExecutor(_files())
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor, readonly=True).ssh_apply(2222)
    assert exc.value.code == "readonly"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_ssh_apply_pending_exists_raises():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    await service.ssh_apply(2222)
    with pytest.raises(NetdError) as exc:
        await service.ssh_apply(2223)
    assert exc.value.code == "pending_exists"


@pytest.mark.asyncio
async def test_ssh_apply_conflicts_with_other_pending_firewall():
    service = _service(executor=FakeExecutor(_files()), other_pending=lambda: True)
    with pytest.raises(NetdError) as exc:
        await service.ssh_apply(2222)
    assert exc.value.code == "pending_exists"


@pytest.mark.asyncio
async def test_ssh_apply_sshd_dash_t_check_failure_rolls_back():
    executor = FakeExecutor(_files(), sshd_check_ok=False)
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(2222)
    assert exc.value.code == "invalid_config"
    assert executor.files[SSHD_DROPIN_PATH] == ""
    assert service_has_no_pending(executor)


def service_has_no_pending(executor: FakeExecutor) -> bool:
    return not executor.files.get("/var/lib/innova/netd/access_pending.json")


@pytest.mark.asyncio
async def test_ssh_apply_sshd_config_conflict_rolls_back():
    executor = FakeExecutor(_files(), ignore_dropin_ports=True, base_ports=(22,))
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(2222)
    assert exc.value.code == "sshd_config_conflict"


@pytest.mark.asyncio
async def test_ssh_apply_uses_socket_dropin_when_ssh_socket_active():
    executor = FakeExecutor(_files(), ssh_socket_active=True)
    await _service(executor=executor).ssh_apply(2222)
    assert SSH_SOCKET_DROPIN_PATH in executor.files
    assert ["systemctl", "restart", "ssh.socket"] in executor.commands
    assert ["systemctl", "reload", "ssh"] not in executor.commands


@pytest.mark.asyncio
async def test_ssh_apply_warns_when_host_firewall_not_innova():
    executor = FakeExecutor(_files(**{NFTABLES_CONF_PATH: "table inet filter {}\n"}))
    result = await _service(executor=executor).ssh_apply(2222)
    assert "o'zingiz ochishingiz kerak" in result["warnings"][0]
    assert PORTS_NFT_PATH not in executor.files


@pytest.mark.asyncio
async def test_ssh_apply_nft_apply_failure_rolls_back():
    executor = FakeExecutor(_files(), nft_apply_ok=False)
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).ssh_apply(2222)
    assert exc.value.code == "apply_failed"
    assert executor.files[SSHD_DROPIN_PATH] == ""


# --------------------------------------------------------------------- confirm()/rollback()

@pytest.mark.asyncio
async def test_confirm_ssh_rewrites_dropin_to_single_port_and_clears_pending():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    applied = await service.ssh_apply(2222)
    state = await service.confirm(applied["pending_id"])
    assert state["pending"] is None
    assert state["last_result"]["status"] == "confirmed"
    ports = [int(p) for p in re.findall(r"^Port (\d+)$", executor.files[SSHD_DROPIN_PATH], re.MULTILINE)]
    assert ports == [2222]


@pytest.mark.asyncio
async def test_confirm_web_clears_pending_without_sshd_calls():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    applied = await service.web_apply(8080, 8443)
    executor.commands.clear()
    state = await service.confirm(applied["pending_id"])
    assert state["pending"] is None
    assert ["systemctl", "reload", "ssh"] not in executor.commands
    assert ["sshd", "-t"] not in executor.commands  # faqat ssh-kind confirm'da chaqiriladi


@pytest.mark.asyncio
async def test_confirm_rejects_wrong_kind():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    applied = await service.ssh_apply(2222)
    with pytest.raises(NetdError) as exc:
        await service.confirm(applied["pending_id"], kind="web")
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_confirm_rejects_unknown_pending_id():
    with pytest.raises(NetdError) as exc:
        await _service().confirm("yoq-bunday-id")
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_rollback_restores_snapshot_and_sets_last_result():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    applied = await service.ssh_apply(2222)
    state = await service.rollback(applied["pending_id"])
    assert state["pending"] is None
    assert state["last_result"]["status"] == "rolled_back"
    assert executor.files.get(SSHD_DROPIN_PATH) == ""


@pytest.mark.asyncio
async def test_maybe_expire_auto_rolls_back_on_timeout():
    executor = FakeExecutor(_files())
    clock = _clock()
    service = _service(executor=executor, now_fn=clock)
    await service.ssh_apply(2222, timeout_s=30)
    clock.advance(31)
    state = await service.state()
    assert state["pending"] is None
    assert state["last_result"]["message"] == "Vaqt tugadi — kirish sozlamasi avtomatik qaytarildi"


@pytest.mark.asyncio
async def test_startup_recover_rolls_back_unconfirmed_pending():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    await service.ssh_apply(2222)
    await service.startup_recover()
    assert service.pending is None
    assert service.last_result.message.startswith("netd qayta ishga tushdi")


@pytest.mark.asyncio
async def test_startup_recover_noop_without_pending():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    await service.startup_recover()
    assert service.last_result is None
    assert executor.commands == []


# --------------------------------------------------------------------- web_apply()

@pytest.mark.asyncio
async def test_web_apply_opens_pending_and_recreates_container():
    executor = FakeExecutor(_files())
    result = await _service(executor=executor).web_apply(8080, 8443)
    assert set(result.keys()) == {"pending_id", "expires_at", "warnings"}
    assert "WEB_HOST_PORT=8080" in executor.files[ENV_PATH]
    assert "WEB_HTTPS_PORT=8443" in executor.files[ENV_PATH]
    assert list(COMPOSE_WEB_ARGV) in executor.commands


@pytest.mark.asyncio
async def test_web_apply_rejects_same_ports_as_current():
    executor = FakeExecutor(_files(**{ENV_PATH: "WEB_HOST_PORT=80\nWEB_HTTPS_PORT=443\n"}))
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).web_apply(80, 443)
    assert exc.value.code == "invalid_config"


@pytest.mark.asyncio
async def test_web_apply_compose_failure_restores_env_and_raises():
    executor = FakeExecutor(_files(**{ENV_PATH: "WEB_HOST_PORT=80\nWEB_HTTPS_PORT=443\n"}), compose_ok=False)
    with pytest.raises(NetdError) as exc:
        await _service(executor=executor).web_apply(8080, 8443)
    assert exc.value.code == "command_failed"
    assert executor.files[ENV_PATH] == "WEB_HOST_PORT=80\nWEB_HTTPS_PORT=443\n"
    assert executor.commands.count(list(COMPOSE_WEB_ARGV)) == 2  # urinish + qaytarish


@pytest.mark.asyncio
async def test_web_apply_readonly_raises():
    with pytest.raises(NetdError) as exc:
        await _service(readonly=True).web_apply(8080, 8443)
    assert exc.value.code == "readonly"


# --------------------------------------------------------------------- current_ports()

@pytest.mark.asyncio
async def test_current_ports_reflects_effective_sshd_and_web_env():
    executor = FakeExecutor(_files(**{ENV_PATH: "WEB_HOST_PORT=8080\nWEB_HTTPS_PORT=8443\n"}))
    ports = await _service(executor=executor).current_ports()
    assert ports == {"ssh": [22], "web": [8080, 8443]}


@pytest.mark.asyncio
async def test_current_ports_shows_both_ports_during_pending_ssh_change():
    executor = FakeExecutor(_files())
    service = _service(executor=executor)
    await service.ssh_apply(2222)
    ports = await service.current_ports()
    assert ports["ssh"] == [22, 2222]
