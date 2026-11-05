"""`app/netd/executor.py` — allowlist, argv (shell=False), atomik yozish,
`host_path` (m8-network-contract.md bo'lim 1: FAQAT nsenter + argv ro'yxati)."""
from __future__ import annotations

import os
import stat

import pytest

from app.netd.executor import (
    COMPOSE_WEB_ARGV,
    FIREWALL_CONF_PATH,
    NFTABLES_CONF_PATH,
    CommandNotAllowedError,
    Executor,
    host_path,
)


def test_host_path_joins_under_root():
    assert host_path("/proc/1/root", "/etc/hostname") == "/proc/1/root/etc/hostname"


def test_host_path_rejects_relative_input():
    with pytest.raises(ValueError):
        host_path("/proc/1/root", "etc/hostname")


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        Executor("sudo", "/")


def test_local_mode_does_not_wrap_with_nsenter():
    executor = Executor("local", "/")
    assert executor._wrap(["ip", "addr"]) == ["ip", "addr"]


def test_nsenter_mode_wraps_argv():
    executor = Executor("nsenter", "/proc/1/root")
    wrapped = executor._wrap(["ip", "addr"])
    assert wrapped == ["nsenter", "-t", "1", "-m", "-u", "-n", "-i", "-p", "--", "ip", "addr"]


@pytest.mark.asyncio
async def test_run_rejects_binary_outside_allowlist():
    executor = Executor("local", "/")
    with pytest.raises(CommandNotAllowedError):
        await executor.run(["rm", "-rf", "/"])


@pytest.mark.asyncio
async def test_run_rejects_empty_argv():
    executor = Executor("local", "/")
    with pytest.raises(CommandNotAllowedError):
        await executor.run([])


@pytest.mark.asyncio
async def test_run_executes_allowlisted_binary(tmp_path):
    executor = Executor("local", "/")
    result = await executor.run(["hostname"])
    assert result.returncode in (0, 1)  # muhitga qarab farq qilishi mumkin, muhimi ishlaydi


def test_write_text_atomic_then_read_back(tmp_path):
    executor = Executor("local", str(tmp_path))
    executor.write_text_atomic("/etc/network/interfaces", "auto lo\n")
    assert executor.read_text("/etc/network/interfaces") == "auto lo\n"
    assert executor.exists("/etc/network/interfaces")


def test_write_text_atomic_sets_mode(tmp_path):
    executor = Executor("local", str(tmp_path))
    executor.write_text_atomic("/var/lib/innova/netd/pending.json", "{}", mode=0o600)
    full = executor.path("/var/lib/innova/netd/pending.json")
    assert stat.S_IMODE(os.stat(full).st_mode) == 0o600


def test_read_text_missing_file_returns_none(tmp_path):
    executor = Executor("local", str(tmp_path))
    assert executor.read_text("/nope") is None


def test_listdir_missing_dir_returns_empty(tmp_path):
    executor = Executor("local", str(tmp_path))
    assert executor.listdir("/nope") == []


def test_is_symlink_detection(tmp_path):
    executor = Executor("local", str(tmp_path))
    target = tmp_path / "real.conf"
    target.write_text("x")
    link = tmp_path / "etc" / "resolv.conf"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    assert executor.is_symlink("/etc/resolv.conf") is True
    assert executor.is_symlink("/etc/real.conf") is False


# --------------------------------------------------------------------- M12 B1/B2/B3: yangi binarlar + argv guard

@pytest.mark.asyncio
@pytest.mark.parametrize("argv", [
    ["timedatectl", "show"],
    ["timedatectl", "set-ntp", "true"],
    ["timedatectl", "set-ntp", "false"],
    ["timedatectl", "set-timezone", "Asia/Tashkent"],
    ["timedatectl", "show-timesync"],
    ["systemctl", "reboot"],
    ["systemctl", "poweroff"],
    ["systemctl", "restart", "systemd-timesyncd"],
    ["systemctl", "restart", "chrony"],
    ["nft", "-c", "-f", FIREWALL_CONF_PATH],
    ["nft", "-f", FIREWALL_CONF_PATH],
    # Kirish (SSH/Veb) — M12 B4
    ["nft", "-c", "-f", NFTABLES_CONF_PATH],
    ["nft", "-f", NFTABLES_CONF_PATH],
    ["sshd", "-t"],
    ["sshd", "-T"],
    ["ss", "-Hltn"],
    ["systemctl", "is-active", "ssh"],
    ["systemctl", "is-active", "ssh.socket"],
    ["systemctl", "reload", "ssh"],
    ["systemctl", "restart", "ssh.socket"],
    ["systemctl", "daemon-reload"],
    list(COMPOSE_WEB_ARGV),
    # Tarmoq «Ping» tabi — faqat `ping -c N -W S [-4|-6] <host>`
    ["ping", "-c", "4", "-W", "2", "-4", "1.1.1.1"],
    ["ping", "-c", "1", "-W", "5", "-6", "2001:db8::1"],
    ["ping", "-c", "10", "-W", "1", "google.com"],
    # Sana/vaqt — konteyner (LXC) aniqlash: NTP u yerda ishlamaydi
    ["systemd-detect-virt", "--container"],
])
async def test_run_accepts_allowlisted_argv_for_new_binaries(argv, monkeypatch):
    # XAVF: bu buyruqlar HAQIQIY bajarilsa host qayta yuklanadi/o'chadi (2026-11-04 dev/bot
    # serveri shu test tufayli 3 marta reboot bo'lgan) — subprocess DOIM soxta.
    calls: list[tuple[str, ...]] = []

    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def _fake_exec(*args, **_kwargs):
        calls.append(args)
        return _FakeProc()

    monkeypatch.setattr("app.netd.executor.asyncio.create_subprocess_exec", _fake_exec)
    executor = Executor("local", "/")
    result = await executor.run(argv)
    assert result.returncode == 0
    assert calls == [tuple(argv)]


