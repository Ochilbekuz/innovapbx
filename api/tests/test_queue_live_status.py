"""`queue_live_status`/`_longest_wait_s` — `queue show <name>` chiqishini
tahlil qiladi. Namuna JONLI tasdiqlangan (`innova-m0-asterisk-1` konteyneri,
2026-10-28, `channel originate Local/700@parkedcalls application Queue <q>`
bilan sinovda olingan) — m1b-contract.md bo'lim 5 "queues.longest_wait_s"."""
from __future__ import annotations

import pytest

from app.services.live_status import _longest_wait_s, queue_live_status

QUEUE = "t1-q-ef1ca0c7-e8f8-41ff-88bc-6dbf2e42961b"

_EMPTY_OUTPUT = (
    f"{QUEUE} has 0 calls (max unlimited) in 'ringall' strategy (0s holdtime, 0s talktime), "
    "W:0, C:0, A:0, SL:0.0%, SL2:0.0% within 20s\n"
    "   Members: \n"
    "      Agent101 (PJSIP/t1-101) (ringinuse disabled) (realtime) (Unavailable) has taken no calls yet "
    "(login was 0 secs ago)\n"
    "   No Callers\n"
)

_ONE_CALLER_OUTPUT = (
    f"{QUEUE} has 1 calls (max unlimited) in 'ringall' strategy (0s holdtime, 0s talktime), "
    "W:0, C:0, A:0, SL:0.0%, SL2:0.0% within 20s\n"
    "   Members: \n"
    "      Agent101 (PJSIP/t1-101) (ringinuse disabled) (realtime) (Unavailable) has taken no calls yet "
    "(login was 13 secs ago)\n"
    "      Agent102 (PJSIP/t1-102) (ringinuse disabled) (realtime) (Not in use) has taken no calls yet "
    "(login was 13 secs ago)\n"
    "   Callers: \n"
    "      1. Local/700@parkedcalls-00000004;1 (wait: 0:11, prio: 0)\n"
)

_TWO_CALLERS_OUTPUT = _ONE_CALLER_OUTPUT.replace(
    "      1. Local/700@parkedcalls-00000004;1 (wait: 0:11, prio: 0)\n",
    "      1. Local/700@parkedcalls-00000004;1 (wait: 0:11, prio: 0)\n"
    "      2. Local/701@parkedcalls-00000005;1 (wait: 1:05, prio: 0)\n",
)


class _FakeAmi:
    def __init__(self, output: str | None) -> None:
        self._output = output

    async def ensure_connected(self) -> None:
        return None

    async def action(self, action: str, **fields) -> dict:
        if self._output is None:
            raise ConnectionError("AMI yo'q")
        return {"Output": self._output}


def test_longest_wait_s_returns_zero_without_callers():
    assert _longest_wait_s(_EMPTY_OUTPUT) == 0


def test_longest_wait_s_parses_minutes_and_seconds():
    assert _longest_wait_s(_ONE_CALLER_OUTPUT) == 11


def test_longest_wait_s_picks_maximum_among_several_callers():
    assert _longest_wait_s(_TWO_CALLERS_OUTPUT) == 65


@pytest.mark.asyncio
async def test_queue_live_status_includes_longest_wait_s():
    result = await queue_live_status(_FakeAmi(_ONE_CALLER_OUTPUT), QUEUE)
    assert result == {"waiting": 1, "members_online": 1, "longest_wait_s": 11}


@pytest.mark.asyncio
async def test_queue_live_status_zero_members_online_when_all_unavailable():
    result = await queue_live_status(_FakeAmi(_EMPTY_OUTPUT), QUEUE)
    assert result == {"waiting": 0, "members_online": 0, "longest_wait_s": 0}


@pytest.mark.asyncio
async def test_queue_live_status_none_when_ami_unreachable():
    assert await queue_live_status(_FakeAmi(None), QUEUE) is None
