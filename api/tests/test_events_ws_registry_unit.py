"""`EventsWsRegistry` — M10 Bo'lak B3, ulanish registri (xotiradagi holat)."""
from __future__ import annotations

import pytest

from app.services.events_ws_registry import Connection, EventsWsRegistry


class _FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


def _conn(conn_id: str, key_id: str = "k1", tenant_id: str = "t1", subscribed=("*",)) -> Connection:
    return Connection(conn_id=conn_id, key_id=key_id, tenant_id=tenant_id, websocket=_FakeSocket(),
                       subscribed=subscribed)


def test_add_and_remove_tracks_limiter():
    reg = EventsWsRegistry()
    conn = _conn("c1")
    reg.add(conn)
    assert reg.limiter.per_key["k1"] == 1
    assert reg.limiter.per_tenant["t1"] == 1
    reg.remove("c1")
    assert "k1" not in reg.limiter.per_key


def test_can_connect_respects_limiter():
    reg = EventsWsRegistry()
    for i in range(5):
        reg.add(_conn(f"c{i}"))
    assert reg.can_connect("k1", "t1") is False


def test_for_tenant_filters_by_tenant():
    reg = EventsWsRegistry()
    reg.add(_conn("c1", tenant_id="t1"))
    reg.add(_conn("c2", tenant_id="t2"))
    assert [c.conn_id for c in reg.for_tenant("t1")] == ["c1"]


def test_update_subscription_changes_filter():
    reg = EventsWsRegistry()
    reg.add(_conn("c1", subscribed=("*",)))
    reg.update_subscription("c1", ("call.ended",))
    assert reg._connections["c1"].subscribed == ("call.ended",)
    assert reg._connections["c1"].include_internal is False


def test_update_subscription_stores_include_internal():
    reg = EventsWsRegistry()
    reg.add(_conn("c1"))
    reg.update_subscription("c1", ("*",), include_internal=True)
    assert reg._connections["c1"].include_internal is True


@pytest.mark.asyncio
async def test_broadcast_sends_only_to_matching_subscribers():
    reg = EventsWsRegistry()
    reg.add(_conn("c1", subscribed=("call.ended",)))
    reg.add(_conn("c2", subscribed=("call.ringing",)))
    await reg.broadcast("t1", "call.ended", {"type": "event"})
    assert reg._connections["c1"].websocket.sent == [{"type": "event"}]
    assert reg._connections["c2"].websocket.sent == []


@pytest.mark.asyncio
async def test_broadcast_ignores_other_tenants():
    reg = EventsWsRegistry()
    reg.add(_conn("c1", tenant_id="t1"))
    reg.add(_conn("c2", tenant_id="t2"))
    await reg.broadcast("t1", "call.ended", {"type": "event"})
    assert reg._connections["c2"].websocket.sent == []


@pytest.mark.asyncio
async def test_broadcast_withholds_internal_event_by_default():
    reg = EventsWsRegistry()
    reg.add(_conn("c1"))
    await reg.broadcast("t1", "internal.diag", {"type": "event"}, internal=True)
    assert reg._connections["c1"].websocket.sent == []


@pytest.mark.asyncio
async def test_broadcast_delivers_internal_event_when_opted_in():
    reg = EventsWsRegistry()
    reg.add(_conn("c1"))
    reg.update_subscription("c1", ("*",), include_internal=True)
    await reg.broadcast("t1", "internal.diag", {"type": "event"}, internal=True)
    assert reg._connections["c1"].websocket.sent == [{"type": "event"}]
