"""`app/api/v1/trunks._validate_trunk_mode_fields` — sof funksiya (DB'siz).
m1b-contract.md bo'lim 1: 422 `password_required`/`bad_host`; m0-contract.md
«Trunklar»: `ip` rejim DB `ip_needs_match` cheklovi bilan mos — `match` bo'sh
bo'lsa 422 `bad_match` (avval IntegrityError 409 `name_taken` deb noto'g'ri
belgilanardi — jonli integratsion test bilan topilgan, shu faylda tuzatilgan)."""
from __future__ import annotations

import pytest

from app.api.v1.trunks import _validate_trunk_mode_fields
from app.core.errors import ApiError


def test_blank_host_raises_bad_host():
    with pytest.raises(ApiError) as exc:
        _validate_trunk_mode_fields("ip", "   ", None, None, ["1.2.3.4/32"])
    assert exc.value.code == "bad_host"


def test_register_mode_without_password_raises_password_required():
    with pytest.raises(ApiError) as exc:
        _validate_trunk_mode_fields("register", "sip.example.com", "user1", None)
    assert exc.value.code == "password_required"


def test_register_mode_without_username_raises_password_required():
    with pytest.raises(ApiError) as exc:
        _validate_trunk_mode_fields("register", "sip.example.com", None, "secret")
    assert exc.value.code == "password_required"


def test_register_mode_with_username_and_password_ok():
    _validate_trunk_mode_fields("register", "sip.example.com", "user1", "secret")


def test_ip_mode_with_empty_match_raises_bad_match():
    with pytest.raises(ApiError) as exc:
        _validate_trunk_mode_fields("ip", "198.51.100.5", None, None, [])
    assert exc.value.code == "bad_match"


def test_ip_mode_with_match_ok():
    _validate_trunk_mode_fields("ip", "198.51.100.5", None, None, ["198.51.100.5/32"])


def test_ip_mode_match_not_checked_when_none_not_provided_in_patch():
    """PATCH'da `match` berilmasa (`None`) — ip rejimda ham tekshirilmaydi
    (chaqiruvchi effektiv qiymatni o'zi hisoblab beradi)."""
    _validate_trunk_mode_fields("ip", "198.51.100.5", None, None, None)
