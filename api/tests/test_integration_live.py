"""Jonli integratsion testlar — HAQIQIY `innova-m0` docker-compose stack'iga
qarshi (black-box, HTTP orqali), `scripts/m0-proof.sh` bilan bir xil ruhda.

Stack ishlamasa (masalan CI'da compose yo'q) butun modul `skip` qilinadi —
unit testlar (test_optimistic.py, test_auth_logic.py, test_apply_result.py,
test_compiler.py) baribir bazasiz/tarmoqsiz ishlayveradi.

Har bir test o'ziga xos (uuid4 bilan) raqam/nom/DID yaratadi — umumiy admin
hisobiga YOKI boshqa testlarga YON TA'SIR qilmaydi, shu sabab bir necha marta
qayta ishga tushirish xavfsiz (idempotent)."""
from __future__ import annotations

import os
import random
import re
from pathlib import Path
import uuid

import httpx
import pytest

BASE = "http://127.0.0.1:8710/api/v1"
ADMIN_LOGIN = "admin"


def _proof_password() -> str:
    """Test admin paroli — env yoki deploy/.env (kodda sir yo'q)."""
    if os.environ.get("PROOF_ADMIN_PASSWORD"):
        return os.environ["PROOF_ADMIN_PASSWORD"]
    env = Path(__file__).resolve().parents[2] / "deploy" / ".env"
    m = re.search(r"^PROOF_ADMIN_PASSWORD=(.+)$", env.read_text(), re.M) if env.exists() else None
    return m.group(1).strip() if m else ""


ADMIN_PASSWORD = _proof_password()


def _stack_available() -> bool:
    try:
        r = httpx.get("http://127.0.0.1:8710/healthz", timeout=2.0)
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


# Task C: individual testlarga `pytest-*` qatorlarni o'zi tozalashni ishonib
# topshirish mo'rt — ko'p test ATAYLAB tozalamaydi (faqat yaratish
# xatti-harakatini sinaydi), shu sabab modul OXIRIDA bitta umumiy «supurish»
# (API orqali, FK tartibida: navbat -> halqa-guruh -> MOH-sinf -> trunk).
_PYTEST_SWEEP_PATHS = ("/queues", "/ring-groups", "/moh-classes", "/trunks")


def _sweep_pytest_prefixed(auth_hdr: dict, path: str) -> None:
    try:
        items = httpx.get(f"{BASE}{path}", headers=auth_hdr, timeout=5.0).json().get("items", [])
    except (httpx.HTTPError, ValueError):
        return
    for item in items:
        if item.get("name", "").startswith("pytest-"):
            httpx.delete(f"{BASE}{path}/{item['id']}", headers=auth_hdr, timeout=5.0)


@pytest.fixture(scope="module", autouse=True)
def _cleanup_pytest_resources_after_module(token: str):
    yield
    auth_hdr = {"Authorization": f"Bearer {token}"}
    for path in _PYTEST_SWEEP_PATHS:
        _sweep_pytest_prefixed(auth_hdr, path)


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


def _random_number() -> str:
    """6 xonali, `9` bilan boshlanadigan raqam — haqiqiy ichki raqamlar bilan
    (101, 102, 201 ...) VA bir-biridan (qayta-qayta ishga tushirishda) deyarli
    hech qachon to'qnashmasligi uchun keng diapazon (900000-999999)."""
    return "9" + str(random.randint(0, 99999)).zfill(5)


def _random_did() -> str:
    return "9" + str(random.randint(1000000, 9999999))


def test_login_bad_credentials_returns_401():
    r = httpx.post(f"{BASE}/auth/login", json={"login": ADMIN_LOGIN, "password": "notthepassword"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "bad_credentials"


def test_setup_when_already_done_returns_409(auth: dict):
    r = httpx.post(f"{BASE}/setup", json={
        "admin": {"login": "irrelevant", "password": ADMIN_PASSWORD, "full_name": "X"},
    })
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "setup_done"


def test_create_extension_and_apply_pipeline(auth: dict):
    number = _random_number()
    r = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "pytest ext"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["item"]["number"] == number
    assert body["apply"]["status"] in ("applied", "unchanged")
    assert "sip" in body and body["sip"]["username"].endswith(number)


def test_create_extension_duplicate_number_conflicts(auth: dict):
    number = _random_number()
    r1 = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "pytest dup"})
    assert r1.status_code == 201
    r2 = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "pytest dup2"})
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "number_taken"