@pytest.mark.asyncio
@pytest.mark.parametrize("argv", [
    ["timedatectl", "set-timezone", "../../etc/passwd"],
    ["timedatectl", "set-timezone", "a; rm -rf /"],
    ["timedatectl", "revert"],
    ["systemctl", "stop", "sshd"],
    ["systemctl", "restart", "sshd"],
    ["systemctl", "restart", "systemd-timesyncd", "asterisk"],
    ["systemd-detect-virt"],
    ["systemd-detect-virt", "--container", "--quiet"],
    ["timedatectl", "show-timesync", "--all"],
    ["systemctl", "reboot", "--now"],
    ["nft", "flush", "ruleset"],
    ["nft", "list", "table", "ip", "filter"],
    ["nft", "list", "table", "inet", "innova_fw"],
    ["nft", "-c", "-f", "/etc/innova/firewall.nft", "extra"],
    ["nft", "-f", NFTABLES_CONF_PATH, "extra"],
    # Kirish (SSH/Veb) — M12 B4: ruxsat etilmagan argv'lar
    ["sshd", "-D"],
    ["sshd", "-t", "-f", "/tmp/evil.conf"],
    ["ss", "-tunlp"],
    ["systemctl", "restart", "ssh"],
    ["systemctl", "stop", "ssh.socket"],
    ["docker", "compose", "down"],
    [*COMPOSE_WEB_ARGV[:-1], "api"],  # web o'rniga boshqa konteyner
    # Tarmoq «Ping» — argument in'eksiyasi / chegaradan tashqari qiymatlar
    ["ping", "-c", "4", "-W", "2", "-oProxy"],
    ["ping", "-c", "4", "-W", "2", "-f", "1.1.1.1"],
    ["ping", "-c", "11", "-W", "2", "-4", "1.1.1.1"],
    ["ping", "-c", "0", "-W", "2", "-4", "1.1.1.1"],
    ["ping", "-c", "4", "-W", "6", "-4", "1.1.1.1"],
    ["ping", "-c", "04", "-W", "2", "-4", "1.1.1.1"],
    ["ping", "-c", "4", "-W", "2", "1.1.1.1"],  # IP literal — oila bayrog'isiz emas
    ["ping", "-c", "4", "-W", "2", "-6", "1.1.1.1"],  # noto'g'ri oila
    ["ping", "-c", "4", "-W", "2", "-4", "google.com"],
    ["ping", "-W", "2", "-c", "4", "google.com"],
    ["ping", "-c", "4", "-W", "2", "a b"],
    ["ping", "-c", "4", "-W", "2", "google.com", "extra"],
    ["ping", "-c", "x", "-W", "2", "google.com"],
    ["ping", "google.com"],
])
async def test_run_rejects_argv_outside_per_binary_guard(argv):
    executor = Executor("local", "/")
    with pytest.raises(CommandNotAllowedError):
        await executor.run(argv)


@pytest.mark.asyncio
async def test_conftest_guard_blocks_host_changing_binaries():
    # Xavfsiz argv (`echo`) — qo'riqchi faqat so'z bo'yicha tutadi, hech narsa bajarilmaydi.
    import asyncio
    with pytest.raises(RuntimeError, match="taqiqlangan"):
        await asyncio.create_subprocess_exec("echo", "systemctl")


@pytest.mark.asyncio
async def test_run_timeout_kills_grandchildren_too(tmp_path, monkeypatch):
    """`nsenter -p` buyruqni BOLA jarayonda bajaradi; timeout'da faqat ota o'ldirilsa bola stdout
    quvurini ushlab turadi va `run()` u tugaguncha osilib qoladi (2026-11-04: 3 s timeout → 30 s,
    «Sana va vaqt» sahifasi yuklanmadi). Butun jarayon guruhi o'ldirilishi SHART."""
    import time

    fake = tmp_path / "hostname"  # allowlist'da, lekin conftest taqiqlamaydi (host'ga tegmaydi)
    fake.write_text(f"#!/bin/sh\nsleep 30 &\necho $! > {tmp_path}/child.pid\nwait\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await Executor("local", "/").run(["hostname"], timeout=0.5)
    assert time.monotonic() - started < 5
    child = int((tmp_path / "child.pid").read_text())
    assert _is_dead(child)


def _is_dead(pid: int) -> bool:
    """O'ldirilgan, lekin hali yig'ib olinmagan (zombie) jarayon ham o'lik hisoblanadi."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] in ("Z", "X")
    except FileNotFoundError:
        return True
