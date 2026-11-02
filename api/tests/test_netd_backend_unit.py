"""Tarmoq boshqaruvchisini aniqlash — netplan > ifupdown > NetworkManager >
unknown ustunlik tartibi (m8-network-contract.md bo'lim 1)."""
from __future__ import annotations

from app.netd.backend import INTERFACES_PATH, NETPLAN_DIR, NETWORKMANAGER_CONF, detect_backend


class _Fs:
    def __init__(self, files: set[str] | None = None, dirs: dict[str, list[str]] | None = None):
        self.files = files or set()
        self.dirs = dirs or {}

    def exists(self, path: str) -> bool:
        return path in self.files or path in self.dirs

    def listdir(self, path: str) -> list[str]:
        return self.dirs.get(path, [])


def test_netplan_wins_when_yaml_present():
    info = detect_backend(_Fs(files={INTERFACES_PATH}, dirs={NETPLAN_DIR: ["01-netcfg.yaml"]}))
    assert info.name == "netplan" and info.editable is False and info.readonly_reason


def test_netplan_dir_without_yaml_is_ignored():
    info = detect_backend(_Fs(files={INTERFACES_PATH}, dirs={NETPLAN_DIR: ["README"]}))
    assert info.name == "ifupdown" and info.editable is True and info.readonly_reason is None


def test_ifupdown_when_interfaces_file_present():
    info = detect_backend(_Fs(files={INTERFACES_PATH}))
    assert info.name == "ifupdown" and info.editable is True


def test_networkmanager_fallback():
    info = detect_backend(_Fs(files={NETWORKMANAGER_CONF}))
    assert info.name == "networkmanager" and info.editable is False and info.readonly_reason


def test_unknown_when_nothing_found():
    info = detect_backend(_Fs())
    assert info.name == "unknown" and info.editable is False and info.readonly_reason