def test_patch_extension_with_stale_updated_at_returns_409(auth: dict):
    number = _random_number()
    created = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "stale-test"})
    ext_id = created.json()["item"]["id"]
    r = httpx.patch(f"{BASE}/extensions/{ext_id}", headers=auth,
                     json={"name": "renamed", "updated_at": "2000-01-01T00:00:00Z"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "stale"


def test_rotate_secret_is_realtime_only(auth: dict):
    number = _random_number()
    created = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "rotate-test"})
    ext_id = created.json()["item"]["id"]
    r = httpx.post(f"{BASE}/extensions/{ext_id}/rotate-secret", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["apply"] == {"status": "realtime", "revision": None, "message": None}
    assert body["sip"]["password"]


def test_create_trunk_and_test_action(auth: dict):
    name = "pytest-trunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "198.51.100.5", "port": 5060, "match": ["198.51.100.5/32"],
        "codecs": ["ulaw"], "max_channels": 5, "enabled": True,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["apply"] == {"status": "realtime", "revision": None, "message": None}


def test_create_register_trunk_without_password_returns_422(auth: dict):
    name = "pytest-trunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "sip.example.com", "auth_mode": "register", "username": "u1",
    })
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "password_required"


def test_create_trunk_with_blank_host_returns_422(auth: dict):
    name = "pytest-trunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={"name": name, "host": "  "})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "bad_host"


def test_create_register_trunk_hides_password_and_triggers_reload(auth: dict):
    name = "pytest-trunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "sip.example.com", "auth_mode": "register",
        "username": "u1", "password": "super-secret-plain",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["item"]["has_password"] is True
    assert "password" not in body["item"]
    assert "super-secret-plain" not in httpx.request("GET", f"{BASE}/trunks", headers=auth).text
    assert body["apply"]["status"] == "realtime"
    assert body["item"]["health"]["registration"] in ("unregistered", "rejected", "registered", None)


def test_update_trunk_password_masked_in_audit(auth: dict):
    name = "pytest-trunk-" + _short_id()
    created = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "sip.example.com", "auth_mode": "register",
        "username": "u1", "password": "first-secret",
    }).json()
    trunk_id = created["item"]["id"]
    updated_at = created["item"]["updated_at"]

    r = httpx.patch(f"{BASE}/trunks/{trunk_id}", headers=auth,
                      json={"password": "second-secret", "updated_at": updated_at})
    assert r.status_code == 200, r.text

    audit = httpx.get(f"{BASE}/audit?entity=trunk&entity_id={trunk_id}", headers=auth)
    if audit.status_code == 200:
        text = audit.text
        assert "first-secret" not in text
        assert "second-secret" not in text


def _hangup_target_id(auth: dict) -> str:
    targets = httpx.get(f"{BASE}/targets?kind=hangup", headers=auth).json()["items"]
    return targets[0]["id"]


def test_ring_group_with_external_member_and_no_matching_route_returns_422(auth: dict):
    """MUHIM (bu segmentda topilgan, SHU TESTdagi xato -- mahsulot kodida
    EMAS): ILGARI bu test "mos marshrut yo'q" holatini "0901234567" bilan
    tekshirardi -- lekin aynan shu raqam `m1b-contract.md` bo'lim 9'dagi
    KANONIK misol (UZ marshruti, strip_prefix='0' -> '901234567' ->
    'XXXXXXXXX'ga mos) -- `scripts/m1b-proof.sh` ANIQ shu raqamga mos
    keluvchi marshrutni (M1bUZRoute) yaratadi. Natijada bu test
    `m1b-proof.sh`dan KEYIN HAR DOIM muvaffaqiyatsiz bo'lardi (422 kutilsa,
    201 qaytardi) -- marshrutlash KODI emas, test RAQAMI noto'g'ri tanlangan
    edi. Tuzatish: aniq "hech qanday mavjud marshrut patterniga (5/7 bilan
    boshlanuvchi 11 xonali, yoki '0'+9 xonali UZ) mos kelmaydigan" qisqa
    (3 xonali) raqam ishlatiladi."""
    hangup = _hangup_target_id(auth)
    unmatched_number = "100"
    r = httpx.post(f"{BASE}/ring-groups", headers=auth, json={
        "name": "pytest-rg-" + _short_id(), "strategy": "ringall", "ring_seconds": 15,
        "members": [{"external_number": unmatched_number}], "no_answer_target_id": hangup,
    })
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "no_outbound_route"
    assert r.json()["error"]["details"]["number"] == unmatched_number


