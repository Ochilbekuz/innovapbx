"""Saqlash muddati — `keep_last` (m4b-contract.md §0/§4 3-band)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.backup_retention import RetentionItem, ids_to_delete

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _items(n: int) -> list[RetentionItem]:
    return [RetentionItem(id=f"b{i}", created_at=NOW - timedelta(days=i)) for i in range(n)]


def test_keeps_newest_n_deletes_rest():
    assert ids_to_delete(_items(5), keep_last=2) == ["b2", "b3", "b4"]


def test_fewer_items_than_keep_last_deletes_nothing():
    assert ids_to_delete(_items(2), keep_last=5) == []


def test_order_independent_of_input_order():
    items = list(reversed(_items(3)))
    assert ids_to_delete(items, keep_last=1) == ["b1", "b2"]


def test_keep_last_must_be_at_least_one():
    with pytest.raises(ValueError):
        ids_to_delete(_items(3), keep_last=0)


def test_empty_items_deletes_nothing():
    assert ids_to_delete([], keep_last=2) == []
