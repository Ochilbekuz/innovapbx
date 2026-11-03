"""M9 B2 — `app/api/v1/cidsources.py`: handler funksiyalari to'g'ridan-to'g'ri
chaqiriladi (HTTP orqali emas — `tests/test_extensions_create_unit.py`dagi
qolip), fake session/monkeypatch bilan."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.v1 import cidsources as cs
from app.core.errors import ApiError
from app.db.models import CidLookupSource, User
from app.schemas import CidSourceTestPayload, UpdateCidSourcePayload

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeUser:
    def __init__(self, tenant_id="t1"):
        self.tenant_id = tenant_id
        self.id = "u1"


@pytest.mark.asyncio
async def test_test_cid_source_delegates_to_test_lookup(monkeypatch):
    source = CidLookupSource(id="s1", tenant_id="t1", name="src", kind="phonebook", enabled=True,
                              timeout_ms=1500, cache_ttl_s=0)

    async def fake_get_source_or_404(session, tenant_id, source_id):
        assert source_id == "s1"
        return source

    captured = {}

    async def fake_test_lookup(session, tenant_id, src, num):
        captured["num"] = num
        return "Ali Valiyev", 42, None

    monkeypatch.setattr(cs, "_get_source_or_404", fake_get_source_or_404)
    monkeypatch.setattr(cs, "test_lookup", fake_test_lookup)

    result = await cs.test_cid_source("s1", CidSourceTestPayload(number="901234567"),
                                       session=None, user=_FakeUser())
    assert result.name == "Ali Valiyev"
    assert result.ms == 42
    assert result.error is None
    assert captured["num"] == "901234567"


@pytest.mark.asyncio
async def test_apply_cid_source_patch_requires_http_url_when_switching_to_http(monkeypatch):
    source = CidLookupSource(id="s1", tenant_id="t1", name="src", kind="phonebook",
                              http_url=None, timeout_ms=1500, cache_ttl_s=3600, enabled=True)
    payload = UpdateCidSourcePayload(kind="http", updated_at=_NOW)

    with pytest.raises(ApiError) as exc_info:
        await cs._apply_cid_source_patch(source, payload)
    assert exc_info.value.code == "required"


@pytest.mark.asyncio
async def test_apply_cid_source_patch_updates_only_changed_fields():
    source = CidLookupSource(id="s1", tenant_id="t1", name="old", kind="phonebook",
                              timeout_ms=1500, cache_ttl_s=3600, enabled=True)
    payload = UpdateCidSourcePayload(name="new", updated_at=_NOW)

    diff = await cs._apply_cid_source_patch(source, payload)
    assert diff == {"name": "new"}
    assert source.name == "new"
    assert source.kind == "phonebook"


@pytest.mark.asyncio
async def test_delete_cid_source_raises_in_use_when_referenced(monkeypatch):
    source = CidLookupSource(id="s1", tenant_id="t1", name="src", kind="phonebook",
                              timeout_ms=1500, cache_ttl_s=3600, enabled=True)

    async def fake_get_source_or_404(session, tenant_id, source_id):
        return source

    from app.schemas import CidSourceUsageRef

    async def fake_used_by(session, tenant_id, source_id):
        return [CidSourceUsageRef(id="route1", name="Asosiy marshrut")]

    monkeypatch.setattr(cs, "_get_source_or_404", fake_get_source_or_404)
    monkeypatch.setattr(cs, "_used_by", fake_used_by)

    with pytest.raises(ApiError) as exc_info:
        await cs.delete_cid_source("s1", session=None, user=_FakeUser())
    assert exc_info.value.code == "in_use"
