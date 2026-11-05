"""Tarmoq diagnostikasi — `ping` (Tarmoq sahifasi «Ping» tabi): admin SIP
server, shlyuz yoki internetga ulanishni tekshiradi. Konfiguratsiyani
o'zgartirmaydi — `NETD_READONLY`da ham ishlaydi. argv shakli va host
qoidasi bitta joyda: `executor.py::ping_argv`/`ping_host_kind` (guard ham
shularni ishlatadi)."""
from __future__ import annotations

import re
from typing import Any

from app.netd.errors import NetdError
from app.netd.executor import PING_COUNTS, Executor, ping_argv, ping_host_kind

WAIT_S = 2  # `-W` — har javobni kutish (s)
OUTPUT_LIMIT = 4096

_PACKETS_RE = re.compile(r"(\d+) packets transmitted, (\d+) (?:packets )?received")
_LOSS_RE = re.compile(r"([\d.]+)% packet loss")
_RTT_RE = re.compile(r"(?:rtt|round-trip) min/avg/max(?:/mdev)? = ([\d.]+)/([\d.]+)/([\d.]+)")


def ping_timeout_s(count: int) -> float:
    """Eng yomon holat: har paket `WAIT_S` kutadi + 2 s zaxira (DNS/ishga tushish)."""
    return float(count * WAIT_S + 2)


def parse_ping_output(text: str) -> dict[str, Any]:
    """iputils/busybox `ping` statistikasini o'qiydi. Statistika yo'q (masalan
    noma'lum host) — 0 paket, 100% yo'qotish."""
    packets = _PACKETS_RE.search(text)
    transmitted, received = (int(packets[1]), int(packets[2])) if packets else (0, 0)
    loss = _LOSS_RE.search(text)
    rtt = _RTT_RE.search(text)
    rtt_min, rtt_avg, rtt_max = (float(v) for v in rtt.groups()) if rtt else (None, None, None)
    return {
        "ok": received > 0, "transmitted": transmitted, "received": received,
        "loss_pct": float(loss[1]) if loss else 100.0,
        "rtt_min_ms": rtt_min, "rtt_avg_ms": rtt_avg, "rtt_max_ms": rtt_max,
    }


def _check_input(host: str, count: int) -> None:
    if ping_host_kind(host) is None:
        raise NetdError("invalid_config", "Yaroqsiz host",
                         [{"field": "host", "message": "IPv4/IPv6 manzil yoki domen nomi bo'lishi kerak"}])
    if count not in PING_COUNTS:
        raise NetdError("invalid_config", "Yaroqsiz paketlar soni",
                         [{"field": "count", "message": "1 dan 10 gacha bo'lishi kerak"}])


async def _run(executor: Executor, host: str, count: int) -> str:
    timeout = ping_timeout_s(count)
    try:
        result = await executor.run(ping_argv(host, count, WAIT_S), timeout=timeout)
    except TimeoutError:
        return f"ping: {timeout:g} s ichida tugamadi\n"
    return result.stdout + result.stderr


async def run_ping(executor: Executor, host: str, count: int) -> dict[str, Any]:
    _check_input(host, count)
    output = await _run(executor, host, count)
    return {"host": host, **parse_ping_output(output), "output": output[:OUTPUT_LIMIT]}
