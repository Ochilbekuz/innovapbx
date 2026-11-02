"""netd sozlamalari — faqat muhit o'zgaruvchilari (stdlib, pydantic_settings
KERAK EMAS — netd DB/FastAPI importsiz alohida jarayon)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NetdSettings:
    socket_path: str = "/run/innova-netd/netd.sock"
    readonly: bool = False
    exec_mode: str = "nsenter"  # "nsenter" | "local"
    host_root: str = "/proc/1/root"
    pending_path: str = "/var/lib/innova/netd/pending.json"
    default_timeout_s: int = 180
    min_timeout_s: int = 60
    max_timeout_s: int = 600
    version: str = "1.0"


def load_settings() -> NetdSettings:
    return NetdSettings(
        socket_path=os.environ.get("NETD_SOCKET_PATH", "/run/innova-netd/netd.sock"),
        readonly=os.environ.get("NETD_READONLY", "0") == "1",
        exec_mode=os.environ.get("NETD_EXEC", "nsenter"),
        host_root=os.environ.get("NETD_HOST_ROOT", "/proc/1/root"),
        pending_path=os.environ.get("NETD_PENDING_PATH", "/var/lib/innova/netd/pending.json"),
    )
