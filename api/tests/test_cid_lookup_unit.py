"""M9 B2 — `app/services/cid_lookup.py`: sof funksiyalar (`sanitize_name`,
`TTLCache`, `_extract_json_path`) + `http`/`phonebook`/`crm` dispetcherlash
(`lookup_name`, `test_lookup`) — tarmoq chaqiruvi `httpx.MockTransport` bilan."""
from __future__ import annotations

import httpx
import pytest

from app.services import cid_lookup
from app.db.models import CidLookupSource


# ---------------------------------------------------------------- sanitize_name

def test_sanitize_name_strips_dangerous_chars_and_truncates():
    raw = 'Ali"Vali;Boy,Qiz\n' + "x" * 50
    out = cid_lookup.sanitize_name(raw)
    assert '"' not in out and ";" not in out and "," not in out and "\n" not in out
    assert len(out) <= 40


def test_sanitize_name_strips_whitespace_edges():
    assert cid_lookup.sanitize_name("  Ali Valiyev  ") == "Ali Valiyev"


# ---------------------------------------------------------------- TTLCache

def test_ttl_cache_hit_and_expiry():
    now = [100.0]
    cache = cid_lookup.TTLCache(clock=lambda: now[0])
    cache.set(("src", "901234567"), "Ali", ttl_s=10)

    hit, value = cache.get(("src", "901234567"))
    assert hit is True
    assert value == "Ali"

    now[0] += 11
    hit, value = cache.get(("src", "901234567"))
    assert hit is False
    assert value is None


def test_ttl_cache_zero_ttl_never_stores():
    cache = cid_lookup.TTLCache()
    cache.set(("src", "901234567"), "Ali", ttl_s=0)
    hit, _ = cache.get(("src", "901234567"))
    assert hit is False


def test_ttl_cache_evicts_oldest_when_over_capacity():
    cache = cid_lookup.TTLCache(max_items=2)
    cache.set(("s", "1"), "a", ttl_s=60)
    cache.set(("s", "2"), "b", ttl_s=60)
    cache.set(("s", "3"), "c", ttl_s=60)
    assert cache.get(("s", "1")) == (False, None)
    assert cache.get(("s", "3")) == (True, "c")


# ---------------------------------------------------------------- _extract_json_path

def test_extract_json_path_dotted_dict_lookup():
    data = {"data": {"name": "Ali"}}
    assert cid_lookup._extract_json_path(data, "data.name") == "Ali"


def test_extract_json_path_list_index():
    data = {"items": [{"name": "Ali"}, {"name": "Vali"}]}
    assert cid_lookup._extract_json_path(data, "items.1.name") == "Vali"


def test_extract_json_path_missing_returns_none():
    assert cid_lookup._extract_json_path({"a": 1}, "b.c") is None
    assert cid_lookup._extract_json_path({"items": [1]}, "items.5") is None


# ---------------------------------------------------------------- http lookup (MockTransport)

def _http_source(**overrides) -> CidLookupSource:
    defaults = dict(
        id="11111111-1111-1111-1111-111111111111", tenant_id="t1", name="src",
        kind="http", http_url="http://example.com/lookup?n={number}",
        http_json_path=None, timeout_ms=1500, cache_ttl_s=0, enabled=True,
    )
    defaults.update(overrides)
    return CidLookupSource(**defaults)


@pytest.mark.asyncio
async def test_lookup_http_detailed_success_with_json_path():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"name": "Ali Valiyev"}})

    source = _http_source(http_json_path="data.name")
    transport = httpx.MockTransport(handler)
    name, error = await cid_lookup._lookup_http_detailed(source, "901234567", transport=transport)
    assert name == "Ali Valiyev"
    assert error is None


@pytest.mark.asyncio
async def test_lookup_http_detailed_non_200_status():
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    source = _http_source()
    name, error = await cid_lookup._lookup_http_detailed(source, "901234567", transport=transport)
    assert name is None
    assert error == "http_500"


