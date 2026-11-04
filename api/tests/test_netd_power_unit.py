"""`app/netd/power.py` — m12-contract.md B2 (qayta yuklash/o'chirish).
`_schedule` inyeksiya qilinadi — HAQIQIY `asyncio.sleep`/`systemctl` HECH
QACHON chaqirilmaydi (2026-11-04 insident: avvalgi test server'ni 4 marta
qayta yukladi — bu test shunga qarshi himoya)."""
from __future__ import annotations

from typing import Awaitable, Callable

import pytest

from app.netd.executor import CommandResult
from app.netd.power import DELAY_S, PowerService
from app.netd.service import NetdError


class FakeExecutor:
    def __init__(self):
        self.commands: list[list[str]] = []

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        return CommandResult(0, "", "")


class CapturingScheduler:
    """Haqiqiy `asyncio.sleep`/`create_task` ISHLATMAYDI — chaqiriqni shunchaki
    ushlab qoladi, test uni qo'lda keyinroq `run()` qiladi."""

    def __init__(self):
        self.calls: list[tuple[float, Callable[[], Awaitable[None]]]] = []

    def __call__(self, delay_s: float, callback: Callable[[], Awaitable[None]]) -> None:
        self.calls.append((delay_s, callback))


@pytest.mark.asyncio
async def test_state_reports_no_readonly_reason_when_writable():
    state = await PowerService(FakeExecutor(), readonly=False).state()
    assert state == {"readonly_reason": None}


@pytest.mark.asyncio
async def test_state_reports_readonly_reason_when_readonly():
    state = await PowerService(FakeExecutor(), readonly=True).state()
    assert state["readonly_reason"]


@pytest.mark.asyncio
async def test_execute_readonly_raises_without_scheduling():
    scheduler = CapturingScheduler()
    service = PowerService(FakeExecutor(), readonly=True, schedule=scheduler)
    with pytest.raises(NetdError) as exc:
        await service.execute("reboot")
    assert exc.value.code == "readonly"
    assert scheduler.calls == []


@pytest.mark.asyncio
async def test_execute_rejects_unknown_action():
    scheduler = CapturingScheduler()
    service = PowerService(FakeExecutor(), readonly=False, schedule=scheduler)
    with pytest.raises(NetdError) as exc:
        await service.execute("shutdown -h now")
    assert exc.value.code == "invalid_config"
    assert scheduler.calls == []


@pytest.mark.parametrize("action", ["reboot", "poweroff"])
@pytest.mark.asyncio
async def test_execute_schedules_systemctl_call_with_delay_but_does_not_run_it_yet(action):
    executor = FakeExecutor()
    scheduler = CapturingScheduler()
    service = PowerService(executor, readonly=False, schedule=scheduler)
    result = await service.execute(action)
    assert result == {"action": action, "delay_s": DELAY_S, "scheduled": True}
    assert executor.commands == []  # hali bajarilmadi — faqat rejalashtirildi
    assert len(scheduler.calls) == 1
    assert scheduler.calls[0][0] == DELAY_S


@pytest.mark.asyncio
async def test_scheduled_callback_runs_systemctl_with_exact_action_argv():
    executor = FakeExecutor()
    scheduler = CapturingScheduler()
    service = PowerService(executor, readonly=False, schedule=scheduler)
    await service.execute("poweroff")
    _, callback = scheduler.calls[0]
    await callback()  # test o'zi, deterministik ravishda, keyin ishga tushiradi
    assert executor.commands == [["systemctl", "poweroff"]]
