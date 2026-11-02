"""Mezbon nomi — `/etc/hostname`, `/etc/hosts`dagi `127.0.1.1` qatori,
`hostname <nom>` (allowlist'dagi buyruq) — m8-network-contract.md bo'lim 1."""
from __future__ import annotations

import re

from app.netd.executor import Executor

HOSTNAME_PATH = "/etc/hostname"
HOSTS_PATH = "/etc/hosts"
_HOSTS_127_RE = re.compile(r"^127\.0\.1\.1\s+")


def read_hostname(executor: Executor) -> str:
    raw = executor.read_text(HOSTNAME_PATH)
    return (raw or "").strip() or "localhost"


def render_hosts(old_hosts_text: str, new_hostname: str) -> str:
    """`127.0.1.1 <eski-nom>` qatorini yangi nomga almashtiradi; boshqa
    qatorlar O'ZGARMAYDI (qator topilmasa — hech narsa qo'shilmaydi)."""
    out = []
    for line in old_hosts_text.splitlines(keepends=True):
        if _HOSTS_127_RE.match(line):
            ending = "\n" if line.endswith("\n") else ""
            out.append(f"127.0.1.1\t{new_hostname}{ending}")
        else:
            out.append(line)
    return "".join(out)


async def apply_hostname(executor: Executor, new_hostname: str) -> None:
    executor.write_text_atomic(HOSTNAME_PATH, new_hostname + "\n")
    old_hosts = executor.read_text(HOSTS_PATH) or ""
    executor.write_text_atomic(HOSTS_PATH, render_hosts(old_hosts, new_hostname))
    await executor.run(["hostname", new_hostname], timeout=5.0)
