"""Ovozli pochta qutilari va bildirishnoma sozlamalari — jonli `innova-m0`
stack'iga qarshi black-box testlar (m1c-contract.md §2). Stack ishlamasa
butun modul `skip` qilinadi (test_outbound_routes_live.py bilan bir xil
naqsh). Har test o'zi yaratganini o'chiradi; bildirishnoma sozlamalariga
faqat validatsiya so'rovlari yuboriladi (proof sozlamasi buzilmaydi)."""
from __future__ import annotations

import random
import subprocess

import httpx
import pytest

from tests.test_outbound_routes_live import ADMIN_LOGIN, ADMIN_PASSWORD, BASE, _stack_available

pytestmark = pytest.mark.skipif(
    not _stack_available(), reason="innova-m0 stack 127.0.0.1:8710'da ishlab turmagan"
)


@pytest.fixture(scope="module")
def auth() -> dict:
    r = httpx.post(f"{BASE}/auth/login", json={"login": ADMIN_LOGIN, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access']}"}


def _number(prefix: str = "86") -> str:
    return prefix + "".join(random.choices("0123456789", k=4))


def _ast(cmd: str) -> str:
    return subprocess.run(["docker", "exec", "innova-m0-asterisk-1", "asterisk", "-rx", cmd],
                          capture_output=True, text=True, timeout=20).stdout


@pytest.fixture()
def shared_box(auth: dict):
    mailbox = _number()
    r = httpx.post(f"{BASE}/voicemail-boxes", headers=auth, json={"mailbox": mailbox, "pin": "1234"}, timeout=30)
    assert r.status_code == 201, r.text
    item = r.json()["item"]
    yield item
    httpx.delete(f"{BASE}/voicemail-boxes/{item['id']}", headers=auth, timeout=30)


@pytest.mark.parametrize("payload", [
    {"pin": "1234"},                                             # na ext, na mailbox
    {"mailbox": "8601", "extension_id": "x", "pin": "1234"},     # ikkalasi
    {"mailbox": "8601", "pin": "12"},                            # PIN qisqa
    {"mailbox": "8601", "pin": "12a4"},                          # PIN raqam emas
    {"mailbox": "8601"},                                         # PIN yo'q
    {"mailbox": "86/01", "pin": "1234"},                         # mailbox yaroqsiz
])
def test_create_validation_422(auth: dict, payload: dict):
    r = httpx.post(f"{BASE}/voicemail-boxes", headers=auth, json=payload, timeout=30)
    assert r.status_code == 422, r.text


def test_shared_box_contract_shape_and_asterisk(auth: dict, shared_box: dict):
    assert set(shared_box) >= {"id", "mailbox", "extension", "email", "email_notify", "telegram_notify",
                               "telegram_chat_id", "attach_audio", "greeting", "has_pin", "counts", "updated_at"}
    assert shared_box["extension"] is None and shared_box["has_pin"] is True
    assert shared_box["counts"] == {"new": 0, "old": 0}
    assert shared_box["mailbox"] in _ast("voicemail show users for t1")
    targets = httpx.get(f"{BASE}/targets", headers=auth, params={"kind": "voicemail"}).json()["items"]
    assert any(shared_box["mailbox"] in t["label"] for t in targets)


def test_duplicate_mailbox_409(auth: dict, shared_box: dict):
    r = httpx.post(f"{BASE}/voicemail-boxes", headers=auth,
                   json={"mailbox": shared_box["mailbox"], "pin": "1234"}, timeout=30)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "mailbox_taken"


def test_patch_updates_fields_and_rejects_stale(auth: dict, shared_box: dict):
    url = f"{BASE}/voicemail-boxes/{shared_box['id']}"
    r = httpx.patch(url, headers=auth, timeout=30, json={
        "email": "x@innova.test", "email_notify": True, "pin": "98765", "updated_at": shared_box["updated_at"]})
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert (item["email"], item["email_notify"], item["has_pin"]) == ("x@innova.test", True, True)
    # `optimistic.naive_utc` soniya aniqligida solishtiradi — eski vaqt aniq boshqa soniyada.
    stale = httpx.patch(url, headers=auth, timeout=30, json={"email": None, "updated_at": "2020-01-01T00:00:00Z"})
    assert stale.status_code == 409


def test_unknown_box_and_message_404(auth: dict, shared_box: dict):
    base = f"{BASE}/voicemail-boxes/{shared_box['id']}/messages"
    assert httpx.get(f"{BASE}/voicemail-boxes/00000000-0000-0000-0000-000000000000/messages", headers=auth).status_code == 404
    assert httpx.get(f"{base}/INBOX/msg0000/audio", headers=auth).status_code == 404
    assert httpx.post(f"{base}/INBOX/msg9999/heard", headers=auth).status_code == 404
    assert httpx.get(base, headers=auth).json() == {"items": []}


def test_box_used_by_inbound_route_cannot_be_deleted(auth: dict, shared_box: dict):
    target = next(t for t in httpx.get(f"{BASE}/targets", headers=auth, params={"kind": "voicemail"}).json()["items"]
                  if shared_box["mailbox"] in t["label"])
    route = httpx.post(f"{BASE}/inbound-routes", headers=auth, timeout=30, json={
        "name": f"vm-live-{shared_box['mailbox']}", "did": "7" + _number("1") + "99",
        "target_id": target["id"], "enabled": True})
    assert route.status_code == 201, route.text
    try:
        r = httpx.delete(f"{BASE}/voicemail-boxes/{shared_box['id']}", headers=auth, timeout=30)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "in_use"
    finally:
        httpx.delete(f"{BASE}/inbound-routes/{route.json()['item']['id']}", headers=auth, timeout=30)


def test_extension_box_lifecycle_sets_and_clears_no_answer(auth: dict):
    ext = httpx.post(f"{BASE}/extensions", headers=auth, timeout=30,
                     json={"number": _number("87"), "name": "VmLive"}).json()["item"]
    box = httpx.post(f"{BASE}/voicemail-boxes", headers=auth, timeout=30,
                     json={"extension_id": ext["id"], "pin": "4321"})
    assert box.status_code == 201, box.text
    assert box.json()["item"]["extension"] == {"id": ext["id"], "number": ext["number"], "name": "VmLive"}
    listed = httpx.get(f"{BASE}/voicemail-boxes", headers=auth, params={"extension_id": ext["id"]}).json()["items"]
    assert [b["mailbox"] for b in listed] == [ext["number"]]
    assert httpx.get(f"{BASE}/voicemail-boxes", headers=auth, params={"extension_id": "nope"}).json() == {"items": []}
    clash = httpx.post(f"{BASE}/voicemail-boxes", headers=auth, timeout=30,
                       json={"mailbox": ext["number"], "pin": "1234"})
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "mailbox_taken"
    # ext o'chirilsa — qutisi ham (yetim manzil/Asterisk foydalanuvchisi qolmaydi).
    assert httpx.delete(f"{BASE}/extensions/{ext['id']}", headers=auth, timeout=30).status_code == 204
    assert httpx.get(f"{BASE}/voicemail-boxes", headers=auth, params={"extension_id": ext["id"]}).json() == {"items": []}
    assert ext["number"] not in _ast("voicemail show users for t1")


@pytest.mark.parametrize("payload", [
    {"smtp_tls": "ssl"},
    {"smtp_port": 0},
    {"telegram_api_base": "ftp://x"},
    {"from_email": "not-an-email"},
])
def test_notify_settings_validation_422(auth: dict, payload: dict):
    r = httpx.patch(f"{BASE}/settings/notify", headers=auth, json=payload, timeout=30)
    assert r.status_code == 422, r.text


def test_notify_settings_never_returns_secrets(auth: dict):
    body = httpx.get(f"{BASE}/settings/notify", headers=auth).json()
    assert {"has_smtp_password", "has_telegram_token", "telegram_api_base", "smtp_tls"} <= set(body)
    assert "smtp_password" not in body and "telegram_token" not in body
