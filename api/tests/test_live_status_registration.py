"""`trunk_registration_state` — `pjsip show registration` chiqishini tahlil
qiladi. Namunalar JONLI tasdiqlangan (`innova-m0-asterisk-1` konteyneri,
2026-10-27, `res_pjsip_outbound_registration.so` `strings`: Registered/
Rejected/Unregistered — build-log.md «M1b backend»)."""
from __future__ import annotations

import pytest

from app.services.live_status import trunk_registration_state

ENDPOINT = "t1-trunk-3acc4607-7d28-44a0-bd83-e64568fcc812"

_UNREGISTERED_OUTPUT = (
    " <Registration/ServerURI..............................>  <Auth....................>  <Status.......>\n"
    "==========================================================================================\n\n"
    f" {ENDPOINT}/sip:sipp  {ENDPOINT}  Unregistered      (exp. 3s)\n\n"
    "Objects found: 1\n"
)
_REGISTERED_OUTPUT = _UNREGISTERED_OUTPUT.replace("Unregistered      (exp. 3s)", "Registered        (exp. 3598s)")
_REJECTED_OUTPUT = _UNREGISTERED_OUTPUT.replace("Unregistered      (exp. 3s)", "Rejected          (exp. 0s)")


class _FakeAmi:
    def __init__(self, output: str | None) -> None:
        self._output = output

    async def ensure_connected(self) -> None:
        return None

    async def action(self, action: str, **fields) -> dict:
        if self._output is None:
            raise ConnectionError("AMI yo'q")
        return {"Output": self._output}


@pytest.mark.asyncio
async def test_registered_state_parsed():
    result = await trunk_registration_state(_FakeAmi(_REGISTERED_OUTPUT), ENDPOINT)
    assert result == {"registration": "registered", "reason": None}


@pytest.mark.asyncio
async def test_unregistered_state_parsed():
    result = await trunk_registration_state(_FakeAmi(_UNREGISTERED_OUTPUT), ENDPOINT)
    assert result["registration"] == "unregistered"
    assert result["reason"] is not None


@pytest.mark.asyncio
async def test_rejected_state_parsed():
    result = await trunk_registration_state(_FakeAmi(_REJECTED_OUTPUT), ENDPOINT)
    assert result["registration"] == "rejected"
    assert "Rejected" in result["reason"]


@pytest.mark.asyncio
async def test_object_not_found_returns_null_registration():
    result = await trunk_registration_state(_FakeAmi("Unable to find object t1-trunk-x.\n"), ENDPOINT)
    assert result["registration"] is None


@pytest.mark.asyncio
async def test_ami_unreachable_returns_null_registration_not_error():
    result = await trunk_registration_state(_FakeAmi(None), ENDPOINT)
    assert result["registration"] is None
