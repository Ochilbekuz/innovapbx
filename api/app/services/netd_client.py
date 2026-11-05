"""`netd` unix-soket mijozi — API konteyneridan privileged `netd` konteyneriga
(umumiy `netd-sock` volume, m8-network-contract.md bo'lim 1). Protokol
`app/netd/protocol.py` bilan bir xil: bitta qatorli JSON so'rov/javob.

`AmiClient` (`app/services/ami.py`) kabi — har chaqiruv o'z ulanishini ochadi/
yopadi (statsiz, bitta so'rov/javob — doimiy ulanish saqlash shart emas)."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from app.netd.ping import ping_timeout_s
from app.netd.systemtime import NTP_ACTIVE_WAIT_SECONDS, SYNC_WAIT_SECONDS


class NetdUnavailableError(Exception):
    """Soket yo'q/ulanmadi/javob bermadi — chaqiruvchi buni `helper.available
    = false` sifatida ko'rsatadi (`ApiError(503, ...)` emas: holat so'rovi
    ham ishlashi kerak)."""


class NetdClient:
    def __init__(self, socket_path: str, *, timeout: float = 10.0) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    async def call(self, op: str, *, timeout_s: float | None = None, **fields: Any) -> dict[str, Any]:
        payload = {"op": op, **{k: v for k, v in fields.items() if v is not None}}
        try:
            return await asyncio.wait_for(self._request(payload), timeout=timeout_s or self.timeout)
        except (TimeoutError, OSError) as exc:
            raise NetdUnavailableError(f"netd bilan aloqa yo'q: {exc}") from exc

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        reader, writer = await asyncio.open_unix_connection(path=self.socket_path)
        try:
            writer.write(json.dumps(payload).encode() + b"\n")
            await writer.drain()
            raw = await reader.readline()
            if not raw:
                raise NetdUnavailableError("netd bo'sh javob qaytardi")
            return json.loads(raw)
        finally:
            writer.close()

    async def state(self) -> dict[str, Any]:
        return await self.call("state")

    async def validate(self, config: dict[str, Any], *, request_host: str | None = None) -> dict[str, Any]:
        return await self.call("validate", config=config, request_host=request_host)

    async def apply(self, config: dict[str, Any], *, request_host: str | None = None,
                     meta: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.call("apply", config=config, request_host=request_host, meta=meta)

    async def confirm(self, pending_id: str) -> dict[str, Any]:
        return await self.call("confirm", pending_id=pending_id)

    async def rollback(self, pending_id: str) -> dict[str, Any]:
        return await self.call("rollback", pending_id=pending_id)

    # ----------------------------------------------------------- M12 B1 (sana/vaqt)
    async def time_state(self) -> dict[str, Any]:
        return await self.call("time_state")

    async def time_apply(self, config: dict[str, Any]) -> dict[str, Any]:
        # NTP yoqilsa netd xizmat ishga tushishini `NTP_ACTIVE_WAIT_SECONDS`gacha kutadi.
        return await self.call("time_apply", config=config, timeout_s=self.timeout + NTP_ACTIVE_WAIT_SECONDS)

    async def time_sync(self) -> dict[str, Any]:
        # netd NTP javobini `SYNC_WAIT_SECONDS`gacha kutadi — mijoz undan uzoqroq kutsin.
        return await self.call("time_sync", timeout_s=self.timeout + SYNC_WAIT_SECONDS)

    # ----------------------------------------------------------- M12 B2 (quvvat)
    async def power_state(self) -> dict[str, Any]:
        return await self.call("power_state")

    async def power_execute(self, action: str) -> dict[str, Any]:
        return await self.call("power_execute", action=action)

    # ----------------------------------------------------------- M12 B3 (firewall)
    async def firewall_state(self) -> dict[str, Any]:
        return await self.call("firewall_state")

    async def firewall_validate(self, config: dict[str, Any], *, request_host: str | None = None) -> dict[str, Any]:
        return await self.call("firewall_validate", config=config, request_host=request_host)

    async def firewall_apply(self, config: dict[str, Any], *, request_host: str | None = None) -> dict[str, Any]:
        return await self.call("firewall_apply", config=config, request_host=request_host)

    async def firewall_confirm(self, pending_id: str) -> dict[str, Any]:
        return await self.call("firewall_confirm", pending_id=pending_id)

    async def firewall_rollback(self, pending_id: str) -> dict[str, Any]:
        return await self.call("firewall_rollback", pending_id=pending_id)

    # ----------------------------------------------------------- kirish (access: SSH/Veb)
    async def access_state(self) -> dict[str, Any]:
        return await self.call("access_state")

    async def access_ssh_apply(self, port: int, *, timeout_s: int | None = None) -> dict[str, Any]:
        return await self.call("access_ssh_apply", port=port, timeout_s=timeout_s)

    async def access_web_apply(self, http_port: int, https_port: int, *, timeout_s: int | None = None) -> dict[str, Any]:
        return await self.call("access_web_apply", http_port=http_port, https_port=https_port, timeout_s=timeout_s)

    async def access_confirm(self, pending_id: str, *, kind: str | None = None) -> dict[str, Any]:
        return await self.call("access_confirm", pending_id=pending_id, kind=kind)

    async def access_rollback(self, pending_id: str) -> dict[str, Any]:
        return await self.call("access_rollback", pending_id=pending_id)

    # ----------------------------------------------------------- diagnostika («Ping» tabi)
    async def net_ping(self, host: str, count: int) -> dict[str, Any]:
        # netd ping'ni `ping_timeout_s(count)`gacha kutadi — mijoz undan uzoqroq kutsin.
        return await self.call("net_ping", host=host, count=count, timeout_s=self.timeout + ping_timeout_s(count))
