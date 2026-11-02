"""Chiquvchi marshrutlar (`/outbound-routes`) — jonli `innova-m0` stack'iga
qarshi black-box testlar (m1b-contract.md bo'lim 2). Stack ishlamasa butun
modul `skip` qilinadi (test_integration_live.py bilan bir xil naqsh)."""
from __future__ import annotations

import os
import random
import re
import uuid
from pathlib import Path

import httpx
import pytest

BASE = "http://127.0.0.1:8710/api/v1"
INTERNAL_BASE = "http://127.0.0.1:8710"
ADMIN_LOGIN = "admin"


def _proof_password() -> str:
    if os.environ.get("PROOF_ADMIN_PASSWORD"):
        return os.environ["PROOF_ADMIN_PASSWORD"]
    env = Path(__file__).resolve().parents[2] / "deploy" / ".env"
    m = re.search(r"^PROOF_ADMIN_PASSWORD=(.+)$", env.read_text(), re.M) if env.exists() else None
    return m.group(1).strip() if m else ""


def _internal_token() -> str:
    """`INTERNAL_API_TOKEN` — `deploy/.env`da (kodda sir yo'q)."""
    if os.environ.get("INTERNAL_API_TOKEN"):
        return os.environ["INTERNAL_API_TOKEN"]
    env = Path(__file__).resolve().parents[2] / "deploy" / ".env"
    m = re.search(r"^INTERNAL_API_TOKEN=(.+)$", env.read_text(), re.M) if env.exists() else None
    return m.group(1).strip() if m else ""


ADMIN_PASSWORD = _proof_password()
INTERNAL_TOKEN = _internal_token()


def _stack_available() -> bool:
    try:
        r = httpx.get(f"{INTERNAL_BASE}/healthz", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_available(), reason="innova-m0 stack 127.0.0.1:8710'da ishlab turmagan"
)


@pytest.fixture(scope="module")
def token() -> str:
    r = httpx.post(f"{BASE}/auth/login", json={"login": ADMIN_LOGIN, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access"]


@pytest.fixture()
def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _cleanup_created_routes(auth: dict):
    """Har bir test o'zi yaratgan marshrutlarni testdan keyin o'chiradi —
    boshqa test fayllari (masalan `test_integration_live.py`dagi qo'ng'iroq
    guruhi 422 `no_outbound_route` testi) BILAN BIR XIL jonli DB'ni
    ishlatadi (umumiy, transaksiyasiz); keng naqshli marshrut qolib ketsa
    boshqa testning tashqi raqamiga TASODIFAN mos kelib, uni buzishi mumkin
    (jonli sinovda aynan shu kollizion topilgan edi)."""
    before = {i["id"] for i in httpx.get(f"{BASE}/outbound-routes", headers=auth).json()["items"]}
    yield
    after = httpx.get(f"{BASE}/outbound-routes", headers=auth).json()["items"]
    for item in after:
        if item["id"] not in before:
            httpx.delete(f"{BASE}/outbound-routes/{item['id']}", headers=auth)


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


def _random_number() -> str:
    return "9" + str(random.randint(0, 99999)).zfill(5)


@pytest.fixture()
def trunk_id(auth: dict) -> str:
    name = "pytest-ortrunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "198.51.100.20", "match": ["198.51.100.20/32"],
    })
    assert r.status_code == 201, r.text
    return r.json()["item"]["id"]


def _create_route(auth: dict, trunk_id: str, **overrides) -> dict:
    payload = {
        "name": "pytest-route-" + _short_id(),
        "patterns": [{"pattern": "9XXXXXXXXX", "strip_prefix": "", "add_prefix": ""}],
        "trunk_ids": [trunk_id],
    }
    payload.update(overrides)
    r = httpx.post(f"{BASE}/outbound-routes", headers=auth, json=payload)
    return r


