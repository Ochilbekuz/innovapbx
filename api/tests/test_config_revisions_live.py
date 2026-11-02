"""Konfiguratsiya reviziyalari (`/config/revisions/{id}/restore`) — HAQIQIY
`innova-m0` stack'iga qarshi (black-box, `test_integration_live.py`/
`test_outbound_routes_live.py` bilan BIR XIL qolip).

Regressiya (m1b-proof.sh ssenariy 6 orqali topilgan, 2026-10-28): `audit_log.
entity_id` ustuni `uuid` edi, lekin `config_revisions.id` bigint (masalan
461) -- restore HAR DOIM 500 Internal Server Error bilan yiqilardi
(asyncpg `invalid UUID`). Tuzatish: `audit_log.entity_id` -> `text`
(`alembic/versions/0008_audit_entity_id_text.py`)."""
from __future__ import annotations

import os
import random
import re
import uuid
from pathlib import Path

import httpx
import pytest

BASE = "http://127.0.0.1:8710/api/v1"
ADMIN_LOGIN = "admin"


def _proof_password() -> str:
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


def _hangup_target(auth: dict) -> str:
    items = httpx.get(f"{BASE}/targets?kind=hangup", headers=auth).json()["items"]
    return items[0]["id"]


def _random_number() -> str:
    """`test_integration_live.py::_random_number` bilan BIR XIL qolip --
    haqiqiy ichki raqamlar (101, 102, 201 ...) va boshqa test fixture'lar
    bilan to'qnashmasligi uchun keng diapazon."""
    return "9" + str(random.randint(0, 99999)).zfill(5)


def test_restore_applied_revision_does_not_500_and_entity_id_survives(auth: dict):
    """Avval qo'llangan (status=applied) reviziyani tiklash -- 500 EMAS, 200
    bo'lishi SHART; audit yozuvi entity_id=<bigint revision id> bilan
    saqlanishi (UUID'ga cast qilinmasdan) SHART.

    MUHIM (bu segmentda topilgan, SHU TESTdagi xato -- mahsulot kodida EMAS):
    ILGARI bu test ATROF-MUHIT HOLATIGA (boshqa isbot skriptlari --
    `m0-proof.sh`/`m1a-proof.sh`/`m1b-proof.sh` -- qoldirgan qoldiq
    ma'lumotlarga) IKKI JIHATDAN ISHONARDI: (1) `GET /system/health`'da
    ALLAQACHON bitta revision mavjud bo'lishini ("sof" stack'da -- hech
    qanday o'zgarish qilinmagan bo'lsa -- `revision=None`, test shart
    bilan O'TOLMAYDI), (2) tashqi a'zo raqami ("5551112223") uchun
    MOS keluvchi chiquvchi marshrut ALLAQACHON mavjud bo'lishini (bu
    FAQAT ayrim proof skriptlarining tasodifiy marshrut sozlamalariga
    bog'liq -- boshqalarida yo'q). Natijada bu test qaysi proof skript
    OXIRGI ishga tushganiga qarab TASODIFIY o'tib/o'tmay qolardi --
    HAQIQIY mahsulot funksiyasi (revision restore, m1b-proof.sh ssenariy
    6 orqali mustaqil isbotlangan va doim o'tadi) bilan ALOQASI YO'Q.
    Tuzatish: test O'ZI kerakli holatni (kamida bitta revision + ICHKI
    a'zoli ring group, tashqi marshrutga MUTLAQO bog'liq emas) yaratadi."""
    number = _random_number()
    ext = httpx.post(f"{BASE}/extensions", headers=auth,
                      json={"number": number, "name": "revision-probe"})
    assert ext.status_code == 201, ext.text
    ext_id = ext.json()["item"]["id"]
    try:
        health = httpx.get(f"{BASE}/system/health", headers=auth).json()
        revision_a = health["revision"]
        assert revision_a is not None, "boshlang'ich revision topilmadi"

        name = f"RestoreProbe-{uuid.uuid4().hex[:8]}"
        created = httpx.post(
            f"{BASE}/ring-groups", headers=auth,
            json={"name": name, "strategy": "ringall", "ring_seconds": 10,
                  "members": [{"extension_id": ext_id}],
                  "no_answer_target_id": _hangup_target(auth)},
        )
        assert created.status_code == 201, created.text
        rg_id = created.json()["item"]["id"]
        try:
            resp = httpx.post(f"{BASE}/config/revisions/{revision_a}/restore", headers=auth, json={})
            assert resp.status_code == 200, f"restore 500 bilan yiqildi (regressiya): {resp.status_code} {resp.text}"
            assert resp.json()["item"]["status"] == "applied"

            audit = httpx.get(
                f"{BASE}/audit", headers=auth, params={"entity": "config_revision", "action": "restore"},
            ).json()
            assert any(str(item["entity_id"]) == str(revision_a) for item in audit["items"]), (
                f"audit'da entity_id={revision_a} topilmadi: {audit}"
            )
        finally:
            httpx.delete(f"{BASE}/ring-groups/{rg_id}", headers=auth)
    finally:
        httpx.delete(f"{BASE}/extensions/{ext_id}", headers=auth)
