"""`app/api/v1/roles.py` — m7-roles-contract.md §2 birlik testlari (DB'siz:
soxta sessiya + monkeypatch, `test_users_unit.py` naqshi bo'yicha)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1 import roles as rr
from app.core.errors import ApiError
from app.schemas_users import CreateRolePayload, UpdateRolePayload

ADMIN = SimpleNamespace(id="admin1", tenant_id="t1")
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


def _role(**kw) -> SimpleNamespace:
    base = dict(id="r1", tenant_id="t1", name="custom", permissions=["routing:edit"],
                is_system=False, updated_at=OLD)
    base.update(kw)
    return SimpleNamespace(**base)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)

    def scalar_one(self):
        return self._rows[0] if self._rows else 0

    def all(self):
        return self._rows


class _Session:
    """`execute_rows` — bitta so'rovli yo'llar uchun (create/update/delete,
    ularda `session.execute` bor-yo'g'i bir marta chaqiriladi). `execute_seq` —
    `list_roles` kabi BIR NECHTA ketma-ket so'rov qiladigan yo'llar uchun
    (har chaqiruv navbatdagi natijani oladi)."""

    def __init__(self, *, execute_rows: list | None = None, execute_seq: list[list] | None = None,
                 flush_error: Exception | None = None):
        self._execute_rows = execute_rows if execute_rows is not None else []
        self._execute_seq = list(execute_seq) if execute_seq is not None else None
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
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = "new-role"
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = NOW

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def execute(self, _stmt):
        if self._execute_seq is not None:
            return _Result(self._execute_seq.pop(0) if self._execute_seq else [])
        return _Result(self._execute_rows)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(rr, "record_audit", fake_audit)
    return rows


@pytest.fixture
def role_lookup(monkeypatch):
    state = {"role": _role()}

    async def fake_get(session, tenant_id, role_id):
        return state["role"]

    monkeypatch.setattr(rr, "_get_role_or_404", fake_get)
    return state


# --------------------------------------------------------------------- list_roles
@pytest.mark.asyncio
async def test_list_roles_orders_system_roles_first():
    rows = [_role(id="c1", name="custom"), _role(id="a1", name="admin", is_system=True),
            _role(id="o1", name="operator", is_system=True)]
    session = _Session(execute_seq=[rows, []])
    out = await rr.list_roles(session=session, user=ADMIN)
    assert [item.name for item in out.items] == ["admin", "operator", "custom"]


@pytest.mark.asyncio
async def test_list_roles_user_count_from_second_query():
    rows = [_role(id="c1", name="custom")]
    session = _Session(execute_seq=[rows, [("c1", 4)]])
    out = await rr.list_roles(session=session, user=ADMIN)
    assert out.items[0].name == "custom"
    assert out.items[0].user_count == 4


# --------------------------------------------------------------------- create_role
@pytest.mark.asyncio
async def test_create_role_success(audit):
    payload = CreateRolePayload(name="Nazoratchi", permissions=["routing:edit", "routing:view"])
    session = _Session()
    out = await rr.create_role(payload, session=session, user=ADMIN)
    assert out.item.name == "Nazoratchi"
    assert out.item.permissions == ["routing:edit"]  # normalize_permissions — view tashlab yuborildi
    assert out.item.user_count == 0
    assert session.commits == 1
    assert audit[0]["action"] == "role.create"


@pytest.mark.asyncio
async def test_create_role_name_taken_rolls_back():
    payload = CreateRolePayload(name="admin", permissions=[])
    session = _Session(flush_error=IntegrityError("dup", {}, Exception()))
    with pytest.raises(ApiError) as exc:
        await rr.create_role(payload, session=session, user=ADMIN)
    assert exc.value.code == "role_name_taken"
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_create_role_unknown_permission_rejected_422():
    payload = CreateRolePayload(name="Custom", permissions=["foo:edit"])
    with pytest.raises(ApiError) as exc:
        await rr.create_role(payload, session=_Session(), user=ADMIN)
    assert exc.value.status_code == 422
    assert exc.value.field == "permissions"


@pytest.mark.asyncio
async def test_create_role_blank_name_rejected_422():
    payload = CreateRolePayload(name="   ", permissions=[])
    with pytest.raises(ApiError) as exc:
        await rr.create_role(payload, session=_Session(), user=ADMIN)
    assert exc.value.status_code == 422
    assert exc.value.field == "name"


# --------------------------------------------------------------------- update_role
@pytest.mark.asyncio
async def test_update_role_success(role_lookup, audit):
    payload = UpdateRolePayload(name="Yangi nom", updated_at=OLD)
    session = _Session(execute_rows=[])
    out = await rr.update_role("r1", payload, session=session, user=ADMIN)
    assert out.item.name == "Yangi nom"
    assert session.commits == 1
    assert audit[0]["diff"] == {"name": "Yangi nom"}


@pytest.mark.asyncio
async def test_update_role_permissions_normalized(role_lookup, audit):
    payload = UpdateRolePayload(permissions=["apps:view", "apps:edit"], updated_at=OLD)
    session = _Session(execute_rows=[])
    out = await rr.update_role("r1", payload, session=session, user=ADMIN)
    assert out.item.permissions == ["apps:edit"]


@pytest.mark.asyncio
async def test_update_role_system_role_blocked(role_lookup):
    role_lookup["role"] = _role(is_system=True, name="admin")
    payload = UpdateRolePayload(name="X", updated_at=OLD)
    with pytest.raises(ApiError) as exc:
        await rr.update_role("r1", payload, session=_Session(), user=ADMIN)
    assert exc.value.code == "system_role"


@pytest.mark.asyncio
async def test_update_role_stale_raises_409(role_lookup):
    payload = UpdateRolePayload(name="X", updated_at=NOW)
    with pytest.raises(ApiError) as exc:
        await rr.update_role("r1", payload, session=_Session(), user=ADMIN)
    assert exc.value.code == "stale"


@pytest.mark.asyncio
async def test_update_role_name_taken_rolls_back(role_lookup):
    payload = UpdateRolePayload(name="operator", updated_at=OLD)
    session = _Session(flush_error=IntegrityError("dup", {}, Exception()))
    with pytest.raises(ApiError) as exc:
        await rr.update_role("r1", payload, session=session, user=ADMIN)
    assert exc.value.code == "role_name_taken"
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_update_role_unknown_permission_rejected_422(role_lookup):
    payload = UpdateRolePayload(permissions=["foo:edit"], updated_at=OLD)
    with pytest.raises(ApiError) as exc:
        await rr.update_role("r1", payload, session=_Session(), user=ADMIN)
    assert exc.value.status_code == 422
    assert exc.value.field == "permissions"


# --------------------------------------------------------------------- delete_role
@pytest.mark.asyncio
async def test_delete_role_success(role_lookup, audit):
    session = _Session(execute_rows=[])
    await rr.delete_role("r1", session=session, user=ADMIN)
    assert session.deletes == 1 and session.commits == 1
    assert audit[0]["action"] == "role.delete"


@pytest.mark.asyncio
async def test_delete_role_system_role_blocked(role_lookup):
    role_lookup["role"] = _role(is_system=True, name="admin")
    with pytest.raises(ApiError) as exc:
        await rr.delete_role("r1", session=_Session(), user=ADMIN)
    assert exc.value.code == "system_role"


@pytest.mark.asyncio
async def test_delete_role_in_use_blocked(role_lookup):
    session = _Session(execute_rows=[3])
    with pytest.raises(ApiError) as exc:
        await rr.delete_role("r1", session=session, user=ADMIN)
    assert exc.value.code == "role_in_use"
    assert exc.value.details == {"user_count": 3}
