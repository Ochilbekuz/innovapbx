"""M9 B4 — `app/services/extension_csv.py`: sof CSV parsing/validatsiya funksiyalari
+ ikki-bosqichli import rejalashtirish (`_plan_row`) va `run_import` (DB — fake
session, `new_extension`/`ensure_number_free` haqiqiy servislar emas — monkeypatch)."""
from __future__ import annotations

import pytest

from app.db.models import Extension
from app.services import extension_csv as ex_csv


# ---------------------------------------------------------------- pure helpers

def test_bool_cell():
    assert ex_csv._bool_cell(True) == "1"
    assert ex_csv._bool_cell(False) == "0"


@pytest.mark.parametrize("raw,expected", [("1", True), ("true", True), ("ha", True),
                                           ("0", False), ("false", False), ("yo'q", False),
                                           ("", None)])
def test_parse_bool_accepted_values(raw, expected):
    if expected is None:
        assert ex_csv._parse_bool(raw, default=True) is True
        assert ex_csv._parse_bool(raw, default=False) is False
    else:
        assert ex_csv._parse_bool(raw, default=not expected) is expected


def test_parse_bool_invalid_raises():
    with pytest.raises(ValueError):
        ex_csv._parse_bool("maybe", default=True)


def test_parse_csv_detects_comma_delimiter():
    rows = ex_csv.parse_csv("number,name\n201,Ali\n")
    assert rows == [{"number": "201", "name": "Ali"}]


def test_parse_csv_detects_semicolon_delimiter():
    rows = ex_csv.parse_csv("number;name\n201;Ali\n")
    assert rows == [{"number": "201", "name": "Ali"}]


def test_rows_to_csv_escapes_formula_injection():
    out = ex_csv.rows_to_csv([["number", "name"], ["201", "=SUM(A1)"]])
    assert "'=SUM(A1)" in out


# ---------------------------------------------------------------- _row_changes

def test_row_changes_maps_known_fields():
    row = {"name": "Ali", "email": "a@x.uz", "outbound_cid": "998901234567",
           "record_in": "always", "record_out": "never", "max_contacts": "3",
           "enabled": "1", "call_waiting": "0"}
    changes = ex_csv._row_changes(row)
    assert changes["name"] == "Ali"
    assert changes["email"] == "a@x.uz"
    assert changes["outbound_callerid"] == "998901234567"
    assert changes["recording"] == "always"
    assert changes["recording_out"] == "never"
    assert changes["max_contacts"] == 3
    assert changes["enabled"] is True
    assert changes["call_waiting"] is False


def test_row_changes_blank_email_becomes_none():
    assert ex_csv._row_changes({"email": ""})["email"] is None


def test_row_changes_invalid_record_in_raises():
    with pytest.raises(ValueError):
        ex_csv._row_changes({"record_in": "sometimes"})


def test_row_changes_invalid_max_contacts_raises():
    with pytest.raises(ValueError):
        ex_csv._row_changes({"max_contacts": "0"})
    with pytest.raises(ValueError):
        ex_csv._row_changes({"max_contacts": "abc"})


# ------------------------------------------- dialplan injection (CONFIRMED HIGH)
# CSV import `app/schemas.py` Pydantic validatsiyasini chetlab o'tadi — shu sabab
# `name`/`outbound_cid` bu yerda ALOHIDA tekshiriladi (`app/services/dialplan_safety.py`).

def test_row_changes_rejects_crlf_in_name():
    with pytest.raises(ValueError):
        ex_csv._row_changes({"name": "Ali\nexten => 999,1,System(rm -rf /)"})


def test_row_changes_rejects_bad_outbound_cid():
    with pytest.raises(ValueError):
        ex_csv._row_changes({"outbound_cid": "${SHELL(id)}"})


# ---------------------------------------------------------------- _plan_row (async, no real DB writes)

@pytest.mark.asyncio
async def test_plan_row_skips_blank_number():
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": ""}, {}, set())
    assert planned.action == "skip"


@pytest.mark.asyncio
async def test_plan_row_rejects_bad_number_format():
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "abc"}, {}, set())
    assert planned.action == "error"
    assert "number" in planned.message


@pytest.mark.asyncio
async def test_plan_row_rejects_duplicate_number_within_batch():
    seen = {"201"}
    planned = await ex_csv._plan_row(None, "t1", 3, {"number": "201", "name": "Ali"}, {}, seen)
    assert planned.action == "error"
    assert "takrorlangan" in planned.message


@pytest.mark.asyncio
async def test_plan_row_propagates_row_changes_value_error_as_row_error():
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "201", "name": "Ali",
                                                       "max_contacts": "0"}, {}, set())
    assert planned.action == "error"
    assert "max_contacts" in planned.message


@pytest.mark.asyncio
async def test_plan_row_new_number_without_name_is_error():
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "201"}, {}, set())
    assert planned.action == "error"
    assert "name" in planned.message


