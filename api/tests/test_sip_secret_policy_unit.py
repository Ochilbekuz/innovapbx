"""`app/services/sip_secret_policy.py` — foydalanuvchi belgilagan SIP paroli siyosati
(FreePBX-uslubida): uzunlik, ruxsat etilgan belgilar, harf+raqam, raqamni o'z ichiga olmasligi.
Create ham, `PUT /secret` ham SHU BITTA funksiyani chaqiradi (dryer)."""
from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.services.sip_secret_policy import validate_sip_password


def _err(password: str, number: str = "103") -> ApiError:
    with pytest.raises(ApiError) as exc:
        validate_sip_password(password, number)
    return exc.value


def test_valid_password_passes():
    validate_sip_password("Abcd1234", "103")  # ko'tarmasin


@pytest.mark.parametrize("password", ["Ab1", "A1" + "x" * 63])
def test_length_out_of_range_rejected(password):
    err = _err(password)
    assert (err.status_code, err.code, err.field) == (422, "weak_password", "password")


def test_disallowed_character_rejected():
    err = _err("Abcd123$ яой")  # kirill/probel ruxsat etilmagan
    assert (err.status_code, err.code, err.field) == (422, "weak_password", "password")


def test_missing_digit_rejected():
    err = _err("Abcdefgh")
    assert (err.status_code, err.code) == (422, "weak_password")


def test_missing_letter_rejected():
    err = _err("12345678")
    assert (err.status_code, err.code) == (422, "weak_password")


def test_password_equal_to_number_rejected():
    err = _err("103", "103")
    assert (err.status_code, err.code) == (422, "weak_password")


def test_password_containing_number_rejected():
    err = _err("Abc103de", "103")
    assert (err.status_code, err.code) == (422, "weak_password")


def test_allowed_special_characters_pass():
    validate_sip_password("Abcd!@#1", "103")
    validate_sip_password("Abcd^*_+=.,:-1", "103")
