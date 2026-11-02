"""`DELETE /extensions/{id}` — ichki raqam IVR tugmasi, vaqt sharti, navbat timeout'i va h.k. manzili
bo'lsa 409 `in_use` (ilgari faqat kiruvchi marshrut tekshirilardi → IVR'dagi raqam 500 FK xatosi)."""
from __future__ import annotations

import pytest

from app.api.v1 import extensions
from app.core.errors import ApiError
from app.db.models import Extension, User

TENANT = "00000000-0000-0000-0000-000000000000"


def _async(value):
    async def _f(*_a, **_k):
        return value
    return _f


def _user() -> User:
    user = User(tenant_id=TENANT, username="admin", full_name="Admin", password_hash="x", role_id="r")
    user.id = "11111111-1111-1111-1111-111111111111"
    return user


@pytest.mark.parametrize("usage", [
    {"kind": "ivr_option", "id": "ivr-1", "label": "Asosiy menyu", "field": "digit:1"},
    {"kind": "inbound_route", "id": "r1", "label": "712099301", "field": "target"},
])
async def test_delete_extension_raises_409_for_any_target_usage(monkeypatch, usage):
    ext = Extension(tenant_id=TENANT, target_id="target-102", number="102", name="Ali")
    seen: list = []

    async def fake_usages(_session, tenant_id, target_id):
        seen.append((tenant_id, target_id))
        return [usage]

    monkeypatch.setattr(extensions, "_get_extension_or_404", _async(ext))
    monkeypatch.setattr(extensions, "usages_for_target", fake_usages)
    with pytest.raises(ApiError) as exc:
        await extensions.delete_extension("ext-1", session=None, user=_user(), ami=None)
    assert (exc.value.status_code, exc.value.code) == (409, "in_use")
    assert exc.value.details == {"usages": [usage]}
    assert seen == [(TENANT, "target-102")]
