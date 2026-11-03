"""2FA siyosati sof qoidalari — m10-onlinepbx-contract.md Bo'lak B2."""
from __future__ import annotations

from app.services.totp_policy import is_enrollment_exempt_path, must_enroll, requires_totp_challenge


def test_must_enroll_off_never_requires():
    assert must_enroll("off", is_admin=True, totp_enabled=False) is False
    assert must_enroll("off", is_admin=False, totp_enabled=False) is False


def test_must_enroll_admins_only_blocks_admin_without_totp():
    assert must_enroll("admins", is_admin=True, totp_enabled=False) is True
    assert must_enroll("admins", is_admin=False, totp_enabled=False) is False


def test_must_enroll_all_blocks_everyone_without_totp():
    assert must_enroll("all", is_admin=True, totp_enabled=False) is True
    assert must_enroll("all", is_admin=False, totp_enabled=False) is True


def test_must_enroll_never_true_if_already_enabled():
    assert must_enroll("all", is_admin=True, totp_enabled=True) is False
    assert must_enroll("admins", is_admin=True, totp_enabled=True) is False


def test_requires_totp_challenge_mirrors_enabled_flag():
    assert requires_totp_challenge(totp_enabled=True) is True
    assert requires_totp_challenge(totp_enabled=False) is False


def test_enrollment_exempt_paths():
    assert is_enrollment_exempt_path("/auth/login") is True
    assert is_enrollment_exempt_path("/auth/me") is True
    assert is_enrollment_exempt_path("/me/2fa/setup") is True
    assert is_enrollment_exempt_path("/me/2fa/enable") is True


def test_enrollment_non_exempt_paths():
    assert is_enrollment_exempt_path("/me/overview") is False
    assert is_enrollment_exempt_path("/calls") is False
    assert is_enrollment_exempt_path("/users") is False
