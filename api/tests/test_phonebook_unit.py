"""M9 B2 — `app/api/v1/phonebook.py`: CSV raqam hujayrasi serializatsiyasi va
import qatorini qo'llash (`_import_row`/`_run_import`) — yangilash/skip
semantikasi (kontrakt: `{created, updated, skipped, errors}`)."""
from __future__ import annotations

import pytest

from app.api.v1 import phonebook as pb
from app.db.models import PhonebookContact, PhonebookNumber


# ---------------------------------------------------------------- numbers cell

def test_numbers_cell_roundtrip_with_and_without_label():
    contact = PhonebookContact(name="Ali")
    contact.numbers = [
        PhonebookNumber(number_norm="998901234567", label="ish"),
        PhonebookNumber(number_norm="998907654321", label=None),
    ]
    cell = pb._numbers_cell(contact)
    assert cell == "998901234567:ish;998907654321"

    parsed = pb._parse_numbers_cell(cell)
    assert [n.number_norm for n in parsed] == ["998901234567", "998907654321"]
    assert parsed[0].label == "ish"
    assert parsed[1].label is None


def test_parse_numbers_cell_skips_blank_and_unnormalizable_entries():
    parsed = pb._parse_numbers_cell(";;abc;998901234567:uy;")
    assert [n.number_norm for n in parsed] == ["998901234567"]


# ---------------------------------------------------------------- _import_row

@pytest.mark.asyncio
async def test_import_row_blank_row_is_skipped():
    action, message = await pb._import_row(None, "t1", {"name": "", "numbers": ""}, {})
    assert action == "skipped"
    assert message is None


@pytest.mark.asyncio
async def test_import_row_missing_name_is_error():
    action, message = await pb._import_row(None, "t1", {"numbers": "998901234567"}, {})
    assert action == "error"
    assert "name" in message


class _AddTrackingSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_import_row_creates_new_contact_when_no_match():
    session = _AddTrackingSession()
    existing_by_number: dict = {}
    action, message = await pb._import_row(
        session, "t1", {"name": "Ali", "numbers": "998901234567"}, existing_by_number,
    )
    assert action == "created"
    assert message is None
    assert len(session.added) == 1
    assert "998901234567" in existing_by_number


@pytest.mark.asyncio
async def test_import_row_updates_existing_contact_matched_by_number():
    existing = PhonebookContact(name="Old Name", company=None, note=None)
    existing_by_number = {"998901234567": existing}
    session = _AddTrackingSession()

    action, message = await pb._import_row(
        session, "t1", {"name": "New Name", "company": "Acme", "numbers": "998901234567:uy"},
        existing_by_number,
    )
    assert action == "updated"
    assert session.added == []  # yangi qator qo'shilmagan
    assert existing.name == "New Name"
    assert existing.company == "Acme"
    assert [n.label for n in existing.numbers] == ["uy"]


@pytest.mark.asyncio
async def test_import_row_second_row_with_same_number_updates_not_duplicates():
    """Bir faylda bitta raqam ikki marta kelsa — ikkinchisi birinchisini
    YANGILAYDI (duplikat kontakt yaratilmaydi)."""
    session = _AddTrackingSession()
    existing_by_number: dict = {}
    await pb._import_row(session, "t1", {"name": "Ali", "numbers": "998901234567"}, existing_by_number)
    action, _ = await pb._import_row(
        session, "t1", {"name": "Ali V.", "numbers": "998901234567"}, existing_by_number,
    )
    assert action == "updated"
    assert len(session.added) == 1


# ---------------------------------------------------------------- _run_import

class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeImportSession(_AddTrackingSession):
    def __init__(self):
        super().__init__()
        self.rolled_back = False
        self.flushed = False
        self.committed = False

    async def execute(self, stmt):
        return _FakeResult([])

    async def rollback(self):
        self.rolled_back = True

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_run_import_counts_created_skipped_and_errors():
    session = _FakeImportSession()
    rows = [
        {"name": "Ali", "numbers": "998901234567"},
        {"name": "", "numbers": ""},
        {"numbers": "998900000000"},  # name yo'q -> error
    ]
    result = await pb._run_import(session, "t1", rows, dry_run=False)
    assert result.created == 0
    assert result.skipped == 0
    assert len(result.errors) == 1
    assert session.rolled_back is True  # xato bo'lgani uchun hech narsa yozilmagan


