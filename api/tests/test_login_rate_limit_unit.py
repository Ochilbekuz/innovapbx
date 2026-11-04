"""M12 C M5 — `/auth/login`: IP limiter, soxta-bcrypt (vaqt-kanal yopiq),
hisob-enumeration yo'qligi — sof funksiya darajasida (`login()`ning DB'ga
tegadigan yordamchilari monkeypatch qilinadi, `test_auth_logic.py`/
`test_setup_code.py` BILAN BIR XIL qolip, HAQIQIY admin hisobiga teginilmaydi).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import auth as auth_module
from app.core.errors import ApiError
from app.db.models import User
from app.schemas import LoginPayload
from app.services.login_guard import guard as login_guard


class _FakeSession:
    async def commit(self) -> None:
        return None


async def _return_none(*_args, **_kwargs) -> None:
    return None


_noop = _return_none


def _request(ip: str = "9.9.9.9") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip))


def _user(**overrides) -> User:
    user = User(
        tenant_id="00000000-0000-0000-0000-000000000000",
        username="sinov", full_name="Sinov",
        password_hash=auth_module.hash_password("togri-parol"), role_id="r",
    )
    user.is_active = True
    user.failed_logins = 0
    user.locked_until = None
    user.totp_enabled_at = None
    for k, v in overrides.items():
        setattr(user, k, v)
    return user


@pytest.fixture(autouse=True)
def _reset_guard():
    login_guard.reset()
    yield
    login_guard.reset()


@pytest.mark.asyncio
async def test_unknown_user_still_runs_bcrypt_with_dummy_hash(monkeypatch):
    """Foydalanuvchi yo'q bo'lsa ham `verify_password` BIR MARTA, soxta hash
    bilan chaqirilishi SHART — aks holda javob vaqtidan login mavjudligini
    bilib olish mumkin (timing side-channel)."""
    seen_hashes: list[str] = []
    real_verify = auth_module.verify_password

    def _spy(password: str, hashed: str) -> bool:
        seen_hashes.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(auth_module, "verify_password", _spy)
    monkeypatch.setattr(auth_module, "_find_user_by_login", _return_none)
    monkeypatch.setattr(auth_module, "_audit_login_failure", _noop)

    with pytest.raises(ApiError) as exc:
        await auth_module.login(
            LoginPayload(login="mavjud-emas", password="har-narsa"), _request(), _FakeSession(),
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "bad_credentials"
    assert seen_hashes == [auth_module._DUMMY_PASSWORD_HASH]


@pytest.mark.asyncio
async def test_locked_account_returns_generic_401_not_423(monkeypatch):
    """Qulflangan hisob — IP hali bloklanmagan bo'lsa — 423 bilan hisob
    holatini OSHKOR qilmaydi, oddiy `bad_credentials` (401) qaytaradi
    (enumeration yopiq)."""
    from datetime import datetime, timedelta, timezone

    locked_user = _user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=5))

    async def _find(_session: object, _login: str) -> User:
        return locked_user

    registered: list[User] = []

    async def _register(_session: object, user: User) -> None:
        registered.append(user)

    monkeypatch.setattr(auth_module, "_find_user_by_login", _find)
    monkeypatch.setattr(auth_module, "_audit_login_failure", _noop)
    monkeypatch.setattr(auth_module, "_register_failed_login", _register)

    with pytest.raises(ApiError) as exc:
        await auth_module.login(
            LoginPayload(login="sinov", password="togri-parol"), _request(), _FakeSession(),
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "bad_credentials"
    # Allaqachon qulflangan hisobni yana-yana qulflash yo'q (DoS'ning oldi
    # hisob darajasida ham olinadi).
    assert registered == []


@pytest.mark.asyncio
async def test_ip_blocked_after_too_many_failures_without_touching_account(monkeypatch):
    """Bir IP limitdan ko'p xato urinsa — keyingi so'rov DBga umuman
    tegmay, 423'ni qaytarishi SHART (IP haqida, hisob haqida emas)."""
    monkeypatch.setattr(auth_module, "_find_user_by_login", _return_none)
    monkeypatch.setattr(auth_module, "_audit_login_failure", _noop)

    ip = "8.8.4.4"
    for _ in range(login_guard.limit):
        with pytest.raises(ApiError) as exc:
            await auth_module.login(
                LoginPayload(login="x", password="y"), _request(ip), _FakeSession(),
            )
        assert exc.value.code == "bad_credentials"

    touched = False

    async def _should_not_run(*_a, **_kw) -> None:
        nonlocal touched
        touched = True

    monkeypatch.setattr(auth_module, "_find_user_by_login", _should_not_run)

    with pytest.raises(ApiError) as exc:
        await auth_module.login(
            LoginPayload(login="x", password="y"), _request(ip), _FakeSession(),
        )
    assert exc.value.status_code == 423
    assert exc.value.code == "locked"
    assert touched is False


@pytest.mark.asyncio
async def test_other_ip_not_affected_by_blocked_ip(monkeypatch):
    monkeypatch.setattr(auth_module, "_find_user_by_login", _return_none)
    monkeypatch.setattr(auth_module, "_audit_login_failure", _noop)

    for _ in range(login_guard.limit):
        with pytest.raises(ApiError):
            await auth_module.login(
                LoginPayload(login="x", password="y"), _request("8.8.4.4"), _FakeSession(),
            )

    with pytest.raises(ApiError) as exc:
        await auth_module.login(
            LoginPayload(login="x", password="y"), _request("1.1.1.1"), _FakeSession(),
        )
    assert exc.value.code == "bad_credentials"
