"""`app/core/config.py`ning `_require` yordamchisi (sir bo'lmasa aniq xato) —
`require_secret_key`/`require_db_key` takrorini yo'qotgan DRY tuzatish uchun
regressiya testi (dryer, ub-mode «Then Make it Right»)."""
from __future__ import annotations

import pytest

from app.core import config as cfg
from app.core.config import Settings, _reject_weak_secret


def test_require_raises_with_env_name_when_empty():
    with pytest.raises(RuntimeError, match="FOO_ENV muhit o'zgaruvchisi berilmagan"):
        Settings._require("", "FOO_ENV")


def test_require_returns_value_when_present():
    assert Settings._require("qiymat", "FOO_ENV") == "qiymat"


def test_require_secret_key_raises_when_blank():
    settings = Settings(secret_key="", innova_db_key="x")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.require_secret_key()


def test_require_db_key_raises_when_blank():
    settings = Settings(secret_key="x", innova_db_key="")
    with pytest.raises(RuntimeError, match="INNOVA_DB_KEY"):
        settings.require_db_key()


# ------------------------------------------------------------------ Item 6b: zaif sir rad etilishi
def test_reject_weak_secret_allows_blank_value():
    """Bo'sh qiymat — sozlanmaganlik, ALOHIDA (`_require`) tekshiriladi, bu yerda EMAS."""
    _reject_weak_secret("", "SECRET_KEY")  # ko'tarmaydi


def test_reject_weak_secret_allows_strong_random_value():
    _reject_weak_secret("YzIbzvPxTpA9OjcT2imUXgV9MAghJksjJJoDKaDKX4LhdL2zz5pEi287OdH4IZk", "SECRET_KEY")


@pytest.mark.parametrize("weak", ["change-me", "CHANGE-ME", "changeme", "secret", "password", "default"])
def test_reject_weak_secret_rejects_known_placeholders(weak):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _reject_weak_secret(weak, "SECRET_KEY")


def test_reject_weak_secret_rejects_too_short_value():
    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        _reject_weak_secret("short-token-16ch", "INTERNAL_API_TOKEN")  # 16 belgi < 32


def test_get_settings_rejects_weak_secret_key_at_startup(monkeypatch):
    """`get_settings()` — HAQIQIY (muhit o'zgaruvchisidan yuklangan) qiymat
    zaif bo'lsa ishga tushishda darhol to'xtaydi. `.env` fayli YO'Q bo'lgani
    uchun muhit o'zgaruvchisi orqali simulyatsiya qilinadi; keyin keshni
    tozalab, boshqa testlarga ta'sir qolmasligi uchun qayta tozalanadi."""
    monkeypatch.setenv("SECRET_KEY", "change-me")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "RlITMaxr9Ia6YID30M6Gpy0dvFqItK2PvGX8u9ZW2es")
    cfg.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            cfg.get_settings()
    finally:
        cfg.get_settings.cache_clear()


def test_get_settings_allows_strong_secrets_at_startup(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "YzIbzvPxTpA9OjcT2imUXgV9MAghJksjJJoDKaDKX4LhdL2zz5pEi287OdH4IZk")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "RlITMaxr9Ia6YID30M6Gpy0dvFqItK2PvGX8u9ZW2es")
    cfg.get_settings.cache_clear()
    try:
        loaded = cfg.get_settings()
        assert loaded.secret_key.startswith("YzIbzvPx")
    finally:
        cfg.get_settings.cache_clear()