@pytest.mark.asyncio
async def test_run_import_dry_run_rolls_back_after_flush():
    session = _FakeImportSession()
    rows = [{"name": "Ali", "numbers": "998901234567"}]
    result = await pb._run_import(session, "t1", rows, dry_run=True)
    assert result.created == 1
    assert result.errors == []
    assert session.flushed is True
    assert session.rolled_back is True


# ---------------------------------------------------------------- update_contact (handler)

class _FakeUser:
    def __init__(self, tenant_id="t1"):
        self.tenant_id = tenant_id
        self.id = "u1"


class _FakeUpdateSession:
    def __init__(self):
        self.committed = False

    def add(self, obj):
        pass

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_update_contact_applies_payload_and_rebuilds_numbers(monkeypatch):
    from datetime import datetime, timezone

    from app.schemas import PhonebookNumberIn, UpdatePhonebookContactPayload

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    existing = PhonebookContact(id="c1", name="Old", company=None, note=None, updated_at=now)
    existing.numbers = [PhonebookNumber(number_norm="998900000000", label=None)]

    async def fake_get_contact_or_404(session, tenant_id, contact_id):
        return existing

    monkeypatch.setattr(pb, "_get_contact_or_404", fake_get_contact_or_404)

    payload = UpdatePhonebookContactPayload(
        name="New", numbers=[PhonebookNumberIn(number="998901234567", label="uy")], updated_at=now,
    )
    session = _FakeUpdateSession()
    result = await pb.update_contact("c1", payload, session=session, user=_FakeUser())

    assert result.item.name == "New"
    assert [n.number for n in result.item.numbers] == ["998901234567"]
    assert session.committed is True


# ---------------------------------------------------------------- import_contacts_csv (handler)

class _FakeUploadFile:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self, _n):
        return self._data


@pytest.mark.asyncio
async def test_import_contacts_csv_commits_on_success(monkeypatch):
    session = _FakeImportSession()
    csv_bytes = "name,company,note,numbers\nAli,,,998901234567\n".encode("utf-8")

    result = await pb.import_contacts_csv(
        file=_FakeUploadFile(csv_bytes), dry_run=False, session=session, user=_FakeUser(),
    )
    assert result.created == 1
    assert result.errors == []
    assert session.committed is True


@pytest.mark.asyncio
async def test_import_contacts_csv_dry_run_does_not_commit():
    session = _FakeImportSession()
    csv_bytes = "name,company,note,numbers\nAli,,,998901234567\n".encode("utf-8")

    result = await pb.import_contacts_csv(
        file=_FakeUploadFile(csv_bytes), dry_run=True, session=session, user=_FakeUser(),
    )
    assert result.created == 1
    assert session.committed is False


# ---------------------------------------------------------------- export_contacts_csv (handler)

class _FakeExportSession:
    def __init__(self, contacts):
        self._contacts = contacts

    async def execute(self, stmt):
        return self

    def scalars(self):
        return self

    def all(self):
        return self._contacts


@pytest.mark.asyncio
async def test_export_contacts_csv_writes_header_and_rows_with_numbers_cell():
    contact = PhonebookContact(name="Ali", company="Acme", note="eslatma")
    contact.numbers = [PhonebookNumber(number_norm="998901234567", label="ish")]
    session = _FakeExportSession([contact])

    response = await pb.export_contacts_csv(session=session, user=_FakeUser())
    body = response.body.decode("utf-8")
    assert body.splitlines()[0] == "name,company,note,numbers"
    assert "Ali,Acme,eslatma,998901234567:ish" in body
    assert response.media_type == "text/csv"


@pytest.mark.asyncio
async def test_export_contacts_csv_blank_company_and_note_when_absent():
    contact = PhonebookContact(name="Vali", company=None, note=None)
    contact.numbers = []
    session = _FakeExportSession([contact])

    response = await pb.export_contacts_csv(session=session, user=_FakeUser())
    body = response.body.decode("utf-8")
    assert "Vali,,," in body