def test_create_route_assigns_next_priority(auth: dict, trunk_id: str):
    r1 = _create_route(auth, trunk_id)
    assert r1.status_code == 201, r1.text
    body1 = r1.json()["item"]
    r2 = _create_route(auth, trunk_id)
    body2 = r2.json()["item"]
    assert body2["priority"] == body1["priority"] + 1
    assert body1["has_pin"] is False
    assert body1["extensions"] == "all"


def test_create_route_with_explicit_priority_shifts_others(auth: dict, trunk_id: str):
    r1 = _create_route(auth, trunk_id)
    first_priority = r1.json()["item"]["priority"]
    r2 = _create_route(auth, trunk_id, priority=first_priority)
    assert r2.status_code == 201, r2.text
    assert r2.json()["item"]["priority"] == first_priority

    refreshed = httpx.get(f"{BASE}/outbound-routes", headers=auth).json()["items"]
    by_id = {item["id"]: item["priority"] for item in refreshed}
    assert by_id[r1.json()["item"]["id"]] == first_priority + 1
    assert by_id[r2.json()["item"]["id"]] == first_priority


def test_create_route_with_bad_pattern_returns_422(auth: dict, trunk_id: str):
    r = _create_route(auth, trunk_id, patterns=[{"pattern": "9X.5", "strip_prefix": "", "add_prefix": ""}])
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "bad_pattern"
    assert err["details"]["index"] == 0


def test_create_route_with_invalid_trunk_returns_422(auth: dict):
    r = httpx.post(f"{BASE}/outbound-routes", headers=auth, json={
        "name": "pytest-route-" + _short_id(),
        "patterns": [{"pattern": "9XXXXXXXXX"}],
        "trunk_ids": ["00000000-0000-0000-0000-000000000000"],
    })
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "invalid_target"
    assert r.json()["error"]["field"] == "trunk_ids"


def test_create_route_with_invalid_extension_returns_422(auth: dict, trunk_id: str):
    r = _create_route(auth, trunk_id, extension_ids=["00000000-0000-0000-0000-000000000000"])
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "invalid_target"
    assert r.json()["error"]["field"] == "extension_ids"


