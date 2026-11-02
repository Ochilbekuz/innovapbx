"""Asterisk Manager Interface (AMI) mijozi.

Manba: callcenter/backend/app/services/ami.py (sinalgan asinxron AMI mijozi) —
architecture.md: «Jonli hodisalar — AMI (callcenter'dagi mijoz qayta
ishlatiladi)». M0 uchun hodisa oqimi shart emas — faqat action/response
(`DialPlanReload`, `Command`, `PJSIPShowEndpoint`, ...), shu sababli hodisa
filtri va device-status xaritalari olib tashlandi (subtract before add).
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

_CRLF = b"\r\n"
_TERM = b"\r\n\r\n"


class AmiError(Exception):
    pass


class AmiClient:
    """Bitta AMI ulanishi — har `action()` chaqiruvi ulanishni tekshiradi/tiklaydi."""

    def __init__(self, host: str, port: int, username: str, password: str, *,
                 connect_timeout: float = 8.0, action_timeout: float = 15.0,
                 events: str = "off", on_event: Callable[[dict], None] | None = None,
                 event_filters: tuple[str, ...] = ()) -> None:
        """`events`/`on_event` — M3b hodisa ulanishi (`Events: call`): ActionID'siz xabarlar
        `on_event`ga beriladi; u BLOKLAMASLIGI shart (o'qish halqasi kutib qolmasin).
        `event_filters` — login'dan keyin shu sessiyaga `Filter` (oq ro'yxat regex) — Asterisk o'zi saralaydi."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connect_timeout = connect_timeout
        self.action_timeout = action_timeout
        self.events = events
        self.on_event = on_event
        self.event_filters = event_filters

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._write_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Queue] = {}
        self._connected = asyncio.Event()
        self._closing = False
        self.banner: str = ""
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def connect(self) -> None:
        self._closing = False
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.connect_timeout
            )
            banner = await asyncio.wait_for(self._reader.readline(), timeout=self.connect_timeout)
            self.banner = banner.decode("utf-8", "replace").strip()
            self._reader_task = asyncio.create_task(self._read_loop(), name="ami-reader")
            resp = await self.action("Login", Username=self.username, Secret=self.password,
                                     Events=self.events)
            if str(resp.get("Response", "")).lower() != "success":
                raise AmiError(resp.get("Message", "AMI login rad etildi"))
            await self._add_filters()
            self._connected.set()
            self.last_error = None
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)[:300]
            await self._teardown()
            raise

    async def _add_filters(self) -> None:
        for regex in self.event_filters:
            resp = await self.action("Filter", Operation="Add", Filter=regex)
            if str(resp.get("Response", "")).lower() != "success":
                raise AmiError(resp.get("Message", "AMI Filter rad etildi"))

    async def close(self) -> None:
        self._closing = True
        if self._writer is not None and not self._writer.is_closing():
            try:
                await self._send({"Action": "Logoff"})
            except Exception:  # noqa: BLE001, S110
                pass
        await self._teardown()

    async def ensure_connected(self) -> None:
        """Bir xil ulanmagan mijozga KONKURENT chaqiruvlar (masalan `/dashboard`
        ko'p `register` trunk uchun `asyncio.gather` bilan) BITTA `connect()`ga
        jamlanishi SHART — aks holda ikkinchi `connect()` birinchisining
        `_reader`/`_writer`ini tiriklayin almashtirib, "AMI ulanmagan"/
        `_read_loop` assertion xatosi bilan yiqiladi (jonli sinovda topilgan
        haqiqiy race, konteyner qayta ishga tushganda 10+ `register` trunk
        bilan)."""
        if self.connected:
            return
        async with self._connect_lock:
            if not self.connected:
                await self.connect()

    async def _teardown(self) -> None:
        self._connected.clear()
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        self._reader_task = None
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001, S110
                pass
        self._reader = self._writer = None
        for q in list(self._pending.values()):
            q.put_nowait(None)
        self._pending.clear()

    async def _send(self, fields: dict[str, Any]) -> None:
        if self._writer is None:
            raise AmiError("AMI ulanmagan")
        payload = b"".join(
            f"{k}: {v}".encode() + _CRLF for k, v in fields.items() if v is not None
        ) + _CRLF
        async with self._write_lock:
            self._writer.write(payload)
            await self._writer.drain()

    async def action(self, action: str, **fields: Any) -> dict:
        action_id = uuid.uuid4().hex
        queue: asyncio.Queue = asyncio.Queue()
        self._pending[action_id] = queue
        try:
            await self._send({"Action": action, "ActionID": action_id, **fields})
            return await self._next_message(queue)
        finally:
            self._pending.pop(action_id, None)

    async def action_list(self, action: str, **fields: Any) -> list[dict]:
        """Ro'yxat action'i (`ParkedCalls`, ...): birinchi javob, keyin shu
        ActionID'li hodisalar `EventList: Complete` gacha (u kirmaydi)."""
        action_id = uuid.uuid4().hex
        queue: asyncio.Queue = asyncio.Queue()
        self._pending[action_id] = queue
        try:
            await self._send({"Action": action, "ActionID": action_id, **fields})
            first = await self._next_message(queue)
            if str(first.get("Response", "")).lower() != "success":
                raise AmiError(first.get("Message", f"{action} rad etildi"))
            events: list[dict] = []
            while True:
                msg = await self._next_message(queue)
                if str(msg.get("EventList", "")).lower() == "complete":
                    return events
                events.append(msg)
        finally:
            self._pending.pop(action_id, None)

    async def _next_message(self, queue: asyncio.Queue) -> dict:
        msg = await asyncio.wait_for(queue.get(), timeout=self.action_timeout)
        if msg is None:
            raise AmiError("AMI ulanishi uzildi")
        return msg

    async def _read_loop(self) -> None:
        assert self._reader is not None
        buf = b""
        try:
            while True:
                chunk = await self._reader.read(65536)
                if not chunk:
                    raise ConnectionError("AMI ulanishi yopildi")
                buf += chunk
                while _TERM in buf:
                    raw, buf = buf.split(_TERM, 1)
                    msg = _parse_block(raw)
                    if msg:
                        self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)[:300]
            self._connected.clear()
            for q in list(self._pending.values()):
                q.put_nowait(None)

    def _dispatch(self, msg: dict) -> None:
        action_id = msg.get("ActionID")
        if action_id and action_id in self._pending:
            self._pending[action_id].put_nowait(msg)
        elif self.on_event is not None and "Event" in msg:
            self.on_event(msg)


def _parse_block(raw: bytes) -> dict:
    """AMI javobida ba'zi kalitlar takrorlanadi (`Command` action'ning har bir
    chiqish qatori alohida `Output:` header sifatida keladi) — ularni `\\n`
    bilan birlashtiramiz, aks holda faqat oxirgisi qolardi."""
    out: dict[str, str] = {}
    for line in raw.split(_CRLF):
        if not line:
            continue
        text_line = line.decode("utf-8", "replace")
        if ":" not in text_line:
            continue
        key, _, value = text_line.partition(":")
        key = key.strip()
        value = value.strip()
        out[key] = f"{out[key]}\n{value}" if key in out else value
    return out
