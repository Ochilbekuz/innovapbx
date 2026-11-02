"""M2a §4/§5 + tuzatish (a): raqam normalizatsiyasi — bitta funksiya,
`forward_always`/`forward_busy` (extensions.py) va qora ro'yxat (blacklist.py)
BIR XIL qoidani ishlatadi: bo'shliq/`-`/`()` olib tashlanadi, boshidagi `+` ham
(Asterisk dialplan `FILTER(0-9,...)` bilan bir xil natija)."""
from __future__ import annotations

import pytest

from app.services.number_normalize import normalize_number


@pytest.mark.parametrize("raw,expected", [
    ("998901112233", "998901112233"),
    ("+998901112233", "998901112233"),
    (" +998 90 111 22 33", "998901112233"),
    ("+998-90-111-22-33", "998901112233"),
    ("(998) 90-111-22-33", "998901112233"),
    ("202", "202"),
])
def test_normalize_strips_plus_space_dash_parens(raw, expected):
    assert normalize_number(raw) == expected


def test_normalize_empty_returns_empty():
    assert normalize_number("") == ""
    assert normalize_number("   ") == ""
