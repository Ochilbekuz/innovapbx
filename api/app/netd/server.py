"""Unix-soket server — qator-ajratilgan JSON (m8-network-contract.md bo'lim 1).
Har bir ulanish: bitta qator so'rov o'qiladi, `protocol.dispatch` chaqiriladi,
bitta qator javob yoziladi, ulanish yopiladi (statsiz, oddiy so'rov/javob)."""
from __future__ import annotations

import asyncio
import json
import logging
import os

from app.netd.protocol import dispatch
from app.netd.service import NetdService

logger = logging.getLogger("netd.server")

_MAX_LINE_BYTES = 1 << 20  # 1 MiB — bitta so'rov uchun yetarli va cheklangan
# `StreamReader`ning o'zi sukut bo'yicha 64 KiB limit bilan `\n` topilmasa
# `ValueError` tashlaydi — bu bizning o'z "so'rov juda katta" tekshiruvimizdan
# OLDIN bo'ladi va uni hech qachon ishlatilmay qoladi. Shu sabab limit
# ataylab kattaroq: haqiqiy so'rov (<= _MAX_LINE_BYTES) va biroz oshib ketgan
# so'rov ham to'liq o'qilib, keyin bizning tekshiruv chiroyli xabar bilan
# rad etadi; faqat haddan tashqari katta oqim asosiy `except`ga tushadi.
_READER_LIMIT = _MAX_LINE_BYTES * 2


async def _handle(service: NetdService, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await reader.readline()
        if not raw:
            return
        if len(raw) > _MAX_LINE_BYTES:
            response = {"ok": False, "error": {"code": "bad_request", "message": "So'rov juda katta", "fields": []}}
        else:
            try:
                request = json.loads(raw)
            except json.JSONDecodeError:
                response = {"ok": False, "error": {"code": "bad_request", "message": "Yaroqsiz JSON", "fields": []}}
            else:
                response = await dispatch(service, request)
        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()
    except Exception:  # noqa: BLE001 — bitta mijoz xatosi serverni to'xtatmasin
        logger.exception("netd so'rovini qayta ishlashda xato")
    finally:
        writer.close()


async def serve(service: NetdService, socket_path: str) -> asyncio.AbstractServer:
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    server = await asyncio.start_unix_server(lambda r, w: _handle(service, r, w), path=socket_path,
                                              limit=_READER_LIMIT)
    os.chmod(socket_path, 0o660)
    return server
