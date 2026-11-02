"""`/queues/{id}/members/{extension_id}/*` — M2b §1 YANGI endpointlar
(`update_queue_member`, `login|logout|pause|unpause_queue_member`). DB/AMI'siz
(soxta a'zo + monkeypatch), `test_voicemail_routes_unit.py` namunasi bo'yicha.
To'liq oqim jonli testda (`scripts/m2b-proof.sh`, ssenariy 3)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import queues as qr
from app.core.errors import ApiError
from app.schemas import QueueMemberActionPayload, UpdateQueueMemberPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")


class _Session:
    def __init__(self) -> None:
        self.flushes = self.commits = 0

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


def _member(**kw) -> SimpleNamespace:
    defaults = dict(extension_id="e1", penalty=0, dynamic=False, logged_in=False, paused=False,
                     pause_reason=None, state_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
                     extension=SimpleNamespace(id="e1", number="201", name="Aziz"))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(qr, "record_audit", fake_audit)
    return rows


@pytest.fixture
def member_lookup(monkeypatch):
    """`_get_member_or_404` ikki marta chaqiriladi (yozishdan OLDIN/KEYIN) —
    ikkinchisi yangilangan holatni "qayta o'qiganini" simulyatsiya qiladi."""
    state = {"member": _member()}

    async def fake_get(session, tenant_id, queue_id, extension_id):
        return state["member"]

    monkeypatch.setattr(qr, "_get_member_or_404", fake_get)
    return state


@pytest.fixture
def no_nudge(monkeypatch):
    calls: list = []

    async def fake_nudge(ami, **kw):
        calls.append(kw)

    async def fake_code(session, tenant_id):
        return "t1"

    monkeypatch.setattr(qr, "nudge_pause_state", fake_nudge)
    monkeypatch.setattr(qr, "_tenant_code", fake_code)
    return calls


# ------------------------------------------------------------- update_queue_member
@pytest.mark.asyncio
async def test_update_queue_member_applies_penalty_and_dynamic(audit, member_lookup):
    out = await qr.update_queue_member(
        "q1", "e1", UpdateQueueMemberPayload(penalty=5, dynamic=True), session=_Session(), user=USER,
    )
    assert out.item.penalty == 5 and out.item.dynamic is True
    assert audit[0]["action"] == "queue.update_member"
    assert audit[0]["diff"] == {"penalty": 5, "dynamic": True}


@pytest.mark.asyncio
async def test_update_queue_member_leaves_fields_untouched_when_omitted(audit, member_lookup):
    member_lookup["member"] = _member(penalty=3, dynamic=True)
    out = await qr.update_queue_member(
        "q1", "e1", UpdateQueueMemberPayload(), session=_Session(), user=USER,
    )
    assert out.item.penalty == 3 and out.item.dynamic is True
    assert audit[0]["diff"] == {}


@pytest.mark.asyncio
async def test_get_member_or_404_raises_when_extension_not_in_queue(monkeypatch):
    queue = SimpleNamespace(members=[_member(extension_id="other")])

    async def fake_get_queue(session, tenant_id, queue_id):
        return queue

    monkeypatch.setattr(qr, "_get_queue_or_404", fake_get_queue)
    with pytest.raises(ApiError) as exc:
        await qr._get_member_or_404(_Session(), "t1", "q1", "e1")
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


# ----------------------------------------------------------- login/logout/pause/unpause
@pytest.mark.asyncio
async def test_login_queue_member_delegates_to_login_member_source_admin(audit, member_lookup, monkeypatch):
    seen = {}

    async def fake_login(session, member, *, source):
        seen["source"] = source
        member.logged_in = True

    monkeypatch.setattr(qr, "login_member", fake_login)
    out = await qr.act_on_queue_member("q1", "e1", "login", session=_Session(), user=USER, ami=object())
    assert seen["source"] == "admin"
    assert out.item.logged_in is True
    assert audit[0]["action"] == "queue.login_member"


@pytest.mark.asyncio
async def test_logout_queue_member_delegates_to_logout_member(audit, member_lookup, monkeypatch):
    async def fake_logout(session, member, *, source):
        member.logged_in = False

    monkeypatch.setattr(qr, "logout_member", fake_logout)
    out = await qr.act_on_queue_member("q1", "e1", "logout", session=_Session(), user=USER, ami=object())
    assert out.item.logged_in is False
    assert audit[0]["action"] == "queue.logout_member"


@pytest.mark.asyncio
async def test_pause_queue_member_sets_reason_and_nudges_ami(audit, member_lookup, no_nudge, monkeypatch):
    async def fake_pause(session, member, *, source, reason):
        member.paused = True
        member.pause_reason = reason

    monkeypatch.setattr(qr, "pause_member", fake_pause)
    payload = QueueMemberActionPayload(reason="tushlik")
    out = await qr.act_on_queue_member("q1", "e1", "pause", payload, session=_Session(), user=USER, ami=object())
    assert out.item.paused is True and out.item.pause_reason == "tushlik"
    assert no_nudge == [{"tenant_code": "t1", "number": "201", "queue_id": "q1", "paused": True, "reason": "tushlik"}]
    assert audit[0]["action"] == "queue.pause_member"


@pytest.mark.asyncio
async def test_unpause_queue_member_nudges_with_paused_false(audit, member_lookup, no_nudge, monkeypatch):
    member_lookup["member"] = _member(paused=True, pause_reason="tushlik")

    async def fake_unpause(session, member, *, source):
        member.paused = False
        member.pause_reason = None

    monkeypatch.setattr(qr, "unpause_member", fake_unpause)
    out = await qr.act_on_queue_member("q1", "e1", "unpause", session=_Session(), user=USER, ami=object())
    assert out.item.paused is False and out.item.pause_reason is None
    assert no_nudge[0]["paused"] is False
    assert audit[0]["action"] == "queue.unpause_member"


@pytest.mark.asyncio
async def test_login_action_does_not_nudge_ami(audit, member_lookup, no_nudge, monkeypatch):
    """Login/logout — jonli turtki YO'Q (keyingi `Queue()` kirishida ko'rinadi, §0)."""
    async def fake_login(session, member, *, source):
        member.logged_in = True

    monkeypatch.setattr(qr, "login_member", fake_login)
    await qr.act_on_queue_member("q1", "e1", "login", session=_Session(), user=USER, ami=object())
    assert no_nudge == []
