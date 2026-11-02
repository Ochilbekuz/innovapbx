"""`app/api/v1/calls.py` sof funksiyalari — m7-roles-contract.md §1:
`_require_calls_permission`da `reports:view` admin bilan BIR XIL (hamma
qo'ng'iroqni ko'radi). DB/HTTP yo'q (`cdr_grouping` darajasidagi
`test_calls.py` bilan BIR XIL ruh — faqat ruxsat mantiqi, bu yerda)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1.calls import _build_calls_query, _filter_own_calls, _paginate, _require_calls_permission
from app.core.errors import ApiError
from app.core.permissions import ALL, CALLS_READ_OWN
from app.schemas import CallOut


def _user(permissions: list[str]) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(permissions=permissions))


def _call(src: str, dst: str) -> CallOut:
    return CallOut(uniqueid="1", started_at=datetime(2026, 10, 27, 12, 0, 0), src=src, dst=dst,
                   did=None, direction="in", disposition="answered", duration=10, billsec=5,
                   trunk=None)


# --------------------------------------------------------------- _require_calls_permission
def test_require_calls_permission_admin_sees_all():
    assert _require_calls_permission(_user([ALL])) is True


def test_require_calls_permission_reports_view_sees_all_like_admin():
    assert _require_calls_permission(_user(["reports:view"])) is True


def test_require_calls_permission_reports_edit_sees_all():
    assert _require_calls_permission(_user(["reports:edit"])) is True


def test_require_calls_permission_calls_read_own_is_restricted():
    assert _require_calls_permission(_user([CALLS_READ_OWN])) is False


def test_require_calls_permission_no_permission_raises_403():
    with pytest.raises(ApiError) as exc:
        _require_calls_permission(_user([]))
    assert exc.value.status_code == 403


def test_require_calls_permission_unrelated_region_raises_403():
    with pytest.raises(ApiError) as exc:
        _require_calls_permission(_user(["routing:edit"]))
    assert exc.value.status_code == 403


# --------------------------------------------------------------- _filter_own_calls
def test_filter_own_calls_keeps_matching_src_or_dst():
    calls = [_call("101", "999"), _call("200", "101"), _call("300", "400")]
    result = _filter_own_calls(calls, "101")
    assert [c.src for c in result] == ["101", "200"]


def test_filter_own_calls_empty_when_no_own_number():
    calls = [_call("101", "999")]
    assert _filter_own_calls(calls, None) == []


# --------------------------------------------------------------- _paginate
def test_paginate_slices_and_reports_total():
    calls = [_call(str(i), "1") for i in range(5)]
    result = _paginate(calls, page=2, size=2)
    assert [c.src for c in result["items"]] == ["2", "3"]
    assert result["total"] == 5


def test_paginate_first_page():
    calls = [_call(str(i), "1") for i in range(3)]
    result = _paginate(calls, page=1, size=10)
    assert len(result["items"]) == 3 and result["total"] == 3


# --------------------------------------------------------------- _build_calls_query
def test_build_calls_query_applies_tenant_filter_only_by_default():
    stmt = _build_calls_query("t1", from_=None, to=None, q=None)
    assert stmt.whereclause is not None


def test_build_calls_query_with_search_term_builds_or_clause():
    stmt = _build_calls_query("t1", from_=None, to=None, q="101")
    assert "ILIKE" in str(stmt).upper() or "LIKE" in str(stmt).upper()
