"""`app/api/public_widget.py` — m10-onlinepbx-contract.md §A1 xavfsizlik birligi:

1) toll-fraud: `(00)44...`/`0044...`/`+44...` kabi formatlashtirilgan xalqaro raqamlar
   `international_blocked` tekshiruvidan QOCHIB QUTULMASLIGI (AMI'ga yuboriladigan
   aynan shu raqam ustida tekshiriladi, ikkinchi mustaqil normalizatsiya YO'Q).
2) Origin: `allowed_origins` bo'sh bo'lmaganda Origin sarlavhasi YO'Q so'rov ham
   rad etilishi (avval `if origin and ...` qisqa tutashuv bilan bu holatni
   o'tkazib yuborardi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import public_widget as mod
from app.core.errors import ApiError


def _widget(**kw) -> SimpleNamespace:
    base = dict(allowed_origins=[], allow_international=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _request(origin: str | None) -> SimpleNamespace:
    headers = {} if origin is None else {"origin": origin}
    return SimpleNamespace(headers=headers)


# --------------------------------------------------------------- origin
def test_origin_allowed_when_no_restriction_configured():
    widget = _widget(allowed_origins=[])
    mod._require_allowed_origin(widget, _request(None))  # raise bo'lmasligi -- bu test
    mod._require_allowed_origin(widget, _request("https://anything.example"))


def test_origin_rejected_when_header_missing_but_restriction_configured():
    """Avvalgi bug: hujumchi Origin sarlavhasini shunchaki YUBORMASA
    `allowed_origins` cheklovi butunlay aylanib o'tilardi."""
    widget = _widget(allowed_origins=["https://good.example"])
    with pytest.raises(ApiError) as exc:
        mod._require_allowed_origin(widget, _request(None))
    assert exc.value.status_code == 403 and exc.value.code == "origin_not_allowed"


def test_origin_rejected_when_mismatched():
    widget = _widget(allowed_origins=["https://good.example"])
    with pytest.raises(ApiError) as exc:
        mod._require_allowed_origin(widget, _request("https://evil.example"))
    assert exc.value.status_code == 403


def test_origin_allowed_when_matches():
    widget = _widget(allowed_origins=["https://good.example"])
    mod._require_allowed_origin(widget, _request("https://good.example"))  # raise bo'lmasligi -- bu test


# --------------------------------------------------------------- toll-fraud / xalqaro blok
@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [
    "(00)447911123456",  # qavs tufayli avval "00" bilan boshlanmagandek ko'rinardi
    "0044 7911 123456",
    "+44 7911 123456",
    "+44(79)11-123456",
])
async def test_validated_phone_blocks_international_formatted_variants(raw):
    with pytest.raises(ApiError) as exc:
        await mod._validated_phone(raw, allow_international=False)
    assert exc.value.status_code == 422 and exc.value.code == "international_blocked"


@pytest.mark.asyncio
async def test_validated_phone_allows_uzbekistan_number():
    dialed = await mod._validated_phone("+998 90 123-45-67", allow_international=False)
    assert dialed == "998901234567"


@pytest.mark.asyncio
async def test_validated_phone_allows_international_when_widget_opts_in():
    dialed = await mod._validated_phone("(00)447911123456", allow_international=True)
    assert dialed == "00447911123456"


@pytest.mark.asyncio
async def test_validated_phone_rejects_invalid_characters():
    with pytest.raises(ApiError) as exc:
        await mod._validated_phone("101;rm -rf", allow_international=False)
    assert exc.value.status_code == 422 and exc.value.code == "invalid_number"
