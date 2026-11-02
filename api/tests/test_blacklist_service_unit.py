"""M2a §5: qora ro'yxat raqam validatsiyasi (sof, DB'siz)."""
from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.services.blacklist import validate_blacklist_number


@pytest.mark.parametrize("raw,expected", [
    ("998901112233", "998901112233"),
    ("+998901112233", "998901112233"),
    (" +998 90-111-22-33", "998901112233"),
    ("(998) 90 111 22 33", "998901112233"),
    ("202", "202"),  # 3 ta raqam — min uzunlik
])
def test_valid_numbers_normalized(raw, expected):
    assert validate_blacklist_number(raw) == expected


@pytest.mark.parametrize("raw", ["anonymous", "ANONYMOUS", "restricted", "hidden", "", "   "])
def test_special_values_map_to_anonymous(raw):
    assert validate_blacklist_number(raw) == "anonymous"


@pytest.mark.parametrize("raw", ["1", "12", "abc", "1" * 16])
def test_bad_number_rejected(raw):
    with pytest.raises(ApiError) as e:
        validate_blacklist_number(raw)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_number", "number")


def test_letters_stripped_same_as_dashes():
    """`normalize_number()` — FILTER(0-9,...) bilan BIR XIL, harflarni ham olib
    tashlaydi (forward raqami bilan bitta funksiya — maxsus holat yo'q)."""
    assert validate_blacklist_number("12a34") == "1234"
