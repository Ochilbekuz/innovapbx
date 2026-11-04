"""`netd` unix-soket mijozi — API konteyneridan privileged `netd` konteyneriga
(umumiy `netd-sock` volume, m8-network-contract.md bo'lim 1). Protokol
`app/netd/protocol.py` bilan bir xil: bitta qatorli JSON so'rov/javob.

`AmiClient` (`app/services/ami.py`) kabi — har chaqiruv o'z ulanishini ochadi/
yopadi (statsiz, bitta so'rov/javob — doimiy ulanish saqlash shart emas)."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class NetdUnavailableError(Exception):
    """Soket yo'q/ulanmadi/javob bermadi — chaqiruvchi buni `helper.available
    = false` sifatida ko'rsatadi (`ApiError(503, ...)` emas: holat so'rovi
    ham ishlashi kerak)."""


class NetdClient:
    def __init__(self, socket_path: str, *, timeout: float = 10.0) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    async def call(self, op: str, **fields: Any) -> dict[str, Any]:
        payload = {"op": op, **{k: v for k, v in fields.items() if v is not None}}
        try:
            return await asyncio.wait_for(self._request(payload), timeout=self.timeout)
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
        return await self.call("time_apply", config=config)

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
