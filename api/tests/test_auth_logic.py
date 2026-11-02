"""Login lokaut mantiqi — HAQIQIY admin hisobini bloklamasdan, sof
funksiya/obyekt darajasida sinaladi (DB/HTTP yo'q, yon ta'sirsiz)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.api.v1.auth import _is_locked, _register_failed_login
from app.core.config import settings
from app.db.models import User


def _user(**overrides) -> User:
    user = User(
        tenant_id="00000000-0000-0000-0000-000000000000",
        username="sinov", full_name="Sinov", password_hash="x", role_id="r",
    )
    user.failed_logins = 0
    user.locked_until = None
    for k, v in overrides.items():
        setattr(user, k, v)
    return user


def test_is_locked_false_when_no_lock():
    assert _is_locked(_user()) is False


def test_is_locked_false_when_lock_expired():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert _is_locked(_user(locked_until=past)) is False


def test_is_locked_true_when_lock_in_future():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert _is_locked(_user(locked_until=future)) is True


class _FakeSession:
    """`_register_failed_login` faqat `session.flush()`ni chaqiradi."""

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_register_failed_login_increments_counter():
    user = _user()
    await _register_failed_login(_FakeSession(), user)
    assert user.failed_logins == 1
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_register_failed_login_locks_after_max_attempts():
    user = _user(failed_logins=settings.login_max_attempts - 1)
    before = datetime.now(timezone.utc)
    await _register_failed_login(_FakeSession(), user)
    assert user.failed_logins == settings.login_max_attempts
    assert user.locked_until is not None
    assert user.locked_until > before + timedelta(minutes=settings.login_lock_minutes - 1)
