"""`app/core/config.py`ning `_require` yordamchisi (sir bo'lmasa aniq xato) —
`require_secret_key`/`require_db_key` takrorini yo'qotgan DRY tuzatish uchun
regressiya testi (dryer, ub-mode «Then Make it Right»)."""
from __future__ import annotations

import pytest

from app.core.config import Settings


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
