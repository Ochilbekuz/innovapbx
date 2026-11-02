"""M4a — devices xizmati, /prov/ oqimi (soxta sessiya bilan), provisioning sozlamalari, sxema validatsiyasi."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.api import prov as prov_api
from app.api.v1 import settings_provisioning as sp
from app.core.errors import ApiError
from app.schemas_devices import CreateDevicePayload, DeviceKeyIn, PutKeysPayload, UpdateProvisioningPayload
from app.services import devices as svc
from app.services import live_status
from app.services import prov_serve as ps
from app.services.ami import AmiError
from app.services.prov_guard import FailureGuard
from app.services.prov_settings import ProvSettings
from tests.test_m3b_services_unit import FakeSession as _BaseSession
from tests.test_m3b_services_unit import _Result as _BaseResult

TOKEN = "a" * 32
TID = "11111111-1111-1111-1111-111111111111"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class _Result(_BaseResult):
    def scalars(self):  # haqiqiy ScalarResult kabi iteratsiya qilinadi
        return iter(list(self.value or []))


class FakeSession(_BaseSession):
    async def execute(self, stmt, params=None):
        return _Result((await super().execute(stmt, params)).value)


def _key(idx=1, type_="blf", value="102", label=""):
    return SimpleNamespace(idx=idx, type=type_, value=value, label=label)


def _device(**kw):
    base = dict(id="d1", vendor="yealink", model="T46S", mac="80:5e:c0:a4:00:01", label="", enabled=True,
                extension_id="e1", provisioned_at=NOW, config_hash="h", last_ip="10.0.0.5")
    base.update(kw)
    return SimpleNamespace(**base)


def _ext(**kw):
    base = dict(id="e1", number="101", name="Ali", callerid_name=None, webrtc=False, max_contacts=2)
    base.update(kw)
    return SimpleNamespace(**base)


def _tp(host="pbx.uz", from_request=False, admin=None, **cfg):
    return svc.TenantProv(cfg=ProvSettings(prov_token=TOKEN, **cfg), tenant_code="t1", server_host=host,
                          host_from_request=from_request, server_port=5060, admin_password=admin)


def _row(**prov):
    return SimpleNamespace(tenant_id=TID, provisioning={"prov_token": TOKEN, **prov}, integrations={},
                           sip_udp_port=5060, sip_tls_port=5061, updated_at=NOW)


def _request(host="pbx.uz:8711", forwarded=None, scheme="https"):
    headers = [(b"host", host.encode())]
    if forwarded:
        headers.append((b"x-forwarded-host", forwarded.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "scheme": scheme,
                    "query_string": b"", "server": ("x", 443)})


# ------------------------------------------------------------------ server host / status
@pytest.mark.parametrize(("configured", "base", "req", "expected"), [
    ("sip.pbx.uz", "https://web.uz", "h:1", ("sip.pbx.uz", False)),
    (None, "https://web.uz:8443/x", "h:1", ("web.uz", False)),
    (None, "", "pbx.uz:8711", ("pbx.uz", True)),
    (None, None, "[::1]:80", ("::1", True)),
    (None, None, None, ("", True)),
])
def test_resolve_server_host(configured, base, req, expected) -> None:
    assert svc.resolve_server_host(configured, base, req) == expected


def test_server_port_by_transport() -> None:
    row = _row()
    assert svc.server_port(row, "udp") == 5060
    assert svc.server_port(row, "tcp") == 5060
    assert svc.server_port(row, "tls") == 5061
    assert svc.server_port(SimpleNamespace(sip_udp_port=None, sip_tls_port=None), "udp") == 5060


def test_device_status_precedence() -> None:
    assert svc.device_status(_device(provisioned_at=None), "h", True) == "never"
    assert svc.device_status(_device(config_hash=None), "h", True) == "never"
    assert svc.device_status(_device(), "other", True) == "stale_config"
    assert svc.device_status(_device(), "h", True) == "registered"
    assert svc.device_status(_device(), "h", False) == "provisioned"


def test_is_registered_by_contact_host() -> None:
    assert svc.is_registered(_device(), {"10.0.0.5"})
    assert svc.is_registered(_device(last_ip="10.0.0.5/32"), {"10.0.0.5"})
    assert not svc.is_registered(_device(), {"10.0.0.6"})
    assert not svc.is_registered(_device(), None)
    assert not svc.is_registered(_device(), set())
    assert not svc.is_registered(_device(last_ip=None), {"10.0.0.5"})


def test_device_ctx_and_hash() -> None:
    keys = [SimpleNamespace(idx=2, type="speed_dial", value="5", label="b"), SimpleNamespace(idx=1, type="blf",
                                                                                           value="102", label="a")]
    ctx = svc.device_ctx(_device(label="Lobby"), _ext(callerid_name="Qabul"), keys, _tp(admin="adm"), "pw")
    assert (ctx.mac, ctx.sip_user, ctx.display_name, ctx.password, ctx.label) == (
        "805ec0a40001", "t1-101", "Qabul", "pw", "Lobby")
    assert [k.idx for k in ctx.keys] == [1, 2] and ctx.admin_password == "adm"
    assert svc.device_ctx(_device(), _ext(), [], _tp(), "pw").display_name == "Ali"
    # so'rovdan olingan host hash'ga ta'sir qilmaydi (boshqa domen orqali kirilsa ham stale emas)
    a = svc.device_ctx(_device(), _ext(), [], _tp("a.uz", True), "pw")
    b = svc.device_ctx(_device(), _ext(), [], _tp("b.uz", True), "pw")
    assert svc.config_hash("yealink", "T46S", a, _tp("a.uz", True)) == svc.config_hash("yealink", "T46S", b,
                                                                                       _tp("b.uz", True))
    assert svc.config_hash("yealink", "T46S", a, _tp("a.uz")) != svc.config_hash("yealink", "T46S", b, _tp("b.uz"))
    c = svc.device_ctx(_device(), _ext(), [], _tp(), "pw2")
    assert svc.config_hash("yealink", "T46S", c, _tp()) != svc.config_hash(
        "yealink", "T46S", svc.device_ctx(_device(), _ext(), [], _tp(), "pw"), _tp())
    name, body = svc.masked_config("yealink", "T46S", c)
    assert name == "805ec0a40001.cfg" and "pw2" not in body and "account.1.password = ***" in body


# ------------------------------------------------------------------ validatsiya
def _api_error(fn, *args):
    with pytest.raises(ApiError) as exc:
        fn(*args)
    return exc.value


def test_mac_and_model_or_422() -> None:
    assert svc.normalize_mac_or_422("80-5E-C0-A4-00-01") == "805ec0a40001"
    err = _api_error(svc.normalize_mac_or_422, "xyz")
    assert (err.status_code, err.code, err.field) == (422, "invalid_mac", "mac")
    assert svc.model_or_422("yealink", "t46s").model == "T46S"
    err = _api_error(svc.model_or_422, "yealink", "X1")
    assert (err.code, err.field) == ("unsupported_model", "model")
    assert _api_error(svc.model_or_422, None, None).code == "unsupported_model"


@pytest.mark.parametrize(("keys", "code", "field"), [
    ([_key(idx=7)], "key_out_of_range", "keys.0.idx"),
    ([_key(idx=1), _key(idx=1)], "duplicate_key", "keys.1.idx"),
    ([_key(type_="park", value="700")], "invalid_park_slot", "keys.0.value"),
    ([_key(type_="park", value="721")], "invalid_park_slot", "keys.0.value"),
    ([_key(type_="park", value="x")], "invalid_park_slot", "keys.0.value"),
    ([_key(type_="speed_dial", value="12a")], "invalid_key_value", "keys.0.value"),
    ([_key(type_="speed_dial", value="")], "invalid_key_value", "keys.0.value"),
])
def test_check_key_shape_errors(keys, code, field) -> None:
    err = _api_error(svc.check_key_shape, keys, 6)
    assert (err.status_code, err.code, err.field) == (422, code, field)


def test_check_key_shape_ok() -> None:
    svc.check_key_shape([_key(idx=6), _key(idx=2, type_="park", value="701"), _key(idx=3, type_="park", value="720"),
                         _key(idx=4, type_="speed_dial", value="+99890*1#")], 6)


@pytest.mark.asyncio
async def test_validate_keys_blf_must_exist() -> None:
    with pytest.raises(ApiError) as exc:
        await svc.validate_keys(FakeSession(["102"]), TID, [_key(value="102"), _key(idx=2, value="999")], 10)
    assert (exc.value.code, exc.value.field) == ("unknown_extension", "keys.1.value")
    out = await svc.validate_keys(FakeSession(["102"]), TID, [
        _key(value="102", label="Boss"), _key(idx=2, type_="line", value="zzz"), _key(idx=3, type_="dnd", value="1"),
        _key(idx=4, type_="none", value="q"), _key(idx=5, type_="speed_dial", value="5")], 10)
    assert [(k.idx, k.type, k.value, k.label) for k in out] == [
        (1, "blf", "102", "Boss"), (2, "line", "", ""), (3, "dnd", "", ""), (4, "none", "", ""),
        (5, "speed_dial", "5", "")]
    session = FakeSession()
    assert await svc.validate_keys(session, TID, [_key(type_="none", value="")], 10)
    assert session.executed == []  # BLF yo'q — bazaga so'rov yo'q


@pytest.mark.asyncio
async def test_ensure_extension_accepts() -> None:
    with pytest.raises(ApiError) as exc:
        await svc.ensure_extension_accepts(FakeSession(), _ext(webrtc=True))
    assert (exc.value.code, exc.value.field) == ("extension_webrtc", "extension_id")
    with pytest.raises(ApiError) as exc:
        await svc.ensure_extension_accepts(FakeSession(2), _ext())
    assert exc.value.code == "max_contacts" and exc.value.details == {"max_contacts": 2}
    await svc.ensure_extension_accepts(FakeSession(1), _ext())
    session = FakeSession(0)
    await svc.ensure_extension_accepts(session, _ext(), exclude_id="d1")
    assert "devices.id !=" in str(session.executed[0])


@pytest.mark.asyncio
async def test_ensure_mac_free() -> None:
    with pytest.raises(ApiError) as exc:
        await svc.ensure_mac_free(FakeSession(("d1",)), TID, "805ec0a40001")
    assert (exc.value.status_code, exc.value.code) == (409, "mac_taken")
    session = FakeSession(None)
    await svc.ensure_mac_free(session, TID, "805ec0a40001", exclude_id="d1")
    assert "devices.id !=" in str(session.executed[0])


@pytest.mark.asyncio
async def test_replace_and_group_keys() -> None:
    session = FakeSession()
    keys = [SimpleNamespace(device_id=None, idx=1)]
    await svc.replace_keys(session, "d1", keys)
    assert keys[0].device_id == "d1" and session.added == keys and len(session.executed) == 1
    assert await svc.keys_by_device(FakeSession(), []) == {}
    rows = [SimpleNamespace(device_id="d1", idx=1), SimpleNamespace(device_id="d2", idx=1)]

    class S(FakeSession):
        async def execute(self, stmt, params=None):
            return SimpleNamespace(scalars=lambda: iter(rows))
    grouped = await svc.keys_by_device(S(), ["d1", "d2", "d3"])
    assert {k: len(v) for k, v in grouped.items()} == {"d1": 1, "d2": 1, "d3": 0}


# ------------------------------------------------------------------ AMI: contact hostlari, check-sync
PJSIP_OUT = """
 Endpoint:  t1-101                                               Not in use    0 of inf
      Contact:  t1-101/sip:t1-101@172.21.0.231:5060              0fb0660acf NonQual  -nan
      Contact:  t1-101/sip:t1-101@172.21.0.239:5099;ob           1fb0660acf Unavail  -nan
 Endpoint:  t1-102                                               Not in use    0 of inf
      Contact:  t1-102/sip:t1-102@[2001:db8::5]:5060             2fb0660acf Avail     12.1
      Contact:  t1-999/sip:x@10.9.9.9:5060                       3fb0660acf Avail     12.1
