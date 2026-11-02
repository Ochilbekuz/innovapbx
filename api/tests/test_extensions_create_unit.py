"""Vazifa B — `POST /extensions` (parol/qo'shimcha sozlamalar yaratishda) va
`PUT /extensions/{id}/secret` (foydalanuvchi o'zi tanlagan SIP paroli).
DB/AMI'siz: soxta sessiya + monkeypatch — `test_extensions_call_fields_unit.py` bilan bir xil uslub."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import Request

from app.api.v1 import extensions as ex
from app.core.errors import ApiError
from app.db.models import SystemSettings
from app.schemas import CreateExtensionPayload, SetSecretPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


def _request(host: str = "pbx.example.com") -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "scheme": "http", "query_string": b"",
                    "headers": [(b"host", host.encode())], "client": ("10.0.0.1", 1)})


class _Session:
    """`extension_create`/`set_secret` oqimi uchun soxta sessiya: `add`/`flush`/`commit`/`get`."""

    def __init__(self, sip_udp_port: int | None = None):
        self.added: list = []
        self.commits = self.flushes = 0
        self._settings_row = SimpleNamespace(sip_udp_port=sip_udp_port) if sip_udp_port else None

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, model, _pk):
        return self._settings_row if model is SystemSettings else None


@pytest.fixture
def env(monkeypatch):
    state = {"audit": [], "applied": 0, "notified": 0}

    async def fake_ensure_number_free(session, tenant_id, number, **kw):
        return None

    async def fake_encrypt(session, secret):
        return f"ENC:{secret}"

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    async def fake_apply(session, *, tenant_id, user_id, ami):
        state["applied"] += 1
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def fake_get_tenant_code(session, tenant_id):
        return "t1"

    async def fake_notify(session, ami, ext, tenant_code):
        state["notified"] += 1

    def fake_new_extension(*, codecs, **fields):
        # Haqiqiy DB bo'lmasa ustun standartlari (`default=True/...`) INSERT paytida
        # qo'llanadi — soxta sessiyada ORQAGA o'xshatiladi (sof, DB'siz).
        base = dict(enabled=True, outbound_allowed=True, outbound_callerid=None, dnd=False,
                    forward_always=None, forward_busy=None, pickup_group=None, toll_blocked_at=None,
                    toll_block_reason=None, updated_at=NOW, id="e-created")
        base.update(fields, codecs=codecs or [])
        return SimpleNamespace(**base)

    monkeypatch.setattr(ex, "ensure_number_free", fake_ensure_number_free)
    monkeypatch.setattr(ex, "encrypt_secret", fake_encrypt)
    monkeypatch.setattr(ex, "record_audit", fake_audit)
    monkeypatch.setattr(ex, "apply_config", fake_apply)
    monkeypatch.setattr(ex, "get_tenant_code", fake_get_tenant_code)
    monkeypatch.setattr(ex, "notify_extension_devices", fake_notify)
    monkeypatch.setattr(ex, "new_extension", fake_new_extension)
    return state


# ------------------------------------------------------------ POST /extensions — parol
@pytest.mark.asyncio
async def test_create_extension_without_password_generates_random_secret(env):
    out = await ex.create_extension(CreateExtensionPayload(number="301", name="Ali"), _request(),
                                     session=_Session(), user=USER, ami=None)
    assert len(out.sip.password) >= 16  # `generate_sip_secret` standarti


@pytest.mark.asyncio
async def test_create_extension_with_custom_password_uses_it_verbatim(env):
    out = await ex.create_extension(
        CreateExtensionPayload(number="301", name="Ali", password="Abcd1234"), _request(),
        session=_Session(), user=USER, ami=None,
    )
    assert out.sip.password == "Abcd1234"


@pytest.mark.asyncio
async def test_create_extension_weak_password_rejected_before_any_write(env):
    session = _Session()
    with pytest.raises(ApiError) as e:
        await ex.create_extension(CreateExtensionPayload(number="301", name="Ali", password="short1"),
                                  _request(), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "weak_password", "password")
    assert session.added == [] and session.commits == 0


@pytest.mark.asyncio
async def test_create_extension_password_containing_number_rejected(env):
    with pytest.raises(ApiError) as e:
        await ex.create_extension(CreateExtensionPayload(number="301", name="Ali", password="my301pass"),
                                  _request(), session=_Session(), user=USER, ami=None)
    assert e.value.code == "weak_password"


# ------------------------------------------------------------ POST /extensions — qo'shimcha sozlamalar
@pytest.mark.asyncio
async def test_create_extension_with_settings_applies_them(env):
    out = await ex.create_extension(
        CreateExtensionPayload(number="301", name="Ali", dnd=True, forward_busy="202",
                               pickup_group="sales", outbound_allowed=False, enabled=False),
        _request(), session=_Session(), user=USER, ami=None,
    )
    item = out.item
    assert (item.dnd, item.forward_busy, item.pickup_group) == (True, "202", "sales")
    assert (item.outbound_allowed, item.enabled) == (False, False)
    assert env["audit"][0]["diff"]["dnd"] == {"from": False, "to": True}


@pytest.mark.asyncio
async def test_create_extension_bad_forward_number_rejected_same_as_patch(env):
    session = _Session()
    with pytest.raises(ApiError) as e:
        await ex.create_extension(CreateExtensionPayload(number="301", name="Ali", forward_always="abc"),
                                  _request(), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_number", "forward_always")
    assert session.added == []  # tekshiruv yozishdan OLDIN


@pytest.mark.asyncio
async def test_create_extension_bad_pickup_group_rejected_same_as_patch(env):
    with pytest.raises(ApiError) as e:
        await ex.create_extension(CreateExtensionPayload(number="301", name="Ali", pickup_group="Sales!"),
                                  _request(), session=_Session(), user=USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_pickup_group", "pickup_group")


# ------------------------------------------------------------ SipCredentials — domen/port
@pytest.mark.asyncio
async def test_sip_credentials_username_is_raw_number_and_domain_from_request_host(env):
    out = await ex.create_extension(CreateExtensionPayload(number="301", name="Ali"),
                                     _request("pbx.acme.uz"), session=_Session(), user=USER, ami=None)
    assert (out.sip.username, out.sip.domain, out.sip.port) == ("301", "pbx.acme.uz", 5060)


@pytest.mark.asyncio
async def test_sip_credentials_port_uses_configured_sip_udp_port(env):
    out = await ex.create_extension(CreateExtensionPayload(number="301", name="Ali"), _request(),
                                     session=_Session(sip_udp_port=5560), user=USER, ami=None)
    assert out.sip.port == 5560


# ------------------------------------------------------------ PUT /extensions/{id}/secret
def _ext(**kw):
    base = dict(id="e1", tenant_id="t1", number="301", sip_password_enc="OLD")
    base.update(kw)
    return SimpleNamespace(**base)


def _fake_get(ext):
    async def fake_get(session, tenant_id, ext_id):
        return ext
    return fake_get


@pytest.mark.asyncio
async def test_set_secret_accepts_valid_password_and_notifies_devices(env, monkeypatch):
    ext = _ext()
    monkeypatch.setattr(ex, "_get_extension_or_404", _fake_get(ext))
    out = await ex.set_secret("e1", SetSecretPayload(password="Abcd1234"), _request(),
                              session=_Session(), user=USER, ami=None)
    assert out.sip.password == "Abcd1234" and ext.sip_password_enc == "ENC:Abcd1234"
    assert env["notified"] == 1 and env["audit"][0]["action"] == "extension.set_secret"


@pytest.mark.asyncio
async def test_set_secret_rejects_weak_password_without_touching_extension(env, monkeypatch):
    ext = _ext()
    monkeypatch.setattr(ex, "_get_extension_or_404", _fake_get(ext))
    with pytest.raises(ApiError) as e:
        await ex.set_secret("e1", SetSecretPayload(password="301301"), _request(),
                            session=_Session(), user=USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "weak_password", "password")
    assert ext.sip_password_enc == "OLD" and env["notified"] == 0
