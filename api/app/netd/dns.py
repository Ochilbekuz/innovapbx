"""DNS — `/etc/resolv.conf`: oddiy fayl bo'lsa tahrirlanadi, symlink bo'lsa
`editable=false` (ko'pincha systemd-resolved) — m8-network-contract.md bo'lim 1."""
from __future__ import annotations

from app.netd.executor import Executor

RESOLV_PATH = "/etc/resolv.conf"


def is_dns_editable(executor: Executor) -> bool:
    return executor.exists(RESOLV_PATH) and not executor.is_symlink(RESOLV_PATH)


def parse_resolv_conf(text: str) -> tuple[list[str], list[str]]:
    servers: list[str] = []
    search: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("nameserver"):
            parts = stripped.split()
            if len(parts) >= 2:
                servers.append(parts[1])
        elif stripped.startswith("search"):
            search = stripped.split()[1:]
    return servers, search


def render_resolv_conf(servers: list[str], search: list[str]) -> str:
    lines = [f"nameserver {s}" for s in servers]
    if search:
        lines.append("search " + " ".join(search))
    return ("\n".join(lines) + "\n") if lines else ""


def write_resolv_conf(executor: Executor, servers: list[str], search: list[str]) -> None:
    executor.write_text_atomic(RESOLV_PATH, render_resolv_conf(servers, search))
