"""M9 B1 — `app/services/pin_hmac.py`: HMAC-SHA256 aniq qidirish (bcrypt EMAS)."""
from __future__ import annotations

from app.services.pin_hmac import hash_pin, pin_matches


def test_hash_pin_is_deterministic_for_same_secret_and_pin():
    assert hash_pin("s3cr3t", "1234") == hash_pin("s3cr3t", "1234")


def test_hash_pin_differs_for_different_pin_or_secret():
    assert hash_pin("s3cr3t", "1234") != hash_pin("s3cr3t", "4321")
    assert hash_pin("s3cr3t", "1234") != hash_pin("other", "1234")


def test_pin_matches_true_for_correct_pin():
    digest = hash_pin("s3cr3t", "9876")
    assert pin_matches("s3cr3t", "9876", digest) is True


def test_pin_matches_false_for_wrong_pin_or_secret():
    digest = hash_pin("s3cr3t", "9876")
    assert pin_matches("s3cr3t", "0000", digest) is False
    assert pin_matches("wrong", "9876", digest) is False