@pytest.mark.asyncio
async def test_lookup_http_detailed_not_found_value():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    source = _http_source(http_json_path="data.name")
    name, error = await cid_lookup._lookup_http_detailed(source, "901234567", transport=transport)
    assert name is None
    assert error == "not_found"


@pytest.mark.asyncio
async def test_lookup_http_detailed_no_url_configured():
    source = _http_source(http_url=None)
    name, error = await cid_lookup._lookup_http_detailed(source, "901234567")
    assert name is None
    assert error == "no_url"


@pytest.mark.asyncio
async def test_lookup_http_detailed_forbidden_url_is_ssrf_checked():
    source = _http_source(http_url="http://127.0.0.1/lookup?n={number}")
    name, error = await cid_lookup._lookup_http_detailed(source, "901234567")
    assert name is None
    assert error is not None and error.startswith("forbidden_url:")


# ---------------------------------------------------------------- test_lookup dispatch

class _Row:
    def __init__(self, value):
        self._value = value

    def __getitem__(self, idx):
        return (self._value,)[idx]


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, name: str | None):
        self._name = name

    async def execute(self, stmt):
        return _Result((self._name,) if self._name else None)


@pytest.mark.asyncio
async def test_test_lookup_phonebook_found():
    source = _http_source(kind="phonebook")
    session = _FakeSession("Ali Valiyev")
    name, ms, error = await cid_lookup.test_lookup(session, "t1", source, "901234567")
    assert name == "Ali Valiyev"
    assert error is None
    assert ms >= 0


@pytest.mark.asyncio
async def test_test_lookup_phonebook_not_found():
    source = _http_source(kind="phonebook")
    session = _FakeSession(None)
    name, ms, error = await cid_lookup.test_lookup(session, "t1", source, "901234567")
    assert name is None
    assert error == "not_found"


@pytest.mark.asyncio
async def test_test_lookup_crm_dispatches_to_lookup_crm_found(monkeypatch):
    async def fake_lookup_crm(session, tenant_id, num, *, transport=None):
        return "Ali Valiyev"

    monkeypatch.setattr(cid_lookup, "_lookup_crm", fake_lookup_crm)
    source = _http_source(kind="crm")
    name, ms, error = await cid_lookup.test_lookup(None, "t1", source, "901234567")
    assert name == "Ali Valiyev"
    assert error is None


@pytest.mark.asyncio
async def test_test_lookup_crm_not_found(monkeypatch):
    async def fake_lookup_crm(session, tenant_id, num, *, transport=None):
        return None

    monkeypatch.setattr(cid_lookup, "_lookup_crm", fake_lookup_crm)
    source = _http_source(kind="crm")
    name, ms, error = await cid_lookup.test_lookup(None, "t1", source, "901234567")
    assert name is None
    assert error == "not_found"


@pytest.mark.asyncio
async def test_test_lookup_bypasses_cache_unlike_lookup_name(monkeypatch):
    """`test_lookup` har doim yangi chaqiruv qiladi — `lookup_name` kabi keshdan
    o'qimaydi (contract: jonli sinov doim real natija ko'rsatishi kerak)."""
    calls = {"n": 0}

    async def fake_detailed(source, num, *, transport=None):
        calls["n"] += 1
        return "Ali", None

    monkeypatch.setattr(cid_lookup, "_lookup_http_detailed", fake_detailed)
    source = _http_source(kind="http", cache_ttl_s=3600)

    await cid_lookup.test_lookup(None, "t1", source, "901234567")
    await cid_lookup.test_lookup(None, "t1", source, "901234567")
    assert calls["n"] == 2


# ---------------------------------------------------------------- lookup_name (dispatch)

@pytest.mark.asyncio
async def test_lookup_name_disabled_source_returns_none_without_session():
    source = _http_source(kind="phonebook", enabled=False)
    name = await cid_lookup.lookup_name(None, "t1", source, "901234567")
    assert name is None


