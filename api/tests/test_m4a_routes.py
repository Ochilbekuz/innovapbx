"""M4a — /devices va /settings/provisioning marshrut funksiyalari (soxta sessiya, bog'liqliklar monkeypatch)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api import prov as prov_api
from app.api.v1 import devices as api
from app.api.v1 import settings_provisioning as sp
from app.core.errors import ApiError
from app.schemas_devices import (
    AssignDiscoveredPayload,
    DeviceOut,
    RotateTokenPayload,
    UpdateDevicePayload,
    UpdateProvisioningPayload,
    PutKeysPayload,
    DeviceKeyIn,
)
from app.services import device_views as views
from app.services import devices as svc
from app.services.ami import AmiError
from app.services.prov_settings import ProvSettings
from tests.test_m4a_services import TID, TOKEN, FakeSession, _device, _ext, _key, _request, _tp

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(id="u1", tenant_id=TID)
DEV_ID = "22222222-2222-2222-2222-222222222222"


class Session(FakeSession):
    def __init__(self, *results, objects=None):
        super().__init__(*results, objects=objects)
        self.deleted = []

    async def delete(self, obj):
        self.deleted.append(obj)


@pytest.fixture
def audits(monkeypatch):
    seen = []

    async def fake_audit(_session, **kw):
        seen.append(kw)

    monkeypatch.setattr(api, "record_audit", fake_audit)
    monkeypatch.setattr(sp, "record_audit", fake_audit)
    return seen


@pytest.fixture
def view(monkeypatch):
    async def fake_view(_session, _ami, _tid, device):
        return f"view:{device.id}"

    monkeypatch.setattr(views, "device_view", fake_view)
    monkeypatch.setattr(api, "DeviceItem", lambda item: SimpleNamespace(item=item))


def _phone(**kw):
    return _device(id=DEV_ID, kind="ip_phone", updated_at=NOW, notes=None, **kw)


def _patch_device(monkeypatch, device):
    async def fake(_session, _user, _device_id):
        return device

    monkeypatch.setattr(api, "_device_or_404", fake)


# ------------------------------------------------------------------ PATCH /devices/{id}
def test_update_device_changes_and_audits(monkeypatch, audits, view):
    device = _phone()
    _patch_device(monkeypatch, device)
    calls = []

    async def fake_mac_free(_s, _t, mac, exclude_id=None):
        calls.append(("mac", mac, exclude_id))

    async def fake_keys(_s, ids):
        return {ids[0]: [_key(idx=5)]}

    async def fake_ext(_s, _u, ext_id):
        return _ext(id=ext_id)

    async def fake_accepts(_s, ext, exclude_id=None):
        calls.append(("ext", ext.id, exclude_id))

    monkeypatch.setattr(svc, "ensure_mac_free", fake_mac_free)
    monkeypatch.setattr(svc, "keys_by_device", fake_keys)
    monkeypatch.setattr(api, "_extension_or_422", fake_ext)
    monkeypatch.setattr(svc, "ensure_extension_accepts", fake_accepts)
    payload = UpdateDevicePayload(updated_at=NOW, mac="80-5E-C0-A4-00-09", model="T48S", extension_id="e9",
                                  label="Qabul", notes="n", enabled=False)
    result = asyncio.run(api.update_device(DEV_ID, payload, Session(), USER, None))
    assert result.item == f"view:{DEV_ID}"
    assert (device.mac, device.model, device.extension_id, device.label, device.enabled) == (
        "805ec0a40009", "T48S", "e9", "Qabul", False)
    assert calls == [("mac", "805ec0a40009", DEV_ID), ("ext", "e9", DEV_ID)]
    assert audits[0]["action"] == "device.update" and audits[0]["diff"]["notes"] == "n"


def test_update_device_model_too_small_for_keys(monkeypatch, audits, view):
    _patch_device(monkeypatch, _phone(model="T48S"))

    async def fake_keys(_s, ids):
        return {ids[0]: [_key(idx=29)]}

    monkeypatch.setattr(svc, "keys_by_device", fake_keys)
    with pytest.raises(ApiError) as err:
        asyncio.run(api.update_device(DEV_ID, UpdateDevicePayload(updated_at=NOW, model="T41S"), Session(), USER,
                                      None))
    assert err.value.code == "key_out_of_range" and audits == []


def test_update_device_noop_skips_commit(monkeypatch, audits, view):
    _patch_device(monkeypatch, _phone())
    session = Session()
    asyncio.run(api.update_device(DEV_ID, UpdateDevicePayload(updated_at=NOW), session, USER, None))
    assert session.commits == 0 and audits == []


def test_update_device_stale(monkeypatch, view):
    _patch_device(monkeypatch, _phone())
    with pytest.raises(ApiError) as err:
        asyncio.run(api.update_device(DEV_ID, UpdateDevicePayload(updated_at=datetime(2020, 1, 1)), Session(), USER,
                                      None))
    assert err.value.status_code == 409


# ------------------------------------------------------------------ PUT keys / DELETE / resync
@pytest.mark.parametrize("updated_at", [None, NOW])
def test_put_keys(monkeypatch, audits, view, updated_at):
    device = _phone()
    _patch_device(monkeypatch, device)
    saved = []

    async def fake_validate(_s, _t, keys, limit):
        return [_key(idx=k.idx, type_=k.type, value=k.value) for k in keys]

    async def fake_replace(_s, device_id, keys):
        saved.append((device_id, len(keys)))

    monkeypatch.setattr(svc, "validate_keys", fake_validate)
    monkeypatch.setattr(svc, "replace_keys", fake_replace)
    payload = PutKeysPayload(keys=[DeviceKeyIn(idx=1, type="blf", value="102")], updated_at=updated_at)
    session = Session()
    asyncio.run(api.put_keys(DEV_ID, payload, session, USER, None))
    assert saved == [(DEV_ID, 1)] and session.commits == 1
    assert audits[0]["diff"] == {"op": "keys", "keys": ["1:blf:102"]}


def test_delete_device(monkeypatch, audits):
    device = _phone()
    _patch_device(monkeypatch, device)
    session = Session()
    assert asyncio.run(api.delete_device(DEV_ID, session, USER)).status_code == 204
    assert session.deleted == [device] and audits[0]["diff"] == {"mac": "805ec0a40001"}


@pytest.mark.parametrize(("registered", "notify_error", "expected"), [
    (False, None, 409), (True, AmiError("down"), 502), (True, None, 200)])
def test_resync(monkeypatch, audits, registered, notify_error, expected):
    _patch_device(monkeypatch, _phone())

    async def fake_registered(_s, _ami, _t, _d):
        return registered, "t1-101"

    async def fake_notify(_ami, endpoint):
        if notify_error:
            raise notify_error

    monkeypatch.setattr(views, "is_device_registered", fake_registered)
    monkeypatch.setattr(svc, "send_check_sync", fake_notify)
    if expected != 200:
        with pytest.raises(ApiError) as err:
            asyncio.run(api.resync_device(DEV_ID, Session(), USER, None))
        assert err.value.status_code == expected and audits == []
        return
    result = asyncio.run(api.resync_device(DEV_ID, Session(), USER, None))
    assert (result.ok, result.endpoint) == (True, "t1-101") and audits[0]["action"] == "device.resync"


# ------------------------------------------------------------------ topilganlar / so'rovlar jurnali
def _discovered(vendor="yealink", model="T46S"):
    return SimpleNamespace(mac="80:5e:c0:a4:00:01", vendor=vendor, model=model)


def test_assign_discovered_needs_vendor():
    session = Session(objects={("DiscoveredDevice", str((TID, "805ec0a40001"))): _discovered(vendor=None)})
    with pytest.raises(ApiError) as err:
        asyncio.run(api.assign_discovered("80:5e:c0:a4:00:01", AssignDiscoveredPayload(extension_id="e1"), session,
                                          USER, None))
    assert (err.value.code, err.value.field) == ("unsupported_model", "vendor")


def test_assign_discovered_creates(monkeypatch, view):
    session = Session(objects={("DiscoveredDevice", str((TID, "805ec0a40001"))): _discovered()})
    created = []

    async def fake_create(_s, _u, payload):
        created.append(payload)
        return SimpleNamespace(id="new")

    monkeypatch.setattr(api, "_create", fake_create)
    result = asyncio.run(api.assign_discovered("805ec0a40001", AssignDiscoveredPayload(extension_id="e1", label="L"),
                                               session, USER, None))
    assert result.item == "view:new"
    assert (created[0].mac, created[0].vendor, created[0].model, created[0].label) == (
        "805ec0a40001", "yealink", "T46S", "L")


def test_discovered_unknown_mac_404():
    with pytest.raises(ApiError) as err:
        asyncio.run(api.dismiss_discovered("zz", Session(), USER))
    assert err.value.status_code == 404


def test_dismiss_discovered(audits):
    row = _discovered()
    session = Session(objects={("DiscoveredDevice", str((TID, "805ec0a40001"))): row})
    assert asyncio.run(api.dismiss_discovered("805ec0a40001", session, USER)).status_code == 204
    assert session.deleted == [row] and audits[0]["entity"] == "discovered_device"


@pytest.mark.parametrize(("mac", "ip", "fragments"), [
    (None, None, []), ("80:5E:C0:A4:00:01", None, ["provision_requests.mac"]),
    (None, " 10.0.0.5 ", ["host(provision_requests.ip)"])])
def test_list_requests_filters(mac, ip, fragments):
    row = SimpleNamespace(id=1, at=NOW, ip="10.0.0.5", mac=None, vendor=None, path="/prov/***/x", status_code=404,
                          reason="unknown_mac", user_agent="UA")
    session = Session([row])
    result = asyncio.run(api.list_requests(mac, ip, 50, session, USER))
    assert [item.mac for item in result.items] == [None]
    sql = str(session.executed[0])
    assert all(fragment in sql for fragment in fragments)


# ------------------------------------------------------------------ device_views / device_pairs / config_view
def test_device_views_empty_short_circuits():
    assert asyncio.run(views.device_views(Session(), None, TID, [])) == []


def test_device_views_builds_status(monkeypatch):
    device = _phone(provisioned_at=None, last_seen_at=None, firmware=None, user_agent=None, created_at=NOW)
    ext = _ext()

    async def fake_tp(_s, _t, _h=None):
        return _tp()

    async def fake_keys(_s, ids):
        return {ids[0]: [_key()]}

    async def fake_passwords(_s, ids):
        return {"e1": "pw"}

    async def fake_hosts(_ami, endpoints):
        assert endpoints == ["t1-101"]
        return {}

    monkeypatch.setattr(views, "tenant_prov", fake_tp)
    monkeypatch.setattr(svc, "keys_by_device", fake_keys)
    monkeypatch.setattr(svc, "sip_passwords", fake_passwords)
    monkeypatch.setattr(svc, "contact_hosts", fake_hosts)
    out = asyncio.run(views.device_views(Session(), None, TID, [(device, ext)]))
    assert isinstance(out[0], DeviceOut)
    assert (out[0].status, out[0].registered, out[0].keys_count, out[0].extension.number) == (
        "never", False, 1, "101")


@pytest.mark.parametrize(("kw", "fragments"), [
    ({}, []), ({"extension_id": "e1", "vendor": "fanvil"}, ["devices.extension_id", "devices.vendor"]),
    ({"q": "  Ali "}, ["lower(devices.label)", "replace("]), ({"q": "   "}, [])])
def test_device_pairs_filters(kw, fragments):
    session = Session([("d", "e")])
    assert asyncio.run(views.device_pairs(session, TID, **kw)) == [("d", "e")]
    sql = str(session.executed[0])
    assert all(fragment in sql for fragment in fragments)
    assert ("lower(devices.label)" in sql) == bool((kw.get("q") or "").strip())


def test_config_view_masks(monkeypatch):
    async def fake_tp(_s, _t, host=None):
        assert host == "pbx.uz:8711"
        return _tp()

    async def fake_keys(_s, ids):
        return {ids[0]: []}

    monkeypatch.setattr(views, "tenant_prov", fake_tp)
    monkeypatch.setattr(svc, "keys_by_device", fake_keys)
    session = Session(objects={("Extension", "e1"): _ext()})
    out = asyncio.run(views.config_view(session, TID, _phone(), "pbx.uz:8711"))
    assert out.filename == "805ec0a40001.cfg" and "account.1.password = ***" in out.content


# ------------------------------------------------------------------ /settings/provisioning
def _settings_row(**prov):
    raw = ProvSettings(prov_token=TOKEN).to_raw()
    raw.update(prov)
    return SimpleNamespace(provisioning=raw, integrations={}, updated_at=NOW)


@pytest.fixture
def settings_row(monkeypatch):
    row = _settings_row(admin_password_enc="old")

    async def fake_row(_s, _t):
        return row

    async def fake_encrypt(_s, value):
        return f"enc:{value}"

    monkeypatch.setattr(sp, "get_settings_row", fake_row)
    monkeypatch.setattr(sp, "encrypt_secret", fake_encrypt)
    return row


@pytest.mark.parametrize(("password", "stored", "diff"), [
    ("s3cret", "enc:s3cret", "set"), (None, None, "cleared"), ("", None, "cleared")])
def test_update_provisioning_admin_password(settings_row, audits, password, stored, diff):
    payload = UpdateProvisioningPayload(updated_at=NOW, admin_password=password)
    out = asyncio.run(sp.update_provisioning(payload, _request(), Session(), USER))
    assert settings_row.provisioning["admin_password_enc"] == stored
    assert audits[0]["diff"] == {"admin_password": diff}
    assert out.has_admin_password is bool(stored)


def test_update_provisioning_extra_and_plain(settings_row, audits):
    payload = UpdateProvisioningPayload.model_validate(
        {"updated_at": NOW, "language": "ru", "extra": {"fanvil": "<GLOBAL CONFIG MODULE>"}})
    out = asyncio.run(sp.update_provisioning(payload, _request(), Session(), USER))
    assert settings_row.provisioning["language"] == "ru" and out.extra.fanvil == "<GLOBAL CONFIG MODULE>"
    assert settings_row.provisioning["admin_password_enc"] == "old"
    assert set(audits[0]["diff"]) == {"language", "extra"}


def test_update_provisioning_noop(settings_row, audits):
    session = Session()
    asyncio.run(sp.update_provisioning(UpdateProvisioningPayload(updated_at=NOW), _request(), session, USER))
    assert session.commits == 0 and audits == []


@pytest.mark.parametrize("payload", [None, RotateTokenPayload(), RotateTokenPayload(updated_at=NOW)])
def test_rotate_token(settings_row, audits, payload):
    out = asyncio.run(sp.rotate_token(_request(), payload, Session(), USER))
    assert settings_row.provisioning["prov_token"] != TOKEN and TOKEN not in out.url
    assert audits[0]["diff"] == {"prov_token": "rotated"}


def test_rotate_token_stale(settings_row):
    with pytest.raises(ApiError) as err:
        asyncio.run(sp.rotate_token(_request(), RotateTokenPayload(updated_at=datetime(2020, 1, 1)), Session(), USER))
    assert err.value.status_code == 409


# ------------------------------------------------------------------ GET /prov/ marshruti, tozalovchi sikl
def test_provision_route_passes_request(monkeypatch):
    seen = []

    async def fake_serve(_s, req):
        seen.append(req)
        return SimpleNamespace(body=b"x", status=200, content_type="text/plain")

    monkeypatch.setattr(prov_api, "serve", fake_serve)
    request = Request({"type": "http", "method": "GET", "path": "/", "scheme": "http", "query_string": b"",
                       "headers": [(b"user-agent", b"Yealink"), (b"host", b"web")], "client": ("10.0.0.5", 1)})
    resp = asyncio.run(prov_api.provision(TOKEN, "y000000000028.cfg", request, Session()))
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    assert (seen[0].ip, seen[0].user_agent, seen[0].host) == ("10.0.0.5", "Yealink", "web")


@pytest.mark.parametrize("outcome", [3, 0, RuntimeError("db")])
def test_purge_forever_survives_errors(monkeypatch, outcome):
    async def fake_once(_factory):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def stop(_s):
        raise asyncio.CancelledError

    monkeypatch.setattr(prov_api, "purge_requests_once", fake_once)
    monkeypatch.setattr(prov_api.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(prov_api.purge_requests_forever(None, 1))


def test_purge_forever_skips_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_once(_factory):
        raise AssertionError("texnik xizmat paytida purge_requests_once chaqirilmasin")

    async def stop(_s):
        raise asyncio.CancelledError

    monkeypatch.setattr(prov_api, "purge_requests_once", fail_once)
    monkeypatch.setattr(prov_api.asyncio, "sleep", stop)
    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(prov_api.purge_requests_forever(None, 1))
    finally:
        maintenance.state.enabled = False
