"""`app/netd/ping.py` — Tarmoq sahifasi «Ping» diagnostikasi: chiqish parseri
(sof funksiya), host validatsiyasi va soxta `Executor` bilan ijro. HAQIQIY
`ping` HECH QACHON chaqirilmaydi (conftest ham `ping`ni taqiqlaydi)."""
from __future__ import annotations

import pytest

from app.netd.errors import NetdError
from app.netd.executor import CommandResult, ping_argv, ping_host_kind
from app.netd.ping import OUTPUT_LIMIT, WAIT_S, parse_ping_output, ping_timeout_s, run_ping

IPUTILS_OK = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=1.10 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=1.40 ms
64 bytes from 1.1.1.1: icmp_seq=4 ttl=57 time=1.20 ms

--- 1.1.1.1 ping statistics ---
4 packets transmitted, 3 received, 25% packet loss, time 3004ms
rtt min/avg/max/mdev = 1.100/1.233/1.400/0.124 ms
"""

IPUTILS_LOSS = """PING 192.0.2.1 (192.0.2.1) 56(84) bytes of data.

--- 192.0.2.1 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss, time 3060ms
"""

IPUTILS_ERRORS = """--- 10.9.9.9 ping statistics ---
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2003ms
"""

BUSYBOX_OK = """--- 8.8.8.8 ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 10.5/11.0/11.5 ms
"""

UNKNOWN_HOST = "ping: nosuchhost.invalid: Name or service not known\n"


# --------------------------------------------------------------------- parser

def test_parse_iputils_partial_loss_with_rtt():
    assert parse_ping_output(IPUTILS_OK) == {
        "ok": True, "transmitted": 4, "received": 3, "loss_pct": 25.0,
        "rtt_min_ms": 1.1, "rtt_avg_ms": 1.233, "rtt_max_ms": 1.4,
    }


def test_parse_full_loss_has_no_rtt():
    assert parse_ping_output(IPUTILS_LOSS) == {
        "ok": False, "transmitted": 4, "received": 0, "loss_pct": 100.0,
        "rtt_min_ms": None, "rtt_avg_ms": None, "rtt_max_ms": None,
    }


def test_parse_errors_field_between_received_and_loss():
    parsed = parse_ping_output(IPUTILS_ERRORS)
    assert (parsed["transmitted"], parsed["received"], parsed["loss_pct"], parsed["ok"]) == (3, 0, 100.0, False)


def test_parse_busybox_round_trip_format():
    parsed = parse_ping_output(BUSYBOX_OK)
    assert parsed == {"ok": True, "transmitted": 2, "received": 2, "loss_pct": 0.0,
                      "rtt_min_ms": 10.5, "rtt_avg_ms": 11.0, "rtt_max_ms": 11.5}


def test_parse_unknown_host_is_full_loss_without_packets():
    assert parse_ping_output(UNKNOWN_HOST) == {
        "ok": False, "transmitted": 0, "received": 0, "loss_pct": 100.0,
        "rtt_min_ms": None, "rtt_avg_ms": None, "rtt_max_ms": None,
    }


# --------------------------------------------------------------------- host / argv

@pytest.mark.parametrize("host, kind", [
    ("1.1.1.1", "ipv4"), ("2001:db8::1", "ipv6"), ("::1", "ipv6"),
    ("google.com", "name"), ("sip-trunk.example.uz", "name"), ("localhost", "name"), ("a", "name"),
])
def test_ping_host_kind_accepts(host, kind):
    assert ping_host_kind(host) == kind


@pytest.mark.parametrize("host", [
    "", "-c", "-oProxy", "a b", "a;rm -rf /", "$(id)", "host\n", "fe80::1%eth0", "a..b", ".a", "x" * 64,
    "a." + "b" * 250, "a_b.com", "1.1.1.1 -f", "ex*mple.com",
])
def test_ping_host_kind_rejects(host):
    assert ping_host_kind(host) is None


def test_ping_argv_adds_family_flag_only_for_ip_literals():
    assert ping_argv("1.1.1.1", 4, 2) == ["ping", "-c", "4", "-W", "2", "-4", "1.1.1.1"]
    assert ping_argv("2001:db8::1", 1, 5) == ["ping", "-c", "1", "-W", "5", "-6", "2001:db8::1"]
    assert ping_argv("google.com", 10, 1) == ["ping", "-c", "10", "-W", "1", "google.com"]


def test_timeout_is_count_times_wait_plus_two():
    assert ping_timeout_s(4) == 4 * WAIT_S + 2
    assert ping_timeout_s(10) == 10 * WAIT_S + 2


# --------------------------------------------------------------------- run_ping (soxta executor)

class _FakeExecutor:
    def __init__(self, result: CommandResult | Exception):
        self._result = result
        self.calls: list[tuple[list[str], float]] = []

    async def run(self, argv, *, timeout=10.0):
        self.calls.append((argv, timeout))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.mark.asyncio
async def test_run_ping_success_builds_argv_and_parses():
    executor = _FakeExecutor(CommandResult(0, IPUTILS_OK, ""))
    result = await run_ping(executor, "1.1.1.1", 4)
    assert executor.calls == [(["ping", "-c", "4", "-W", str(WAIT_S), "-4", "1.1.1.1"], ping_timeout_s(4))]
    assert result["host"] == "1.1.1.1" and result["ok"] is True and result["received"] == 3
    assert result["rtt_avg_ms"] == 1.233
    assert result["output"] == IPUTILS_OK


@pytest.mark.asyncio
async def test_run_ping_unknown_host_keeps_stderr_in_output():
    executor = _FakeExecutor(CommandResult(2, "", UNKNOWN_HOST))
    result = await run_ping(executor, "nosuchhost.invalid", 1)
    assert result["ok"] is False and result["loss_pct"] == 100.0
    assert "Name or service not known" in result["output"]


@pytest.mark.asyncio
async def test_run_ping_truncates_output():
    executor = _FakeExecutor(CommandResult(0, "x" * (OUTPUT_LIMIT * 3), ""))
    result = await run_ping(executor, "google.com", 1)
    assert len(result["output"]) == OUTPUT_LIMIT


@pytest.mark.asyncio
async def test_run_ping_timeout_is_failed_result_not_crash():
    executor = _FakeExecutor(TimeoutError())
    result = await run_ping(executor, "google.com", 2)
    assert result["ok"] is False and result["transmitted"] == 0
    assert str(int(ping_timeout_s(2))) in result["output"]


@pytest.mark.asyncio
@pytest.mark.parametrize("host, count, field", [
    ("-oProxy", 4, "host"), ("a b", 4, "host"), ("google.com", 0, "count"), ("google.com", 11, "count"),
])
async def test_run_ping_rejects_bad_input_without_running(host, count, field):
    executor = _FakeExecutor(CommandResult(0, "", ""))
    with pytest.raises(NetdError) as exc:
        await run_ping(executor, host, count)
    assert exc.value.code == "invalid_config"
    assert exc.value.fields[0]["field"] == field
    assert executor.calls == []
