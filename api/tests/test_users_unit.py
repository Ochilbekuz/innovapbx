"""`app/api/v1/users.py` — m2b-contract.md §3 birlik testlari (DB'siz: soxta
sessiya + monkeypatch, `test_extensions_call_fields_unit.py`/
`test_queue_members_routes_unit.py` namunasi bo'yicha). To'liq oqim jonli
testda (`scripts/m2b-proof.sh`, ssenariy 1/8)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1 import users as ur
from app.core.errors import ApiError
from app.schemas_users import CreateUserPayload, UpdateUserPayload

ADMIN = SimpleNamespace(id="admin1", tenant_id="t1", tenant=SimpleNamespace(language="uz"))
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def first(self):
        return (self._rows[0],) if self._rows else None


class _Session:
    def __init__(self, *, execute_rows: list | None = None, flush_error: Exception | None = None):
        self._execute_rows = execute_rows if execute_rows is not None else []
        self._flush_error = flush_error
        self.added: list = []
        self.flushes = self.commits = self.rollbacks = self.deletes = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def delete(self, obj) -> None:
        self.deletes += 1

    async def flush(self) -> None:
        self.flushes += 1
        if self._flush_error is not None:
            raise self._flush_error
        # Haqiqiy `AsyncSession.flush()` ustun sukutlarini (`default=True`,
        # `server_default=now()`) INSERT'dan keyin obyektga to'ldiradi — soxta
        # sessiya hech narsa qilmagani uchun shu yerda simulyatsiya qilinadi.
        for obj in self.added:
            if getattr(obj, "is_active", False) is None:
                obj.is_active = True
            if getattr(obj, "must_change_password", False) is None:
                obj.must_change_password = True
            if getattr(obj, "updated_at", False) is None:
                obj.updated_at = NOW

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def execute(self, _stmt):
        return _Result(self._execute_rows)


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(id=f"r-{name}", name=name)


def _user(**kw) -> SimpleNamespace:
    base = dict(id="u1", tenant_id="t1", username="aziz", full_name="Aziz", email=None,
                role=_role("operator"), extension=None, extension_id=None, is_active=True,
                language="uz", must_change_password=False, last_login_at=None, updated_at=OLD,
                tenant=SimpleNamespace(language="uz"), totp_enabled_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------- _check_self_lockout
def test_self_lockout_blocks_deactivating_self():
    target = _user(id="admin1", role=_role("admin"))
    with pytest.raises(ApiError) as exc:
        ur._check_self_lockout(ADMIN, target, next_is_active=False, next_role="admin")
    assert exc.value.code == "self_lockout"


def test_self_lockout_blocks_role_downgrade_of_self():
    target = _user(id="admin1", role=_role("admin"))
    with pytest.raises(ApiError) as exc:
        ur._check_self_lockout(ADMIN, target, next_is_active=True, next_role="operator")
    assert exc.value.code == "self_lockout"


def test_self_lockout_allows_changes_to_other_user():
    target = _user(id="other", role=_role("admin"))
    ur._check_self_lockout(ADMIN, target, next_is_active=False, next_role="operator")  # ko'tarmaydi


# --------------------------------------------------------- _check_last_admin
@pytest.mark.asyncio
async def test_last_admin_blocks_when_no_other_active_admin():
    target = _user(role=_role("admin"))
    with pytest.raises(ApiError) as exc:
        await ur._check_last_admin(_Session(execute_rows=[]), "t1", target, next_is_active=False, next_role="admin")
    assert exc.value.code == "last_admin"


@pytest.mark.asyncio
async def test_last_admin_allows_when_another_admin_exists():
    target = _user(role=_role("admin"))
    await ur._check_last_admin(_Session(execute_rows=["other-id"]), "t1", target, next_is_active=False, next_role="admin")


@pytest.mark.asyncio
async def test_last_admin_ignored_for_operator():
    target = _user(role=_role("operator"))
    await ur._check_last_admin(_Session(execute_rows=[]), "t1", target, next_is_active=False, next_role="operator")


# ------------------------------------------------------- _ensure_extension_free
@pytest.mark.asyncio
async def test_ensure_extension_free_allows_when_unused():
    ext = SimpleNamespace(id="e1", number="101")
    await ur._ensure_extension_free(_Session(execute_rows=[]), "t1", ext)


@pytest.mark.asyncio
async def test_ensure_extension_free_blocks_when_taken():
    ext = SimpleNamespace(id="e1", number="101")
    other = SimpleNamespace(username="bob")
    with pytest.raises(ApiError) as exc:
        await ur._ensure_extension_free(_Session(execute_rows=[other]), "t1", ext)
    assert exc.value.code == "extension_taken"
    assert exc.value.details == {"username": "bob"}


@pytest.mark.asyncio
async def test_ensure_extension_free_passes_exclude_user_id_through():
    ext = SimpleNamespace(id="e1", number="101")
    # Soxta sessiya `stmt`ni e'tiborsiz qoldiradi — shu yerda faqat chaqiruv
    # xatosiz o'tishi (exclude_user_id argumenti qabul qilinishi) tekshiriladi.
    await ur._ensure_extension_free(_Session(execute_rows=[]), "t1", ext, exclude_user_id="u1")


# --------------------------------------------------------------- create_user
@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(ur, "record_audit", fake_audit)
    return rows


@pytest.fixture
def no_revoke(monkeypatch):
    calls: list = []

    async def fake_revoke(session, user_id):
        calls.append(user_id)

    monkeypatch.setattr(ur, "revoke_refresh_tokens", fake_revoke)
    return calls


@pytest.mark.asyncio
async def test_create_user_success(audit, monkeypatch):
    async def fake_role_for(session, tenant_id, name):
        return _role(name)

    monkeypatch.setattr(ur, "_role_for", fake_role_for)
    payload = CreateUserPayload(username="vali", full_name="Vali", role="operator", password="StrongPass123")
    session = _Session()
    out = await ur.create_user(payload, session=session, user=ADMIN)
    assert out.item.username == "vali" and out.item.role == "operator"
    assert session.commits == 1
    assert audit[0]["action"] == "user.create"
    assert audit[0]["diff"]["password"] == "StrongPass123"  # record_audit o'zi maskalaydi (bu yerda soxta)


@pytest.mark.asyncio
async def test_create_user_weak_password_rejected(monkeypatch):
    payload = CreateUserPayload(username="vali", full_name="Vali", role="operator", password="123")
    with pytest.raises(ApiError) as exc:
        await ur.create_user(payload, session=_Session(), user=ADMIN)
    assert exc.value.code == "weak_password"


@pytest.mark.asyncio
async def test_create_user_username_taken(monkeypatch):
    async def fake_role_for(session, tenant_id, name):
        return _role(name)

    monkeypatch.setattr(ur, "_role_for", fake_role_for)
    payload = CreateUserPayload(username="vali", full_name="Vali", role="operator", password="StrongPass123")
    session = _Session(flush_error=IntegrityError("dup", {}, Exception()))
    with pytest.raises(ApiError) as exc:
        await ur.create_user(payload, session=session, user=ADMIN)
    assert exc.value.code == "username_taken"
    assert session.rollbacks == 1


# ------------------------------------------------- update_user yordamchilari
def test_apply_identity_fields_tracks_username_fullname_email_language():
    target = _user(username="aziz", full_name="Aziz", email=None, language="uz")
    payload = UpdateUserPayload(username="vali", full_name="Vali", email="v@example.com",
                                 language="ru", updated_at=OLD)
    diff = ur._apply_identity_fields(target, payload, payload.model_fields_set)
    assert diff == {"username": "vali", "full_name": "Vali", "email": "v@example.com", "language": "ru"}
    assert target.username == "vali" and target.email == "v@example.com"


def test_apply_identity_fields_empty_when_unchanged():
    target = _user(username="aziz", full_name="Aziz")
    payload = UpdateUserPayload(updated_at=OLD)
    assert ur._apply_identity_fields(target, payload, payload.model_fields_set) == {}


def test_apply_active_toggles_is_active():
    target = _user(is_active=True)
    payload = UpdateUserPayload(is_active=False, updated_at=OLD)
    diff = ur._apply_active(target, payload)
    assert diff == {"is_active": False} and target.is_active is False


@pytest.mark.asyncio
async def test_apply_extension_clears_when_null(monkeypatch):
    target = _user(extension_id="e1", extension=_ext_sentinel())
    payload = UpdateUserPayload(extension_id=None, updated_at=OLD)
    diff = await ur._apply_extension(_Session(), "t1", target, payload, payload.model_fields_set)
    assert diff == {"extension_id": None} and target.extension is None


@pytest.mark.asyncio
async def test_apply_extension_noop_when_not_given():
    target = _user(extension_id=None, extension=None)
    payload = UpdateUserPayload(updated_at=OLD)
    diff = await ur._apply_extension(_Session(), "t1", target, payload, payload.model_fields_set)
    assert diff == {}


def _ext_sentinel() -> SimpleNamespace:
    return SimpleNamespace(id="e1", number="101")


# --------------------------------------------------------------- update_user
@pytest.fixture
def user_lookup(monkeypatch):
    state = {"target": _user()}

    async def fake_get(session, tenant_id, user_id):
        return state["target"]

    monkeypatch.setattr(ur, "_get_user_or_404", fake_get)
    return state


@pytest.mark.asyncio
async def test_update_user_role_change_revokes_tokens(user_lookup, audit, no_revoke, monkeypatch):
    async def fake_role_for(session, tenant_id, name):
        return _role(name)

    monkeypatch.setattr(ur, "_role_for", fake_role_for)
    payload = UpdateUserPayload(role="admin", updated_at=OLD)
    out = await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert out.item.role == "admin"
    assert no_revoke == ["u1"]
    assert audit[0]["diff"] == {"role": "admin"}


@pytest.mark.asyncio
async def test_update_user_password_change_sets_must_change_password(user_lookup, audit, no_revoke):
    payload = UpdateUserPayload(password="AnotherStrongPass1", updated_at=OLD)
    out = await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert out.item.must_change_password is True
    assert no_revoke == ["u1"]
    assert audit[0]["diff"]["password"] == "AnotherStrongPass1"


@pytest.mark.asyncio
async def test_update_user_deactivate_revokes_tokens(user_lookup, audit, no_revoke):
    payload = UpdateUserPayload(is_active=False, updated_at=OLD)
    out = await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert out.item.is_active is False
    assert no_revoke == ["u1"]


@pytest.mark.asyncio
async def test_update_user_simple_rename_does_not_revoke(user_lookup, audit, no_revoke):
    payload = UpdateUserPayload(full_name="Yangi Ism", updated_at=OLD)
    await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert no_revoke == []


@pytest.mark.asyncio
async def test_update_user_stale_raises_409(user_lookup):
    payload = UpdateUserPayload(full_name="X", updated_at=NOW)
    with pytest.raises(ApiError) as exc:
        await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert exc.value.code == "stale"


@pytest.mark.asyncio
async def test_update_user_self_lockout_blocks_before_any_write(user_lookup, no_revoke):
    user_lookup["target"] = _user(id="admin1", role=_role("admin"))
    payload = UpdateUserPayload(is_active=False, updated_at=OLD)
    with pytest.raises(ApiError) as exc:
        await ur.update_user("u1", payload, session=_Session(), user=ADMIN)
    assert exc.value.code == "self_lockout"
    assert no_revoke == []


# --------------------------------------------------------------- delete_user
@pytest.mark.asyncio
async def test_delete_user_revokes_tokens_and_deletes(user_lookup, audit, no_revoke):
    session = _Session()
    await ur.delete_user("u1", session=session, user=ADMIN)
    assert session.deletes == 1 and session.commits == 1
    assert no_revoke == ["u1"]
    assert audit[0]["action"] == "user.delete"


@pytest.mark.asyncio
async def test_delete_user_last_admin_blocks(monkeypatch):
    async def fake_get(session, tenant_id, user_id):
        return _user(id="admin1", role=_role("admin"))

    monkeypatch.setattr(ur, "_get_user_or_404", fake_get)
    with pytest.raises(ApiError) as exc:
        await ur.delete_user("admin1", session=_Session(execute_rows=[]), user=SimpleNamespace(id="other", tenant_id="t1"))
    assert exc.value.code == "last_admin"
