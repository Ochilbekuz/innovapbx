"""`app/services/queue_agents.py` — M2b §0/§1. Yagona yozish yo'li: har bitta
funksiya (a) GUC manba belgisini o'rnatadi, (b) `QueueMember` ustunini
yangilaydi. DB/AMI'siz — sof holat o'tishlari + xato yo'llari."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.errors import ApiError
from app.services import queue_agents as qa


class _FakeSession:
    """`set_agent_event_source` faqat `session.execute(text(...), {...})` ni
    chaqiradi — biz shu chaqiruvni ushlaymiz, haqiqiy DB kerak emas."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params=None) -> None:
        self.calls.append((str(stmt), params or {}))


def _member(**kw) -> SimpleNamespace:
    defaults = dict(dynamic=False, logged_in=False, paused=False, pause_reason=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------- GUC manba
@pytest.mark.asyncio
async def test_set_agent_event_source_passes_source_as_bind_param():
    session = _FakeSession()
    await qa.set_agent_event_source(session, "admin")
    assert session.calls[0][1] == {"s": "admin"}
    assert "set_config" in session.calls[0][0]


# ------------------------------------------------------------- login/logout
@pytest.mark.asyncio
async def test_login_member_requires_dynamic():
    session = _FakeSession()
    member = _member(dynamic=False)
    with pytest.raises(ApiError) as exc:
        await qa.login_member(session, member, source="admin")
    assert exc.value.status_code == 409
    assert exc.value.code == "not_dynamic"
    assert member.logged_in is False
    assert session.calls == []  # Xato DB yozuvidan OLDIN ko'tarilishi kerak.


@pytest.mark.asyncio
async def test_login_member_sets_logged_in_true_and_source():
    session = _FakeSession()
    member = _member(dynamic=True, logged_in=False)
    await qa.login_member(session, member, source="admin")
    assert member.logged_in is True
    assert session.calls[0][1] == {"s": "admin"}


@pytest.mark.asyncio
async def test_logout_member_requires_dynamic_and_sets_false():
    session = _FakeSession()
    member = _member(dynamic=True, logged_in=True)
    await qa.logout_member(session, member, source="portal")
    assert member.logged_in is False
    with pytest.raises(ApiError):
        await qa.logout_member(_FakeSession(), _member(dynamic=False), source="portal")


# ------------------------------------------------------------- pause/unpause
@pytest.mark.asyncio
async def test_pause_member_works_on_static_members_too():
    """*46/admin pause — DINAMIK bo'lishi SHART emas (login/logout'dan farqli)."""
    session = _FakeSession()
    member = _member(dynamic=False, paused=False)
    await qa.pause_member(session, member, source="admin", reason="tushlik")
    assert member.paused is True
    assert member.pause_reason == "tushlik"


@pytest.mark.asyncio
async def test_unpause_member_clears_reason():
    session = _FakeSession()
    member = _member(paused=True, pause_reason="tushlik")
    await qa.unpause_member(session, member, source="admin")
    assert member.paused is False
    assert member.pause_reason is None


# ------------------------------------------------------- interface nomlari
def test_queue_interface_builds_pjsip_uri():
    assert qa.queue_interface("t1", "201") == "PJSIP/t1-201"


def test_queue_asterisk_name_builds_tenant_scoped_queue_name():
    assert qa.queue_asterisk_name("t1", "abc-123") == "t1-q-abc-123"


# ------------------------------------------------------------------ nudge
class _FakeAmi:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.actions: list[tuple[str, dict]] = []

    async def ensure_connected(self) -> None:
        if self.fail:
            raise ConnectionError("AMI yo'q")

    async def action(self, action: str, **fields) -> dict:
        self.actions.append((action, fields))
        return {"Response": "Success"}


@pytest.mark.asyncio
async def test_nudge_pause_state_sends_queue_pause_with_scoped_queue():
    ami = _FakeAmi()
    await qa.nudge_pause_state(ami, tenant_code="t1", number="201", queue_id="q1", paused=True, reason="tushlik")
    assert ami.actions == [("QueuePause", {
        "Interface": "PJSIP/t1-201", "Paused": "true", "Queue": "t1-q-q1", "Reason": "tushlik",
    })]


@pytest.mark.asyncio
async def test_nudge_pause_state_swallows_ami_errors_silently():
    """PG allaqachon haqiqiy holatni yozgan — turtki muvaffaqiyatsiz bo'lsa ham
    funksional xato EMAS (m2b-contract.md §0)."""
    ami = _FakeAmi(fail=True)
    await qa.nudge_pause_state(ami, tenant_code="t1", number="201", queue_id="q1", paused=False, reason=None)
