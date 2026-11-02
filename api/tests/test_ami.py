"""`AmiClient.ensure_connected` — konkurent chaqiruvlar (masalan `/dashboard`
ko'p `register` trunk uchun `asyncio.gather`) BITTA haqiqiy `connect()`ga
jamlanishi SHART. Regressiya: jonli konteyner qayta ishga tushganda (AMI
hali ulanmagan holatda) 10+ konkurent `ensure_connected()` chaqiruvi ikkinchi
`connect()`ni boshlab, birinchisining `_reader`/`_writer`ini tiriklayin
almashtirar edi — natijada "AMI ulanmagan"/`_read_loop` assertion xatosi
bilan `/dashboard` 500 qaytargan (2026-10-28, jonli o'lchovda topilgan)."""
from __future__ import annotations

import asyncio

import pytest

from app.services.ami import AmiClient


class _SlowConnectAmi(AmiClient):
    """`connect()`ni chaqirilgan son va bir martalik sun'iy kechikish bilan
    hisoblaydi — haqiqiy socket o'rniga."""

    def __init__(self) -> None:
        super().__init__(host="127.0.0.1", port=5038, username="x", password="y")
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1
        await asyncio.sleep(0.02)
        self._connected.set()


@pytest.mark.asyncio
async def test_ensure_connected_concurrent_calls_connect_only_once():
    ami = _SlowConnectAmi()
    await asyncio.gather(*(ami.ensure_connected() for _ in range(10)))
    assert ami.connect_calls == 1


@pytest.mark.asyncio
async def test_ensure_connected_skips_connect_when_already_connected():
    ami = _SlowConnectAmi()
    await ami.ensure_connected()
    await ami.ensure_connected()
    assert ami.connect_calls == 1


class _ScriptedAmi(AmiClient):
    """`_send()` socket o'rniga oldindan yozilgan javob/hodisalarni shu ActionID bilan qaytaradi."""

    def __init__(self, replies: list[dict]) -> None:
        super().__init__(host="127.0.0.1", port=5038, username="x", password="y", action_timeout=0.5)
        self.replies = replies
        self.sent: list[dict] = []

    async def _send(self, fields: dict) -> None:
        self.sent.append(fields)
        for reply in self.replies:
            self._dispatch({**reply, "ActionID": fields["ActionID"]})


@pytest.mark.asyncio
async def test_action_list_collects_events_until_complete():
    ami = _ScriptedAmi([
        {"Response": "Success", "EventList": "start"},
        {"Event": "ParkedCall", "ParkingSpace": "701"},
        {"Event": "ParkedCall", "ParkingSpace": "702"},
        {"Event": "ParkedCallsComplete", "EventList": "Complete"},
    ])
    events = await ami.action_list("ParkedCalls", ParkingLot="t1-park")
    assert [e["ParkingSpace"] for e in events] == ["701", "702"]
    assert ami.sent[0]["Action"] == "ParkedCalls" and ami.sent[0]["ParkingLot"] == "t1-park"
    assert ami._pending == {}


@pytest.mark.asyncio
async def test_action_list_error_response_raises():
    from app.services.ami import AmiError
    ami = _ScriptedAmi([{"Response": "Error", "Message": "No such lot"}])
    with pytest.raises(AmiError, match="No such lot"):
        await ami.action_list("ParkedCalls")


@pytest.mark.asyncio
async def test_action_list_disconnect_raises():
    from app.services.ami import AmiError
    ami = _ScriptedAmi([{"Response": "Success", "EventList": "start"}])
    original = ami._send

    async def send_then_drop(fields: dict) -> None:
        await original(fields)
        ami._pending[fields["ActionID"]].put_nowait(None)

    ami._send = send_then_drop
    with pytest.raises(AmiError):
        await ami.action_list("ParkedCalls")
