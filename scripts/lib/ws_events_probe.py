#!/usr/bin/env python3
"""`m10b-proof.sh` uchun WS mijoz (`WS /api/public/v1/events/ws`) — bash'dan
chaqiriladi, HAR BIR buyruq BITTA ulanish ochadi/yopadi va natijani
JSON/satr qilib stdout'ga chiqaradi (shell $() bilan tutiladi).

Buyruqlar (argv[1]):
  ready URL [TOKEN]       — header bilan (TOKEN bo'lsa) yoki birinchi xabar
                            bilan (TOKEN bo'lmasa, stdin'dan token o'qiladi)
                            ulanadi, "ready" xabarini kutadi, "seq=<N>" chiqaradi.
  closecode URL [TOKEN]   — ulanadi (header bilan, TOKEN bo'sh bo'lsa ham),
                            yopilish kodini chiqaradi ("code=<N>").
  replay URL TOKEN SINCE EVENTS [INCLUDE_INTERNAL]  — header bilan ulanadi,
                            {"type":"subscribe", "events":[...],
                            "since_seq":SINCE, "include_internal":bool
                            (ixtiyoriy, "1"/"true" bo'lsa yoqiladi)} yuboradi,
                            3 soniya ichida kelgan "event" xabarlarini
                            "seq=<N>" qatorlari sifatida chiqaradi.
  live URL TOKEN EVENTS TIMEOUT  — ulanadi, obuna bo'ladi, TIMEOUT soniya
                            ichida mos "event" kutadi, topilsa uni JSON
                            qilib chiqaradi (exit 0), topilmasa exit 1.
  first-msg-send URL TOKEN — header YO'Q, ulangandan keyin BIRINCHI xabar
                            sifatida {"token": TOKEN} yuboradi, "ready"ni
                            kutadi, "seq=<N>" chiqaradi.

`wss://` manzillar uchun sertifikat tekshirilmaydi (mahalliy o'z-imzoli,
`web-nginx.conf`)."""
from __future__ import annotations

import asyncio
import json
import ssl
import sys
import time

import websockets


def _ssl_ctx(url: str):
    if not url.startswith("wss://"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _connect(url: str, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return await websockets.connect(url, additional_headers=headers, ssl=_ssl_ctx(url), open_timeout=10)


async def cmd_ready(url: str, token: str | None) -> int:
    async with await _connect(url, token) as ws:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if msg.get("type") != "ready":
            print(f"error: kutilmagan birinchi xabar: {msg}")
            return 1
        print(f"seq={msg['seq']}")
        return 0


async def cmd_first_msg_send(url: str, token: str) -> int:
    async with websockets.connect(url, ssl=_ssl_ctx(url), open_timeout=10) as ws:
        await ws.send(json.dumps({"token": token}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if msg.get("type") != "ready":
            print(f"error: kutilmagan birinchi xabar: {msg}")
            return 1
        print(f"seq={msg['seq']}")
        return 0


async def cmd_closecode(url: str, token: str | None) -> int:
    try:
        async with await _connect(url, token) as ws:
            await asyncio.wait_for(ws.recv(), timeout=10)
        print("error: kutilgan yopilish bo'lmadi")
        return 1
    except websockets.exceptions.ConnectionClosed as exc:
        print(f"code={exc.code}")
        return 0


async def cmd_replay(url: str, token: str, since_seq: str, events: str, include_internal: str | None = None) -> int:
    async with await _connect(url, token) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)  # ready
        payload = {"type": "subscribe", "events": events.split(","), "since_seq": int(since_seq)}
        if include_internal:
            payload["include_internal"] = include_internal.lower() in ("1", "true")
        await ws.send(json.dumps(payload))
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                if msg.get("type") == "event":
                    print(f"seq={msg['seq']}")
        except (TimeoutError, asyncio.TimeoutError):
            pass
        return 0


async def cmd_live(url: str, token: str, events: str, timeout: str) -> int:
    async with await _connect(url, token) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)  # ready
        await ws.send(json.dumps({"type": "subscribe", "events": events.split(",")}))
        deadline = time.monotonic() + float(timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print("error: timeout")
                return 1
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            except (TimeoutError, asyncio.TimeoutError):
                print("error: timeout")
                return 1
            if msg.get("type") == "event":
                print(json.dumps(msg))
                return 0


async def cmd_limit(url: str, token: str, count: str) -> int:
    """`count` ta ulanishni OCHIQ tutib, (count+1)-chisini sinaydi —
    `MAX_CONNECTIONS_PER_KEY=5` chegarasini jonli tekshirish uchun."""
    held = []
    try:
        for _ in range(int(count)):
            ws = await _connect(url, token)
            await asyncio.wait_for(ws.recv(), timeout=10)  # ready
            held.append(ws)
        try:
            async with await _connect(url, token) as extra:
                await asyncio.wait_for(extra.recv(), timeout=10)
            print("error: kutilgan yopilish bo'lmadi")
            return 1
        except websockets.exceptions.ConnectionClosed as exc:
            print(f"code={exc.code}")
            return 0
    finally:
        for ws in held:
            await ws.close()


_COMMANDS = {
    "ready": (cmd_ready, 2),
    "first-msg-send": (cmd_first_msg_send, 2),
    "closecode": (cmd_closecode, 2),
    "replay": (cmd_replay, 5),
    "live": (cmd_live, 4),
    "limit": (cmd_limit, 3),
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        print(f"foydalanish: {sys.argv[0]} <{'|'.join(_COMMANDS)}> ...", file=sys.stderr)
        return 2
    fn, nargs = _COMMANDS[sys.argv[1]]
    args = sys.argv[2:2 + nargs]
    while len(args) < nargs:
        args.append(None)
    return asyncio.run(fn(*args))


if __name__ == "__main__":
    sys.exit(main())
