"""Tarmoq boshqaruvchisini aniqlash — m8-network-contract.md bo'lim 1: `netplan`
yoki NetworkManager boshqarsa — faqat ko'rish; `/etc/network/interfaces`
mavjud bo'lsa — `ifupdown` (to'liq tahrir); aks holda `unknown`."""
from __future__ import annotations

from dataclasses import dataclass

from app.netd.executor import Executor

INTERFACES_PATH = "/etc/network/interfaces"
NETPLAN_DIR = "/etc/netplan"
NETWORKMANAGER_CONF = "/etc/NetworkManager/NetworkManager.conf"

_READONLY_REASON = {
    "netplan": "bu serverda tarmoqni netplan boshqaradi. Tahrirlash Debian (ifupdown) oʻrnatmasida ishlaydi",
    "networkmanager": "bu serverda tarmoqni NetworkManager boshqaradi. Tahrirlash Debian (ifupdown) oʻrnatmasida ishlaydi",
    "unknown": "tarmoq boshqaruvchisi aniqlanmadi",
}


@dataclass(frozen=True)
class BackendInfo:
    name: str  # "ifupdown" | "netplan" | "networkmanager" | "unknown"
    editable: bool
    readonly_reason: str | None


def _has_netplan_config(executor: Executor) -> bool:
    if not executor.exists(NETPLAN_DIR):
        return False
    return any(name.endswith((".yaml", ".yml")) for name in executor.listdir(NETPLAN_DIR))


def detect_backend(executor: Executor) -> BackendInfo:
    if _has_netplan_config(executor):
        return BackendInfo("netplan", False, _READONLY_REASON["netplan"])
    if executor.exists(INTERFACES_PATH):
        return BackendInfo("ifupdown", True, None)
    if executor.exists(NETWORKMANAGER_CONF):
        return BackendInfo("networkmanager", False, _READONLY_REASON["networkmanager"])
    return BackendInfo("unknown", False, _READONLY_REASON["unknown"])