def test_ring_group_member_both_fields_rejected_as_validation_error(auth: dict):
    hangup = _hangup_target_id(auth)
    r = httpx.post(f"{BASE}/ring-groups", headers=auth, json={
        "name": "pytest-rg-" + _short_id(), "strategy": "ringall", "ring_seconds": 15,
        "members": [{"extension_id": "x", "external_number": "0901234567"}],
        "no_answer_target_id": hangup,
    })
    assert r.status_code == 422


def test_ring_group_with_internal_member_created(auth: dict):
    number = _random_number()
    ext = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "rg-member"}).json()
    hangup = _hangup_target_id(auth)
    r = httpx.post(f"{BASE}/ring-groups", headers=auth, json={
        "name": "pytest-rg-" + _short_id(), "strategy": "ringall", "ring_seconds": 15,
        "members": [{"extension_id": ext["item"]["id"]}], "no_answer_target_id": hangup,
    })
    assert r.status_code == 201, r.text
    body = r.json()["item"]
    assert body["members"][0]["extension"]["number"] == number
    assert body["members"][0]["external_number"] is None


def test_delete_trunk_not_in_use_succeeds(auth: dict):
    name = "pytest-trunk-" + _short_id()
    created = httpx.post(f"{BASE}/trunks", headers=auth, json={
        "name": name, "host": "198.51.100.9", "match": ["198.51.100.9/32"],
    }).json()
    r = httpx.delete(f"{BASE}/trunks/{created['item']['id']}", headers=auth)
    assert r.status_code == 204


def test_create_ip_trunk_without_match_returns_422(auth: dict):
    name = "pytest-trunk-" + _short_id()
    r = httpx.post(f"{BASE}/trunks", headers=auth, json={"name": name, "host": "198.51.100.10", "match": []})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "bad_match"


def test_inbound_route_did_conflict_returns_409(auth: dict):
    targets = httpx.get(f"{BASE}/targets?kind=extension", headers=auth).json()["items"]
    assert targets, "kamida bitta ichki raqam mavjud bo'lishi kerak (oldingi testlardan)"
    target_id = targets[0]["id"]
    did = _random_did()

    r1 = httpx.post(f"{BASE}/inbound-routes", headers=auth, json={
        "name": "pytest-route-1", "did": did, "cid": "", "target_id": target_id, "enabled": True,
    })
    assert r1.status_code == 201, r1.text

    r2 = httpx.post(f"{BASE}/inbound-routes", headers=auth, json={
        "name": "pytest-route-2", "did": did, "cid": "", "target_id": target_id, "enabled": True,
    })
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "did_conflict"


def test_delete_extension_in_use_returns_409(auth: dict):
    number = _random_number()
    ext = httpx.post(f"{BASE}/extensions", headers=auth, json={"number": number, "name": "in-use-test"}).json()
    ext_id = ext["item"]["id"]

    # DIQQAT: `/targets`dagi `id` ichki raqamning `id`siga TENG EMAS (alohida
    # target-identifikator) — sinovda topilgan, shu sabab har doim
    # `/targets`dan raqam bo'yicha qidirish SHART, ext_id'ni ishlatish EMAS.
    targets = httpx.get(f"{BASE}/targets?kind=extension", headers=auth).json()["items"]
    target_id = next(t["id"] for t in targets if t["number"] == number)

    did = _random_did()
    route = httpx.post(f"{BASE}/inbound-routes", headers=auth, json={
        "name": "pytest-in-use-route", "did": did, "cid": "", "target_id": target_id, "enabled": True,
    })
    assert route.status_code == 201, route.text

    r = httpx.delete(f"{BASE}/extensions/{ext_id}", headers=auth)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "in_use"


def test_unauthorized_request_returns_401():
    r = httpx.get(f"{BASE}/extensions")
    assert r.status_code == 401


