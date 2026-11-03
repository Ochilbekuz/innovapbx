"""`app/services/numbers.py` — umumiy raqam nom maydoni: `extensions.number`,
`dial_numbers` VA ext'siz (umumiy) ovozli pochta qutilarining `mailbox`i bir xil
tekshiruvdan o'tishi kerak (1.0.4 §2 — umumiy quti raqami ext/navbat/guruh/IVR
raqami bilan to'qnashmasin, va teskarisi). DB'siz: soxta sessiya har model uchun
oldindan belgilangan qatorlarni qaytaradi."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.errors import ApiError
from app.db.models import DialNumber, Extension, VoicemailBox
from app.services import numbers as nm

TENANT = "t1"


class _Result:
    def __init__(self, rows: list):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _Session:
    """`rows[Model]` — shu model uchun so'rov qaytaradigan qiymatlar ro'yxati."""

    def __init__(self, rows: dict | None = None):
        self._rows = {Extension: [], DialNumber: [], VoicemailBox: [], **(rows or {})}

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        return _Result(self._rows[entity])

    async def get(self, model, pk):
        """M9 A3: `get_parking_settings` `session.get(ParkingSettings, tenant_id)` chaqiradi —
        yozuv yo'q deb hisoblanadi, sukut (700 lot, 701-720) qiymatlar qaytadi."""
        return None


# ------------------------------------------------------------ number_taken
async def test_number_taken_true_for_extension_match():
    assert await nm.number_taken(_Session({Extension: ["e1"]}), TENANT, "201") is True


async def test_number_taken_true_for_dial_number_match():
    assert await nm.number_taken(_Session({DialNumber: ["target-1"]}), TENANT, "601") is True


async def test_number_taken_true_for_shared_voicemail_mailbox_match():
    """Reverse direction: ext/navbat/... raqami ekki ext'siz ovozli pochta qutisi mailbox'i bilan
    to'qnashsa ham band deb topilishi kerak."""
    assert await nm.number_taken(_Session({VoicemailBox: ["box-1"]}), TENANT, "700") is True


async def test_number_taken_false_when_nothing_matches():
    assert await nm.number_taken(_Session(), TENANT, "999") is False


# ------------------------------------------------------------ ensure_number_free
async def test_ensure_number_free_uses_caller_field_for_mailbox_conflict():
    with pytest.raises(ApiError) as exc:
        await nm.ensure_number_free(_Session({VoicemailBox: ["box-1"]}), TENANT, "700", field="mailbox")
    assert (exc.value.status_code, exc.value.code, exc.value.field) == (409, "number_taken", "mailbox")


async def test_ensure_number_free_defaults_field_to_number():
    with pytest.raises(ApiError) as exc:
        await nm.ensure_number_free(_Session({Extension: ["e1"]}), TENANT, "201")
    assert exc.value.field == "number"


async def test_ensure_number_free_park_number_ignores_field_and_is_reserved():
    with pytest.raises(ApiError) as exc:
        await nm.ensure_number_free(_Session(), TENANT, "700", field="mailbox")
    assert (exc.value.code, exc.value.field, exc.value.details) == ("number_taken", "mailbox", {"reason": "reserved"})


async def test_ensure_number_free_ok_when_nothing_taken():
    await nm.ensure_number_free(_Session(), TENANT, "999")  # ko'tarmaydi


# ------------------------------------------------------------ free_numbers
async def test_free_numbers_excludes_shared_voicemail_mailbox():
    session = _Session({Extension: ["101"], VoicemailBox: ["102"]})
    out = await nm.free_numbers(session, TENANT, from_n=100, to_n=104, limit=10)
    assert out == ["100", "103", "104"]
