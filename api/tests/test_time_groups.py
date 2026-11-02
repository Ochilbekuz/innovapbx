"""`app/api/v1/time_groups.py` — birlik testlari, fake session bilan (DB'siz,
koordinator talabi 2026-10-27): validatsiya (`range_order`), 409 `in_use`."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.v1 import time_groups
from app.core.errors import ApiError
from app.db.models import TimeGroup, User
from app.schemas import TimeRangeIn


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, execute_items=None):
        self._execute_items = execute_items or []
        self.deleted: list = []
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def delete(self, obj) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def execute(self, _stmt):
        return _FakeResult(self._execute_items)


def _user() -> User:
    user = User(tenant_id="00000000-0000-0000-0000-000000000000", username="admin",
                full_name="Admin", password_hash="x", role_id="r")
    user.id = "11111111-1111-1111-1111-111111111111"
    return user


def _group(**overrides) -> TimeGroup:
    group = TimeGroup(tenant_id="t1", name="M1aTG")
    group.id = "tg-1"
    group.updated_at = datetime.now(timezone.utc)
    group.ranges = []
    for k, v in overrides.items():
        setattr(group, k, v)
    return group


# --------------------------------------------------------------- validatsiya
def test_validate_ranges_passes_for_ordered_range():
    time_groups._validate_ranges([TimeRangeIn(weekdays=[1], start="09:00", end="18:00")])


def test_validate_ranges_raises_422_when_end_before_start():
    with pytest.raises(ApiError) as exc:
        time_groups._validate_ranges([TimeRangeIn(weekdays=[1], start="18:00", end="09:00")])
    assert exc.value.status_code == 422
    assert exc.value.code == "range_order"


def test_validate_ranges_raises_422_when_end_equals_start():
    with pytest.raises(ApiError) as exc:
        time_groups._validate_ranges([TimeRangeIn(weekdays=[1], start="09:00", end="09:00")])
    assert exc.value.code == "range_order"


# ------------------------------------------------------------------ 409 in_use
class _FakeTimeCondition:
    def __init__(self, id_: str, name: str) -> None:
        self.id = id_
        self.name = name


async def test_delete_time_group_raises_409_when_in_use(monkeypatch):
    group = _group()
    monkeypatch.setattr(time_groups, "_get_group_or_404", _async(group))
    session = _FakeSession(execute_items=[_FakeTimeCondition("tc-1", "M1aTc1")])

    with pytest.raises(ApiError) as exc:
        await time_groups.delete_time_group("tg-1", session=session, user=_user())
    assert exc.value.status_code == 409
    assert exc.value.code == "in_use"
    assert exc.value.details["usages"][0]["id"] == "tc-1"
    assert session.deleted == []


async def test_delete_time_group_succeeds_when_not_in_use(monkeypatch):
    group = _group()
    monkeypatch.setattr(time_groups, "_get_group_or_404", _async(group))
    session = _FakeSession(execute_items=[])

    await time_groups.delete_time_group("tg-1", session=session, user=_user())
    assert session.deleted == [group]


def _async(value):
    async def _fn(*_args, **_kwargs):
        return value
    return _fn