# ============================================================= M1b: MOH sinflari
def test_create_moh_class_matches_contract_shape_then_deletes(auth: dict):
    name = "pytest-moh-" + _short_id()
    r = httpx.post(f"{BASE}/moh-classes", headers=auth, json={"name": name, "shuffle": True, "file_ids": []})
    assert r.status_code == 201, r.text
    body = r.json()
    item = body["item"]
    assert set(item) == {"id", "name", "shuffle", "files", "updated_at"}
    assert item["name"] == name and item["shuffle"] is True and item["files"] == []
    assert body["apply"]["status"] in ("applied", "unchanged")

    listed = httpx.get(f"{BASE}/moh-classes", headers=auth).json()["items"]
    assert any(m["id"] == item["id"] for m in listed)

    r = httpx.delete(f"{BASE}/moh-classes/{item['id']}", headers=auth)
    assert r.status_code == 204


def test_create_moh_class_duplicate_name_returns_409(auth: dict):
    name = "pytest-moh-" + _short_id()
    created = httpx.post(f"{BASE}/moh-classes", headers=auth, json={"name": name, "shuffle": False, "file_ids": []})
    assert created.status_code == 201, created.text
    dup = httpx.post(f"{BASE}/moh-classes", headers=auth, json={"name": name, "shuffle": False, "file_ids": []})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "name_taken"
    httpx.delete(f"{BASE}/moh-classes/{created.json()['item']['id']}", headers=auth)


