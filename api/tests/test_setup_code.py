"""O'rnatish kodi tekshiruvi (1.0.4) — sof funksiya darajasida (DB/HTTP yo'q,
yon ta'sirsiz) — `test_auth_logic.py` BILAN BIR XIL qolip."""
from __future__ import annotations

import pytest

from app.api.v1.auth import _check_setup_code
from app.core.config import settings
from app.core.errors import ApiError
from app.services.setup_guard import guard as setup_code_guard


@pytest.fixture(autouse=True)
def _reset_guard():
    setup_code_guard.reset()
    yield
    setup_code_guard.reset()


def test_disabled_when_setup_code_empty(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "")
    _check_setup_code("1.2.3.4", None)  # kod o'rnatilmagan bo'lsa — eski server, tekshiruv o'chirilgan


def test_accepts_correct_code(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    _check_setup_code("1.2.3.4", "sinov-kod")


def test_rejects_wrong_code(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    with pytest.raises(ApiError) as exc:
        _check_setup_code("1.2.3.4", "boshqa-kod")
    assert exc.value.status_code == 403
    assert exc.value.code == "invalid_setup_code"


def test_rejects_missing_code(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    with pytest.raises(ApiError) as exc:
        _check_setup_code("1.2.3.4", None)
    assert exc.value.code == "invalid_setup_code"


def test_blocks_ip_after_too_many_failed_attempts(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    for _ in range(setup_code_guard.limit):
        with pytest.raises(ApiError):
            _check_setup_code("9.9.9.9", "notogri")
    with pytest.raises(ApiError) as exc:
        _check_setup_code("9.9.9.9", "sinov-kod")  # bloklangan IP uchun to'g'ri kod ham ishlamaydi
    assert exc.value.status_code == 403
    assert exc.value.code == "rate_limited"


def test_does_not_block_other_ip(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    for _ in range(setup_code_guard.limit):
        with pytest.raises(ApiError):
            _check_setup_code("9.9.9.9", "notogri")
    _check_setup_code("8.8.8.8", "sinov-kod")  # boshqa IP ta'sirlanmaydi


def test_rejects_non_ascii_code_without_crashing(monkeypatch):
    monkeypatch.setattr(settings, "setup_code", "sinov-kod")
    with pytest.raises(ApiError) as exc:
        _check_setup_code("1.2.3.4", "кодкод")  # ilgari compare_digest TypeError -> 500
    assert exc.value.code == "invalid_setup_code"
