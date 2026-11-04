"""Qayta yuklash/o'chirish — m12-contract.md B2: `systemctl reboot|poweroff`
FAQAT shu ikki amal (`executor.py::_systemctl_argv_ok`). Hostname-confirm va
faol qo'ng'iroqlar soni API qatlamida (AMI netd'da yo'q) — bu yerda faqat
10 s kechikish bilan rejalashtirilgan ijro."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from app.netd.errors import NetdError
from app.netd.executor import Executor

DELAY_S = 10.0
_ACTIONS = frozenset({"reboot", "poweroff"})

Scheduler = Callable[[float, Callable[[], Awaitable[None]]], None]


def _default_scheduler(delay_s: float, callback: Callable[[], Awaitable[None]]) -> None:
    async def _runner() -> None:
        await asyncio.sleep(delay_s)
        await callback()

    asyncio.create_task(_runner())


class PowerService:
    """`schedule` — testlarda haqiqiy `asyncio.sleep`siz chaqiriqni ushlab
    qolish uchun almashtiriladigan funksiya (ub-mode: sof holatga yaqin,
    vaqtga bog'liq yon ta'sir in'ektsiya orqali test qilinadigan)."""

    def __init__(self, executor: Executor, *, readonly: bool, schedule: Scheduler = _default_scheduler) -> None:
        self.executor = executor
        self.readonly = readonly
        self._schedule = schedule

    async def state(self) -> dict[str, Any]:
        return {"readonly_reason": self._readonly_reason()}

    def _readonly_reason(self) -> str | None:
        if self.readonly:
            return "Bu serverda qayta yuklash/o'chirish o'chirilgan (NETD_READONLY)"
        return None

    async def execute(self, action: str) -> dict[str, Any]:
        if self.readonly:
            # `self.readonly` True bo'lganda `_readonly_reason()` doim xabar qaytaradi
            # (hech qachon falsy emas) — o'likcha fallback yo'q, mutator buni aniqladi.
            raise NetdError("readonly", self._readonly_reason())
        if action not in _ACTIONS:
            raise NetdError("invalid_config", f"Noma'lum amal: {action!r}",
                             [{"field": "action", "message": "reboot yoki poweroff bo'lishi kerak"}])

        async def _apply() -> None:
            await self.executor.run(["systemctl", action], timeout=5.0)

        self._schedule(DELAY_S, _apply)
        return {"action": action, "delay_s": DELAY_S, "scheduled": True}