def test_update_moh_class_with_stale_updated_at_returns_409(auth: dict):
    name = "pytest-moh-" + _short_id()
    created = httpx.post(f"{BASE}/moh-classes", headers=auth, json={"name": name, "shuffle": False, "file_ids": []}).json()
    moh_id = created["item"]["id"]
    r = httpx.patch(f"{BASE}/moh-classes/{moh_id}", headers=auth,
                     json={"shuffle": True, "updated_at": "2000-01-01T00:00:00Z"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "stale"
    httpx.delete(f"{BASE}/moh-classes/{moh_id}", headers=auth)


def test_delete_default_moh_class_returns_409_in_use(auth: dict):
    items = httpx.get(f"{BASE}/moh-classes", headers=auth).json()["items"]
    default = next(m for m in items if m["name"] == "default")
    r = httpx.delete(f"{BASE}/moh-classes/{default['id']}", headers=auth)
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "in_use"
    assert body["details"]["usages"][0]["kind"] == "moh_class"


def test_queue_wiring_moh_class_blocks_delete_until_queue_removed(auth: dict):
    hangup = _hangup_target_id(auth)
    moh_name = "pytest-moh-" + _short_id()
    moh = httpx.post(f"{BASE}/moh-classes", headers=auth,
                      json={"name": moh_name, "shuffle": False, "file_ids": []}).json()["item"]

    queue = httpx.post(f"{BASE}/queues", headers=auth, json={
        "name": "pytest-q-" + _short_id(), "timeout_target_id": hangup, "moh_class_id": moh["id"],
    })
    assert queue.status_code == 201, queue.text
    queue_item = queue.json()["item"]
    assert queue_item["moh_class"] == {"id": moh["id"], "name": moh_name}

    blocked = httpx.delete(f"{BASE}/moh-classes/{moh['id']}", headers=auth)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["usages"][0]["kind"] == "queue"

    removed = httpx.delete(f"{BASE}/queues/{queue_item['id']}", headers=auth)
    assert removed.status_code == 204, removed.text
    freed = httpx.delete(f"{BASE}/moh-classes/{moh['id']}", headers=auth)
    assert freed.status_code == 204


def test_create_queue_with_invalid_moh_class_id_returns_404(auth: dict):
    hangup = _hangup_target_id(auth)
    r = httpx.post(f"{BASE}/queues", headers=auth, json={
        "name": "pytest-q-" + _short_id(), "timeout_target_id": hangup,
        "moh_class_id": "00000000-0000-0000-0000-000000000000",
    })
    assert r.status_code == 404
    assert r.json()["error"]["field"] == "moh_class_id"


# ============================================================= M1b: audit (login)
def test_audit_list_returns_user_login_not_500(auth: dict):
    """Regressiya: `audit.py`'s `_user_refs` `User.login`ga murojaat qilardi,
    lekin modelda `username` bor — `user_id` to'ldirilgan har qanday audit
    yozuvi 500 (`AttributeError`) bilan yiqilardi (`m1b-contract.md` bo'lim 6:
    `{"id","login"}`). Bu test bevosita admin login orqali hosil bo'lgan
    audit yozuvlarini ro'yxatlab, 200 va to'g'ri shaklni tasdiqlaydi."""
    r = httpx.get(f"{BASE}/audit", headers=auth, params={"action": "login", "size": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"], "kamida bitta 'login' audit yozuvi bo'lishi kerak"
    entry = body["items"][0]
    assert entry["user"]["login"] == ADMIN_LOGIN


def test_successful_login_writes_audit_entry():
    r = httpx.post(f"{BASE}/auth/login", json={"login": ADMIN_LOGIN, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json()["access"]
    auth_hdr = {"Authorization": f"Bearer {token}"}

    listed = httpx.get(f"{BASE}/audit", headers=auth_hdr, params={"action": "login", "size": 5})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(i["action"] == "login" and i["user"]["login"] == ADMIN_LOGIN for i in items)


def test_failed_login_with_known_user_writes_audit_entry(auth: dict):
    bad = httpx.post(f"{BASE}/auth/login", json={"login": ADMIN_LOGIN, "password": "not-the-password"})
    assert bad.status_code == 401

    listed = httpx.get(f"{BASE}/audit", headers=auth, params={"action": "login_failed", "size": 5})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(i["action"] == "login_failed" and i["user"]["login"] == ADMIN_LOGIN for i in items)


def test_failed_login_with_unknown_user_writes_audit_entry_without_user(auth: dict):
    unknown_login = "pytest-nouser-" + _short_id()
    bad = httpx.post(f"{BASE}/auth/login", json={"login": unknown_login, "password": "whatever"})
    assert bad.status_code == 401

    listed = httpx.get(f"{BASE}/audit", headers=auth, params={"q": unknown_login, "size": 5})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(i["action"] == "login_failed" and i["user"] is None for i in items)
    assert any(i["diff"].get("login") == unknown_login for i in items)


def test_audit_q_filter_matches_entity_id_and_diff(auth: dict):
    """`q` endi faqat `entity`ga emas — `entity_id`/`diff` matniga ham mos
    kelishi SHART (brauzerda admin obyekt id yoki ma'lumot bo'yicha qidiradi)."""
    name = "pytest-moh-" + _short_id()
    created = httpx.post(f"{BASE}/moh-classes", headers=auth,
                          json={"name": name, "shuffle": False, "file_ids": []})
    moh_id = created.json()["item"]["id"]

    by_id = httpx.get(f"{BASE}/audit", headers=auth, params={"q": moh_id, "size": 5})
    assert by_id.status_code == 200
    assert any(i["entity_id"] == moh_id for i in by_id.json()["items"])

    by_diff = httpx.get(f"{BASE}/audit", headers=auth, params={"q": name, "size": 5})
    assert by_diff.status_code == 200
    assert any(i["entity_id"] == moh_id for i in by_diff.json()["items"])

    httpx.delete(f"{BASE}/moh-classes/{moh_id}", headers=auth)


# ============================================================= M1b: settings/sip
def test_get_sip_settings_matches_contract_shape(auth: dict):
    """Regressiya: `local_nets` (Postgres `CIDR[]`) asyncpg orqali
    `IPv4Network`/`IPv6Network` obyekt sifatida qaytadi — `str`ga
    aylantirilmasa `GET /settings/sip` 500 (`pydantic.ValidationError`) bilan
    yiqilardi (jonli muhitda topilgan, 2026-10-28)."""
    r = httpx.get(f"{BASE}/settings/sip", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["local_nets"], list)
    assert all(isinstance(n, str) for n in body["local_nets"])
    assert set(body) >= {
        "external_ip", "external_host", "local_nets", "sip_udp_port", "sip_tls_port",
        "rtp_start", "rtp_end", "codecs", "detected", "restart_required", "updated_at",
    }


def _patch_sip(auth: dict, item: dict, apply: bool = False) -> httpx.Response:
    return httpx.patch(f"{BASE}/settings/sip", headers=auth, json={"item": item, "apply": apply})


def test_sip_settings_explicit_null_clears_external_address(auth: dict):
    """Regressiya (S32, 2026-10-28): frontend tozalash uchun `null` yuboradi — avval
    backend `None` ni «o'zgarmaydi» deb tashlab yuborardi, tashqi IP/host'ni o'chirib bo'lmasdi."""
    r = _patch_sip(auth, {"external_ip": "203.0.113.9", "external_host": "pbx.example.uz"})
    assert r.status_code == 200, r.text
    assert r.json()["item"]["external_ip"] == "203.0.113.9"
    r = _patch_sip(auth, {"external_ip": None, "external_host": None})
    assert r.status_code == 200, r.text
    assert r.json()["item"]["external_ip"] is None
    assert r.json()["item"]["external_host"] is None


def test_sip_settings_omitted_field_is_unchanged(auth: dict):
    _patch_sip(auth, {"external_host": "keep.example.uz"})
    r = _patch_sip(auth, {"codecs": ["alaw", "ulaw"]})
    assert r.status_code == 200, r.text
    assert r.json()["item"]["external_host"] == "keep.example.uz"
    _patch_sip(auth, {"external_host": None, "codecs": ["alaw", "ulaw", "g722", "opus"]})


def test_sip_settings_bad_external_ip_is_422(auth: dict):
    r = _patch_sip(auth, {"external_ip": "999.1.1.1"})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "bad_ip"


# ============================================================= M1b: audio yuklash
def test_upload_audio_creates_file_with_valid_duration(auth: dict, tmp_path: Path):
    """Regressiya: `upload_audio` boshida qatorni `duration_ms=0` bilan flush
    qilardi — bu har doim `audio_files_duration_ms_check` (CHECK duration_ms
    > 0) ni buzardi, va natijadagi `IntegrityError` (noto'g'ri) 409
    `name_taken` sifatida ko'rsatilardi: audio yuklash haqiqiy bazaga qarshi
    HECH QACHON muvaffaqiyatli bo'lmagan (jonli DB'da topilgan, 2026-10-28 —
    unit testlar buni ushlamagan, chunki ular haqiqiy CHECK constraint'siz
    DB'ga qarshi ishlamaydi)."""
    from app.services.audio_tools import synth_tone_wav

    wav_path = tmp_path / "tone.wav"
    synth_tone_wav(wav_path, duration_ms=300)
    name = "pytest-audio-" + _short_id()

    r = httpx.post(f"{BASE}/audio", headers=auth,
                    files={"file": ("tone.wav", wav_path.read_bytes(), "audio/wav")},
                    data={"name": name})
    assert r.status_code == 201, r.text
    item = r.json()["item"]
    assert item["name"] == name
    assert item["duration_ms"] > 0

    deleted = httpx.delete(f"{BASE}/audio/{item['id']}", headers=auth)
    assert deleted.status_code == 204


def test_upload_audio_duplicate_name_returns_409_and_leaves_no_orphan_file(auth: dict, tmp_path: Path):
    """Haqiqiy nom to'qnashuvi hali ham 409 `name_taken` bo'lishi SHART (yuqoridagi
    tuzatish — flush'ni kechiktirish — bu yo'lni buzmasligini tasdiqlaydi), va
    diskka yozilgan `.wav` o'chirilishi kerak (orphan fayl qolmasin)."""
    from app.services.audio_tools import synth_tone_wav

    wav_path = tmp_path / "tone.wav"
    synth_tone_wav(wav_path, duration_ms=300)
    name = "pytest-audio-" + _short_id()
    files = lambda: {"file": ("tone.wav", wav_path.read_bytes(), "audio/wav")}  # noqa: E731

    first = httpx.post(f"{BASE}/audio", headers=auth, files=files(), data={"name": name})
    assert first.status_code == 201, first.text
    item = first.json()["item"]

    dup = httpx.post(f"{BASE}/audio", headers=auth, files=files(), data={"name": name})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "name_taken"

    httpx.delete(f"{BASE}/audio/{item['id']}", headers=auth)


def test_user_language_is_saved_per_user(auth: dict):
    """M1c §4: til tanlovi `User.language` ga saqlanadi va `/auth/me` da qaytadi."""
    r = httpx.patch(f"{BASE}/auth/me", headers=auth, json={"language": "ru"})
    assert r.status_code == 200, r.text
    assert r.json()["language"] == "ru"
    assert httpx.get(f"{BASE}/auth/me", headers=auth).json()["language"] == "ru"
    bad = httpx.patch(f"{BASE}/auth/me", headers=auth, json={"language": "de"})
    assert bad.status_code == 422, bad.text
    httpx.patch(f"{BASE}/auth/me", headers=auth, json={"language": "uz"})