@pytest.mark.asyncio
async def test_plan_row_create_calls_ensure_number_free(monkeypatch):
    called = {}

    async def fake_ensure_number_free(session, tenant_id, number):
        called["number"] = number

    monkeypatch.setattr(ex_csv, "ensure_number_free", fake_ensure_number_free)
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "201", "name": "Ali"}, {}, set())
    assert planned.action == "create"
    assert called["number"] == "201"


@pytest.mark.asyncio
async def test_plan_row_create_surfaces_number_taken_as_row_error(monkeypatch):
    from app.core.errors import ApiError

    async def fake_ensure_number_free(session, tenant_id, number):
        raise ApiError(409, "number_taken", "Bu raqam band", field="number")

    monkeypatch.setattr(ex_csv, "ensure_number_free", fake_ensure_number_free)
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "201", "name": "Ali"}, {}, set())
    assert planned.action == "error"
    assert planned.message == "Bu raqam band"


@pytest.mark.asyncio
async def test_plan_row_update_existing_number():
    existing_ext = Extension(number="202", name="Old")
    planned = await ex_csv._plan_row(None, "t1", 2, {"number": "202", "name": "New"},
                                      {"202": existing_ext}, set())
    assert planned.action == "update"
    assert planned.existing is existing_ext
    assert planned.changes["name"] == "New"


# ---------------------------------------------------------------- run_import (fake session)

class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, existing):
        self._existing = existing
        self.added = []
        self.flushed = False
        self.rolled_back = False

    async def execute(self, stmt):
        return _FakeResult(self._existing)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True

    async def rollback(self):
        self.rolled_back = True


@pytest.fixture
def _patched_creation(monkeypatch):
    monkeypatch.setattr(ex_csv, "generate_sip_secret", lambda: "s3cretPassw0rd12345")

    async def fake_encrypt_secret(session, plaintext):
        return f"enc:{plaintext}"

    async def fake_ensure_number_free(session, tenant_id, number):
        return None

    monkeypatch.setattr(ex_csv, "encrypt_secret", fake_encrypt_secret)
    monkeypatch.setattr(ex_csv, "ensure_number_free", fake_ensure_number_free)


@pytest.mark.asyncio
async def test_run_import_happy_path_create_and_update(_patched_creation):
    existing_ext = Extension(number="202", name="Old")
    session = _FakeSession([existing_ext])
    rows = [
        {"number": "201", "name": "Ali"},
        {"number": "202", "name": "Updated Name"},
    ]
    result, secrets = await ex_csv.run_import(session, "t1", rows, dry_run=False)

    assert result.created == 1
    assert result.updated == 1
    assert result.errors == 0
    assert secrets == {"201": "s3cretPassw0rd12345"}
    assert existing_ext.name == "Updated Name"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_run_import_dry_run_rolls_back_and_hides_secrets(_patched_creation):
    session = _FakeSession([])
    rows = [{"number": "201", "name": "Ali"}]
    result, secrets = await ex_csv.run_import(session, "t1", rows, dry_run=True)

    assert result.created == 1
    assert result.errors == 0
    assert secrets == {}
    assert session.rolled_back is True


@pytest.mark.asyncio
async def test_run_import_any_error_writes_nothing(_patched_creation):
    session = _FakeSession([])
    rows = [
        {"number": "201", "name": "Ali"},
        {"number": "bad-number", "name": "X"},
    ]
    result, secrets = await ex_csv.run_import(session, "t1", rows, dry_run=False)

    assert result.errors == 1
    assert result.created == 0
    assert result.updated == 0
    assert secrets == {}
    assert session.added == []


# ---------------------------------------------------------------- export_rows

class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeExportSession:
    """1-chaqiruv -> Extension ro'yxati, 2-chaqiruv -> (extension_id, language)
    juftlari, 3-chaqiruv -> ovozli pochta qutisi bor extension_id'lar."""

    def __init__(self, exts, language_rows, mailbox_ids):
        self._results = [_ScalarsResult(exts), _RowsResult(language_rows), _ScalarsResult(mailbox_ids)]
        self._n = 0

    async def execute(self, stmt):
        result = self._results[self._n]
        self._n += 1
        return result


@pytest.mark.asyncio
async def test_export_rows_includes_header_and_one_row_per_extension():
    ext = Extension(id="e1", number="201", name="Ali", email="a@x.uz", outbound_callerid="998901234567",
                     recording="always", recording_out="never", max_contacts=2, enabled=True, call_waiting=True)
    session = _FakeExportSession([ext], [("e1", "uz")], ["e1"])

    rows = await ex_csv.export_rows(session, "t1")

    assert rows[0] == list(ex_csv.COLUMNS)
    assert rows[1] == ["201", "Ali", "a@x.uz", "998901234567", "uz", "1", "always", "never", "2", "1", "1"]


@pytest.mark.asyncio
async def test_export_rows_blank_language_and_voicemail_when_absent():
    ext = Extension(id="e2", number="202", name="Vali", email=None, outbound_callerid=None,
                     recording="never", recording_out="never", max_contacts=1, enabled=False, call_waiting=False)
    session = _FakeExportSession([ext], [], [])

    rows = await ex_csv.export_rows(session, "t1")

    assert rows[1] == ["202", "Vali", "", "", "", "0", "never", "never", "1", "0", "0"]
