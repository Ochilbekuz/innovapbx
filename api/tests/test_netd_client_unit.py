"""`app/services/netd_client.py` — unix-soket orqali JSON so'rov/javob.
Haqiqiy `asyncio` unix serveriga ulanadi (vaqtinchalik soket fayli), netd
jarayonining o'zi ishga tushirilmaydi — faqat protokol qatlami tekshiriladi."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.services.netd_client import NetdClient, NetdUnavailableError


async def _echo_server(socket_path: str, response: bytes):
    async def handle(reader, writer):
        await reader.readline()
        writer.write(response)
        await writer.drain()
        writer.close()

    return await asyncio.start_unix_server(handle, path=socket_path)


@pytest.mark.asyncio
async def test_call_round_trips_request_and_response(tmp_path):
    sock = str(tmp_path / "netd.sock")
    reply = json.dumps({"ok": True, "result": {"backend": "ifupdown"}}).encode() + b"\n"
    server = await _echo_server(sock, reply)
    try:
        client = NetdClient(sock, timeout=2.0)
        response = await client.state()
        assert response == {"ok": True, "result": {"backend": "ifupdown"}}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_apply_sends_op_and_fields(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        raw = await reader.readline()
        received.update(json.loads(raw))
        writer.write(json.dumps({"ok": True, "result": {}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        await client.apply({"hostname": "h1"}, request_host="10.0.0.5", meta={"user_id": "u1"})
        assert received == {"op": "apply", "config": {"hostname": "h1"},
                             "request_host": "10.0.0.5", "meta": {"user_id": "u1"}}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_none_fields_are_omitted_from_payload(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        raw = await reader.readline()
        received.update(json.loads(raw))
        writer.write(json.dumps({"ok": True, "result": {}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        await client.confirm("p1")
        assert received == {"op": "confirm", "pending_id": "p1"}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_time_sync_waits_longer_than_default_timeout(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        received.update(json.loads(await reader.readline()))
        await asyncio.sleep(0.3)  # oddiy timeout (0.1) dan uzoq — NTP javobini kutish
        writer.write(json.dumps({"ok": True, "result": {"sync_server": "x"}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        response = await NetdClient(sock, timeout=0.1).time_sync()
        assert received == {"op": "time_sync"}
        assert response["result"] == {"sync_server": "x"}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_time_apply_sends_time_apply_op_and_config(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        raw = await reader.readline()
        received.update(json.loads(raw))
        writer.write(json.dumps({"ok": True, "result": {}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        await client.time_apply({"timezone": "Asia/Tashkent"})
        assert received == {"op": "time_apply", "config": {"timezone": "Asia/Tashkent"}}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_power_execute_sends_power_execute_op_and_action(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        raw = await reader.readline()
        received.update(json.loads(raw))
        writer.write(json.dumps({"ok": True, "result": {}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        await client.power_execute("reboot")
        assert received == {"op": "power_execute", "action": "reboot"}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_firewall_apply_sends_firewall_apply_op_config_and_host(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        raw = await reader.readline()
        received.update(json.loads(raw))
        writer.write(json.dumps({"ok": True, "result": {}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        await client.firewall_apply({"services": []}, request_host="10.0.0.5")
        assert received == {"op": "firewall_apply", "config": {"services": []}, "request_host": "10.0.0.5"}
    finally:
        server.close()


@pytest.mark.asyncio
async def test_missing_socket_raises_unavailable(tmp_path):
    client = NetdClient(str(tmp_path / "missing.sock"), timeout=1.0)
    with pytest.raises(NetdUnavailableError):
        await client.state()


@pytest.mark.asyncio
async def test_timeout_raises_unavailable(tmp_path):
    sock = str(tmp_path / "netd.sock")

    async def handle(reader, writer):
        await reader.readline()
        await asyncio.sleep(10)  # hech qachon javob bermaydi

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=0.05)
        with pytest.raises(NetdUnavailableError):
            await client.state()
    finally:
        server.close()


@pytest.mark.asyncio
async def test_empty_response_raises_unavailable(tmp_path):
    sock = str(tmp_path / "netd.sock")

    async def handle(reader, writer):
        await reader.readline()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        client = NetdClient(sock, timeout=2.0)
        with pytest.raises(NetdUnavailableError):
            await client.state()
    finally:
        server.close()


@pytest.mark.asyncio
async def test_net_ping_sends_host_count_and_waits_for_whole_ping(tmp_path):
    sock = str(tmp_path / "netd.sock")
    received = {}

    async def handle(reader, writer):
        received.update(json.loads(await reader.readline()))
        await asyncio.sleep(0.3)  # oddiy timeout (0.1) dan uzoq — ping count*W s davom etadi
        writer.write(json.dumps({"ok": True, "result": {"ok": True}}).encode() + b"\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    try:
        response = await NetdClient(sock, timeout=0.1).net_ping("1.1.1.1", 1)
        assert received == {"op": "net_ping", "host": "1.1.1.1", "count": 1}
        assert response["result"] == {"ok": True}
    finally:
        server.close()