def test_update_route_patch_fields(auth: dict, trunk_id: str):
    created = _create_route(auth, trunk_id).json()["item"]
    r = httpx.patch(f"{BASE}/outbound-routes/{created['id']}", headers=auth, json={
        "name": "renamed-" + _short_id(), "enabled": False, "updated_at": created["updated_at"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["item"]["enabled"] is False


def test_update_route_with_stale_updated_at_returns_409(auth: dict, trunk_id: str):
    created = _create_route(auth, trunk_id).json()["item"]
    r = httpx.patch(f"{BASE}/outbound-routes/{created['id']}", headers=auth,
                     json={"enabled": False, "updated_at": "2000-01-01T00:00:00Z"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "stale"


def test_pin_set_and_cleared_never_leaks_plaintext(auth: dict, trunk_id: str):
    created = _create_route(auth, trunk_id, pin="123456").json()["item"]
    assert created["has_pin"] is True
    fetched = httpx.get(f"{BASE}/outbound-routes", headers=auth).json()["items"]
    item = next(i for i in fetched if i["id"] == created["id"])
    assert "pin" not in item and "pin_hash" not in item

    cleared = httpx.patch(f"{BASE}/outbound-routes/{created['id']}", headers=auth,
                           json={"pin_clear": True, "updated_at": created["updated_at"]})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["item"]["has_pin"] is False


def test_delete_route_succeeds(auth: dict, trunk_id: str):
    created = _create_route(auth, trunk_id).json()["item"]
    r = httpx.delete(f"{BASE}/outbound-routes/{created['id']}", headers=auth)
    assert r.status_code == 204


def test_reorder_requires_exact_permutation(auth: dict, trunk_id: str):
    a = _create_route(auth, trunk_id).json()["item"]
    b = _create_route(auth, trunk_id).json()["item"]
    r = httpx.put(f"{BASE}/outbound-routes/order", headers=auth, json={"ids": [a["id"]]})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "invalid_target"


def test_reorder_swaps_priorities(auth: dict, trunk_id: str):
    a = _create_route(auth, trunk_id).json()["item"]
    b = _create_route(auth, trunk_id).json()["item"]
    all_ids = [item["id"] for item in httpx.get(f"{BASE}/outbound-routes", headers=auth).json()["items"]]
    swapped = [i for i in all_ids if i not in (a["id"], b["id"])] + [b["id"], a["id"]]
    r = httpx.put(f"{BASE}/outbound-routes/order", headers=auth, json={"ids": swapped})
    assert r.status_code == 200, r.text
    items = {item["id"]: item["priority"] for item in r.json()["items"]}
    assert items[b["id"]] < items[a["id"]]


def test_simulate_matches_route_and_strips_prefix(auth: dict, trunk_id: str):
    number = _random_number()
    httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "sim-ext"})
    # DIQQAT: naqsh STRIP QILINGANDAN KEYINGI raqamga qarshi tekshiriladi
    # (m1b-contract.md misoli: number="0901234567", strip_prefix="0" -> "901234567",
    # naqsh shu "901234567"ga mos kelishi kerak, ASL "0901234567"ga EMAS) —
    # `outbound_rules.match_number_against_route`/`compiler._route_pattern_lines`
    # ikkisi ham shu tartibda (avval strip, keyin mos kelish).
    # Naqsh LITERAL (wildcard'siz) — boshqa test fayllaridagi tasodifiy
    # tashqi raqamlarga (masalan test_integration_live.py ring-group testi)
    # TASODIFAN mos kelib ketmasligi uchun (jonli sinovda aynan shunday
    # keng "XXXXXXXXX" naqsh kollizion topilgan edi).
    external = "0" + str(random.randint(100000000, 999999999))
    stripped = external[1:]
    _create_route(auth, trunk_id, patterns=[{"pattern": stripped, "strip_prefix": "0", "add_prefix": "998"}])
    r = httpx.post(f"{BASE}/outbound-routes/simulate", headers=auth,
                    json={"extension": number, "number": external})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allowed"] is True
    assert body["dialed"] == "998" + stripped


def test_simulate_no_match_returns_allowed_false(auth: dict, trunk_id: str):
    number = _random_number()
    httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "sim-ext2"})
    r = httpx.post(f"{BASE}/outbound-routes/simulate", headers=auth,
                    json={"extension": number, "number": "11111"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allowed"] is False
    assert body["route"] is None


def test_simulate_blocked_for_outbound_disabled_extension(auth: dict, trunk_id: str):
    number = _random_number()
    created = httpx.post(f"{BASE}/extensions", headers=auth,
                          json={"number": number, "name": "sim-ext3"}).json()["item"]
    patched = httpx.patch(f"{BASE}/extensions/{created['id']}", headers=auth,
                           json={"outbound_allowed": False, "updated_at": created["updated_at"]})
    assert patched.status_code == 200, patched.text
    _create_route(auth, trunk_id, patterns=[{"pattern": "9XXXXXXXXX"}])
    r = httpx.post(f"{BASE}/outbound-routes/simulate", headers=auth,
                    json={"extension": number, "number": "9123456789"})
    assert r.status_code == 200, r.text
    assert r.json()["allowed"] is False


def test_internal_pin_check_endpoint_with_real_route(auth: dict, trunk_id: str):
    created = _create_route(auth, trunk_id, pin="654321").json()["item"]
    ok = httpx.get(f"{INTERNAL_BASE}/internal/outbound-routes/{created['id']}/pin-check",
                    params={"token": INTERNAL_TOKEN, "pin": "654321"})
    assert ok.status_code == 200
    assert ok.text == "1"

    wrong = httpx.get(f"{INTERNAL_BASE}/internal/outbound-routes/{created['id']}/pin-check",
                       params={"token": INTERNAL_TOKEN, "pin": "000000"})
    assert wrong.text == "0"

    bad_token = httpx.get(f"{INTERNAL_BASE}/internal/outbound-routes/{created['id']}/pin-check",
                           params={"token": "wrong", "pin": "654321"})
    assert bad_token.text == "0"
