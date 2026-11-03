"""M9 — qo'ng'iroqlar tarixining kengaytirilgan qidiruvi (`app/services/cdr_search.py`)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.schemas import CallOut
from app.services.cdr_grouping import clid_name
from app.services.cdr_search import TextMatch, build_search, call_matches, calls_csv, filter_calls


def _call(**kw) -> CallOut:
    base = dict(uniqueid="u1", started_at=datetime(2026, 11, 3, 5, 0, tzinfo=timezone.utc), src="201",
                dst="998901234567", did=None, direction="out", disposition="answered", duration=65,
                billsec=60, trunk="Uztelecom", src_name="Ali Valiyev", pin_label="Sotuv", linkedid="u1")
    return CallOut(**{**base, **kw})


@pytest.mark.parametrize(("mode", "value", "expected"), [
    ("contains", "1234", True), ("contains", "9999", False),
    ("begins", "99890", True), ("begins", "90", False),
    ("ends", "567", True), ("ends", "998", False),
    ("exact", "998901234567", True), ("exact", "99890123456", False),
])
def test_text_match_modes(mode, value, expected):
    assert TextMatch(value, mode)("998901234567") is expected


def test_text_match_negate_and_case_insensitive():
    assert TextMatch("ALI", "contains")("ali valiyev") is True
    assert TextMatch("201", "exact", negate=True)("201") is False
    assert TextMatch("201", "exact", negate=True)(None) is True


def test_empty_search_matches_everything():
    assert call_matches(build_search(), _call()) is True


def test_src_dst_did_filters():
    call = _call(direction="in", did="712000000")
    assert call_matches(build_search(src="20", src_mode="begins"), call)
    assert not call_matches(build_search(src="201", src_mode="exact", src_not=True), call)
    assert call_matches(build_search(dst="4567", dst_mode="ends"), call)
    assert call_matches(build_search(did="712"), call)
    assert not call_matches(build_search(did="713"), _call())


def test_name_ext_trunk_account():
    call = _call()
    assert call_matches(build_search(name="vali"), call)
    assert not call_matches(build_search(name="Karim"), call)
    assert call_matches(build_search(ext="201"), call)
    assert not call_matches(build_search(ext="20"), call)
    assert call_matches(build_search(trunk="uztelecom"), call)
    assert not call_matches(build_search(trunk="Uz"), call)
    assert call_matches(build_search(account="sot"), call)
    assert not call_matches(build_search(account="sot"), _call(pin_label=None))


def test_disposition_and_duration():
    assert call_matches(build_search(disposition="answered,busy"), _call())
    assert not call_matches(build_search(disposition="no_answer"), _call())
    assert call_matches(build_search(min_duration=65, max_duration=65), _call())
    assert not call_matches(build_search(min_duration=66), _call())
    assert not call_matches(build_search(max_duration=64), _call())


def test_recording_filter():
    with_rec = _call(recordings=[{"id": "r1", "duration_s": 10}])
    assert build_search(recording="with").needs_recordings
    assert not build_search().needs_recordings
    assert filter_calls(build_search(recording="with"), [with_rec, _call(uniqueid="u2")]) == [with_rec]
    assert [c.uniqueid for c in filter_calls(build_search(recording="without"), [with_rec, _call(uniqueid="u2")])] == ["u2"]


@pytest.mark.parametrize(("kwargs", "field"), [
    ({"src": "1", "src_mode": "like"}, "src_mode"),
    ({"disposition": "answered,lost"}, "disposition"),
    ({"recording": "maybe"}, "recording"),
    ({"min_duration": -1}, "min_duration"),
    ({"min_duration": 10, "max_duration": 5}, "max_duration"),
])
def test_validation_errors_name_the_field(kwargs, field):
    with pytest.raises(ApiError) as exc:
        build_search(**kwargs)
    assert exc.value.status_code == 422
    assert exc.value.field == field


def test_blank_values_are_ignored():
    search = build_search(src="  ", name="", ext=" ", src_mode="like")
    assert search.src is None and search.name is None and search.ext is None


@pytest.mark.parametrize(("clid", "expected"), [
    ('"Ali Valiyev" <201>', "Ali Valiyev"), ("Ali <201>", "Ali"), ('"201" <201>', None),
    ('"+998901234567" <+998901234567>', None), ("201", None), (None, None), ('"" <201>', None),
])
def test_clid_name(clid, expected):
    assert clid_name(clid) == expected


def test_calls_csv_local_time_header_and_formula_guard():
    text = calls_csv([_call(src_name="=HYPERLINK(\"x\")", recordings=[{"id": "r1", "duration_s": 3}])])
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0][:3] == ["started_at", "direction", "src"]
    assert rows[1][0] == "2026-11-03 10:00:00"
    assert rows[1][3] == "'=HYPERLINK(\"x\")"
    assert rows[1][10] == "Sotuv" and rows[1][11] == "1"