"""


def test_contact_hosts_online_only() -> None:
    assert live_status.contact_hosts(PJSIP_OUT, {"t1-101", "t1-102", "t1-103"}) == {
        "t1-101": {"172.21.0.231"}, "t1-102": {"2001:db8::5"}, "t1-103": set()}


class FakeAmi:
    def __init__(self, response=None, raise_exc=None):
        self.response = response or {"Response": "Success"}
        self.raise_exc = raise_exc
        self.actions = []

    async def ensure_connected(self):
        if self.raise_exc:
            raise self.raise_exc

    async def action(self, name, **kw):
        self.actions.append((name, kw))
        return self.response


@pytest.mark.asyncio
async def test_send_check_sync() -> None:
    ami = FakeAmi()
    await svc.send_check_sync(ami, "t1-101")
    assert ami.actions == [("PJSIPNotify", {"Endpoint": "t1-101", "Option": "innova-check-sync"})]
    with pytest.raises(AmiError, match="no endpoint"):
        await svc.send_check_sync(FakeAmi({"Response": "Error", "Message": "no endpoint"}), "t1-101")


@pytest.mark.asyncio
async def test_notify_extension_devices() -> None:
    ami = FakeAmi()
    assert await svc.notify_extension_devices(FakeSession(0), ami, _ext(), "t1") is False
    assert ami.actions == []
    assert await svc.notify_extension_devices(FakeSession(1), ami, _ext(), "t1") is True
    assert ami.actions[0][1]["Endpoint"] == "t1-101"
    assert await svc.notify_extension_devices(FakeSession(1), FakeAmi(raise_exc=OSError("down")), _ext(), "t1") is False
    assert await svc.notify_extension_devices(FakeSession(1), FakeAmi({"Response": "Error"}), _ext(), "t1") is False


@pytest.mark.asyncio
async def test_contact_hosts_ami_down(monkeypatch) -> None:
    async def none(*_a):
        return None
    monkeypatch.setattr(live_status, "run_command", none)
    assert await svc.contact_hosts(object(), ["t1-101"]) == {}
    assert await live_status.endpoint_contact_hosts(object(), []) == {}


# ------------------------------------------------------------------ sxemalar (CR/LF in'yeksiyasi)
@pytest.mark.parametrize("label", ["a\nb", "a\rb", "x\x00y", "tab\there"])
def test_schema_rejects_control_chars(label) -> None:
    with pytest.raises(ValidationError):
        DeviceKeyIn(idx=1, type="blf", value="102", label=label)
    with pytest.raises(ValidationError):
        CreateDevicePayload(mac="805ec0a40001", vendor="yealink", model="T46S", extension_id=TID, label=label)


def test_schema_limits() -> None:
    with pytest.raises(ValidationError):
        DeviceKeyIn(idx=61, type="blf", value="102")
    with pytest.raises(ValidationError):
        DeviceKeyIn(idx=1, type="foo", value="102")
    with pytest.raises(ValidationError):
        PutKeysPayload(keys=[], extra_field=1)
    assert DeviceKeyIn(idx=60, type="none").value == ""


# ------------------------------------------------------------------ settings/provisioning
def test_provisioning_base_and_out() -> None:
    row = _row()
    assert sp.provisioning_base(row, _request()) == "https://pbx.uz:8711"
    assert sp.provisioning_base(row, _request(forwarded="a.uz:443, b")) == "https://a.uz:443"
    row.integrations = {"public_base_url": "https://pbx.example.uz/"}
    out = sp.provisioning_out(row, _request())
    assert out.url == out.dhcp_option_66 == f"https://pbx.example.uz/prov/{TOKEN}/"
    assert out.has_admin_password is False and out.extra.yealink == ""


def test_plain_changes() -> None:
    payload = UpdateProvisioningPayload(updated_at=NOW, allowed_networks=["10.1.2.3/8", "10.0.0.0/8"],
                                        language="ru", sip_transport="tls", timezone="Europe/Moscow",
                                        ntp_server="", sip_server_host=None)
    assert sp.plain_changes(payload) == {
        "allowed_networks": ["10.0.0.0/8"], "language": "ru", "sip_transport": "tls", "timezone": "Europe/Moscow",
        "ntp_server": "pool.ntp.org", "sip_server_host": None}
    assert sp.plain_changes(UpdateProvisioningPayload(updated_at=NOW)) == {}
    with pytest.raises(ApiError) as exc:
        sp.plain_changes(UpdateProvisioningPayload(updated_at=NOW, timezone="Mars/Base"))
    assert (exc.value.code, exc.value.field) == ("validation_error", "timezone")
    with pytest.raises(ApiError) as exc:
        sp.plain_changes(UpdateProvisioningPayload(updated_at=NOW, sip_server_host="bad host!"))
    assert exc.value.field == "sip_server_host"


def test_extra_changes() -> None:
    current = {"yealink": "a = 1", "grandstream": "", "fanvil": ""}
    assert sp.extra_changes(UpdateProvisioningPayload(updated_at=NOW), current) is None
    payload = UpdateProvisioningPayload(updated_at=NOW, extra={"grandstream": "P2=1"})
    assert sp.extra_changes(payload, current) == {"yealink": "a = 1", "grandstream": "P2=1", "fanvil": ""}
    with pytest.raises(ApiError) as exc:
        sp.extra_changes(UpdateProvisioningPayload(updated_at=NOW, extra={"yealink": "bad line"}), current)
    assert (exc.value.status_code, exc.value.field) == (422, "extra.yealink")


# ------------------------------------------------------------------ /prov/ oqimi
def _req(filename="y000000000000.cfg", ip="10.0.0.5", ua="Yealink SIP-T46S 66.86.0.15", token=TOKEN):
    return ps.ProvRequest(token=token, filename=filename, ip=ip, user_agent=ua, host="pbx.uz")


def _guard(limit=20):
    return FailureGuard(lambda: 0.0, limit=limit)


def _logged(session):
    return [o for o in session.added if type(o).__name__ == "ProvisionRequest"]


@pytest.mark.asyncio
async def test_serve_bad_token_without_db_lookup() -> None:
    session = FakeSession()
    result = await ps.serve(session, _req(token="nope"), _guard())
    assert (result.status, result.reason) == (404, "bad_token") and session.executed == []
    log = _logged(session)[0]
    assert log.path == "/prov/***/y000000000000.cfg" and log.reason == "bad_token" and log.tenant_id is None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_serve_unknown_token_and_rate_limit(monkeypatch) -> None:
    alerts = []

    async def fake_alert(session, tenant_id, kind, key, text):
        alerts.append((tenant_id, kind, key, text))

    async def lang(*_a):
        return "uz"
    monkeypatch.setattr(ps, "raise_alert", fake_alert)
    monkeypatch.setattr(ps, "tenant_language", lang)
    guard = _guard(limit=2)
    r1 = await ps.serve(FakeSession(None), _req(), guard)
    r2 = await ps.serve(FakeSession(None, [TID, "t2"]), _req(), guard)
    r3 = await ps.serve(FakeSession(), _req(), guard)
    assert [r.reason for r in (r1, r2, r3)] == ["bad_token", "bad_token", "rate_limited"]
    assert r3.status == 403 and r3.body == b"Forbidden"
    assert [(a[0], a[1], a[2]) for a in alerts] == [(TID, "prov_bruteforce", "prov:10.0.0.5"),
                                                      ("t2", "prov_bruteforce", "prov:10.0.0.5")]
    assert "10.0.0.5" in alerts[0][3]
    assert (await ps.serve(FakeSession(_row()), _req(ip="10.0.0.6"), guard)).status == 200


@pytest.mark.asyncio
async def test_serve_network_denied_and_common_file() -> None:
    session = FakeSession(_row(allowed_networks=["192.168.1.0/24"]))
    result = await ps.serve(session, _req(), _guard())
    assert (result.status, result.reason) == (403, "network_denied")
    assert _logged(session)[0].tenant_id == TID
    result = await ps.serve(FakeSession(_row(language="ru")), _req(), _guard())
    assert result.status == 200 and b"lang.gui = Russian" in result.body and b"password" not in result.body


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "reason"), [("../etc/passwd", "not_found"), ("cfg000b82a40002", "legacy_binary"),
                                                  ("000000000000.cfg", "not_found")])
async def test_serve_bad_filenames(filename, reason) -> None:
    guard = _guard()
    result = await ps.serve(FakeSession(_row()), _req(filename=filename), guard)
    assert (result.status, result.reason) == (404, reason)
    assert not guard.is_blocked("10.0.0.5")


@pytest.mark.asyncio
async def test_serve_unknown_mac_is_discovered() -> None:
    session = FakeSession(_row(), None, 0, None)
    result = await ps.serve(session, _req(filename="805ec0a40001.cfg", ua="Yealink SIP-T46S 66.86.0.15"), _guard())
    assert (result.status, result.reason) == (404, "unknown_mac")
    upsert = session.executed[-1]
    assert "ON CONFLICT" in str(upsert.compile()).upper()
    params = upsert.compile().params
    assert (params["mac"], params["vendor"], params["model"], params["firmware"]) == (
        "805ec0a40001", "yealink", "T46S", "66.86.0.15")
    log = _logged(session)[0]
    assert (log.mac, log.vendor) == ("805ec0a40001", "yealink")


@pytest.mark.asyncio
async def test_serve_unknown_mac_vendor_mismatch_and_cap() -> None:
    session = FakeSession(_row(), None, 0, None)
    await ps.serve(session, _req(filename="805ec0a40001.cfg", ua="Fanvil X4U 2.1"), _guard())
    params = session.executed[-1].compile().params
    assert params["vendor"] == "fanvil" and params["model"] == "X4U"
    session = FakeSession(_row(), None, 0, None)
    await ps.serve(session, _req(filename="cfg000b82a40002.xml", ua="Yealink SIP-T46S 1"), _guard())
    params = session.executed[-1].compile().params
    assert (params["vendor"], params["model"], params["firmware"]) == ("grandstream", None, None)
    session = FakeSession(_row(), None, ps.MAX_DISCOVERED)
    result = await ps.serve(session, _req(filename="805ec0a40001.cfg"), _guard())
    assert result.reason == "unknown_mac" and len(session.executed) == 3  # upsert yo'q


@pytest.mark.asyncio
@pytest.mark.parametrize(("device", "filename"), [(_device(enabled=False), "805ec0a40001.cfg"),
                                                  (_device(vendor="grandstream"), "805ec0a40001.cfg")])
async def test_serve_device_not_served(device, filename) -> None:
    result = await ps.serve(FakeSession(_row(), device), _req(filename=filename), _guard())
    assert (result.status, result.reason) == (404, "not_found")


@pytest.mark.asyncio
async def test_serve_device_renders_and_updates(monkeypatch) -> None:
    async def code(*_a):
        return "t1"

    async def keys(_s, ids):
        return {ids[0]: [SimpleNamespace(idx=1, type="blf", value="102", label="B")]}

    async def passwords(_s, ids):
        return {ids[0]: "Sip!Secret1"}
    monkeypatch.setattr(ps, "get_tenant_code", code)
    monkeypatch.setattr(svc, "keys_by_device", keys)
    monkeypatch.setattr(svc, "sip_passwords", passwords)
    device = _device(config_hash=None, provisioned_at=None, firmware=None)
    session = FakeSession(_row(sip_server_host="sip.pbx.uz"), device, objects={("Extension", "e1"): _ext()})
    result = await ps.serve(session, _req(filename="805ec0a40001.cfg"), _guard())
    assert (result.status, result.reason, result.content_type) == (200, "ok", "text/plain")
    assert b"account.1.password = Sip!Secret1" in result.body and b"linekey.1.value = 102" in result.body
    assert len(device.config_hash) == 64 and device.firmware == "66.86.0.15" and device.last_ip == "10.0.0.5"
    log = _logged(session)[0]
    assert "Sip!Secret1" not in log.path and log.status_code == 200 and log.reason == "ok"


@pytest.mark.asyncio
async def test_purge_requests_once() -> None:
    class S(FakeSession):
        async def execute(self, stmt, params=None):
            self.executed.append(stmt)
            return SimpleNamespace(rowcount=3)
    session = S()
    assert await prov_api.purge_requests_once(lambda: session, NOW) == 3
    assert session.commits == 1 and "provision_requests.at <" in str(session.executed[0])


def test_result_helper() -> None:
    assert isinstance(_Result(1).scalar_one(), int)
    assert ps._fail("unknown_mac") == ps.ProvResult(404, "unknown_mac", b"Not Found")
    assert ps._fail("network_denied").status == 403