@pytest.mark.asyncio
async def test_lookup_name_phonebook_kind_queries_session_and_caches(monkeypatch):
    source = _http_source(kind="phonebook", cache_ttl_s=3600)
    source.id = "src-lookup-name-1"
    session = _FakeSession("Ali Valiyev")
    name = await cid_lookup.lookup_name(session, "t1", source, "901111111")
    assert name == "Ali Valiyev"

    # ikkinchi chaqiruv — keshdan (session butunlay almashtirilsa ham natija bir xil)
    name2 = await cid_lookup.lookup_name(object(), "t1", source, "901111111")
    assert name2 == "Ali Valiyev"


@pytest.mark.asyncio
async def test_lookup_name_http_kind_delegates_to_lookup_http(monkeypatch):
    source = _http_source(kind="http")
    source.id = "src-lookup-name-2"

    async def fake_lookup_http(src, num, *, transport=None):
        return "Http Nom"

    monkeypatch.setattr(cid_lookup, "_lookup_http", fake_lookup_http)
    name = await cid_lookup.lookup_name(None, "t1", source, "901222222")
    assert name == "Http Nom"


@pytest.mark.asyncio
async def test_lookup_name_crm_kind_delegates_to_lookup_crm(monkeypatch):
    source = _http_source(kind="crm")
    source.id = "src-lookup-name-3"

    async def fake_lookup_crm(session, tenant_id, num, *, transport=None):
        return "Crm Nom"

    monkeypatch.setattr(cid_lookup, "_lookup_crm", fake_lookup_crm)
    name = await cid_lookup.lookup_name(None, "t1", source, "901333333")
    assert name == "Crm Nom"


@pytest.mark.asyncio
async def test_lookup_name_unknown_kind_returns_none():
    source = _http_source(kind="mystery")
    source.id = "src-lookup-name-4"
    name = await cid_lookup.lookup_name(None, "t1", source, "901333334")
    assert name is None


# ---------------------------------------------------------------- _lookup_crm (M-CRM §3)

class _DummySub:
    def __init__(self, sub_id="s1", tenant_id="t1", kind="bitrix24"):
        self.id = sub_id
        self.tenant_id = tenant_id
        self.kind = kind


@pytest.mark.asyncio
async def test_lookup_crm_no_enabled_subscription_returns_none(monkeypatch):
    from app.services import crm_route

    async def fake_enabled_subscription(session, tenant_id):
        return None

    monkeypatch.setattr(crm_route, "enabled_subscription", fake_enabled_subscription)
    name = await cid_lookup._lookup_crm(None, "t1", "901234567")
    assert name is None


@pytest.mark.asyncio
async def test_lookup_crm_no_webhook_secret_returns_none(monkeypatch):
    from app.services import crm_route, crm_settings

    async def fake_enabled_subscription(session, tenant_id):
        return _DummySub()

    async def fake_read_secrets(session, sub):
        return {}

    monkeypatch.setattr(crm_route, "enabled_subscription", fake_enabled_subscription)
    monkeypatch.setattr(crm_settings, "read_secrets", fake_read_secrets)
    name = await cid_lookup._lookup_crm(None, "t1", "901234567")
    assert name is None


@pytest.mark.asyncio
async def test_lookup_crm_found_delegates_to_route_for_number(monkeypatch):
    from app.services import crm_route, crm_settings

    async def fake_enabled_subscription(session, tenant_id):
        return _DummySub()

    async def fake_read_secrets(session, sub):
        return {"webhook_url": "https://x.bitrix24.ru/rest/1/abc/"}

    async def fake_route_for_number(session, sub, webhook_url, num, *, transport=None, **kw):
        return crm_route.RouteResult(extension="101", name="Ali Valiyev")

    monkeypatch.setattr(crm_route, "enabled_subscription", fake_enabled_subscription)
    monkeypatch.setattr(crm_settings, "read_secrets", fake_read_secrets)
    monkeypatch.setattr(crm_route, "route_for_number", fake_route_for_number)
    name = await cid_lookup._lookup_crm(None, "t1", "901234567")
    assert name == "Ali Valiyev"
