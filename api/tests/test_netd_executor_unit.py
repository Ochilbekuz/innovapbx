"""`app/netd/executor.py` — allowlist, argv (shell=False), atomik yozish,
`host_path` (m8-network-contract.md bo'lim 1: FAQAT nsenter + argv ro'yxati)."""
from __future__ import annotations

import os
import stat

import pytest

from app.netd.executor import CommandNotAllowedError, Executor, host_path


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
