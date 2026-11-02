"""Raqam normalizatsiyasi — BITTA joy (tuzatish a): `forward_always`/`forward_busy`
(`api/v1/extensions.py`) va qora ro'yxat (`services/blacklist.py`) BIR XIL qoidani
ishlatadi. Asterisk dialplan tarafida xuddi shu natijani `FILTER(0-9,...)` beradi
(barcha raqam bo'lmagan belgilar, shu jumladan boshidagi `+`, olib tashlanadi)."""
from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"[^0-9]")


def normalize_number(raw: str) -> str:
    """Bo'shliq/`-`/`()`/`+` va boshqa raqam bo'lmagan belgilarni olib tashlaydi."""
    return _NON_DIGIT.sub("", raw)
