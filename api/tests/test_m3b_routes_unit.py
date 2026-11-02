"""M3b — webhook yetkazuvchisi (httpx MockTransport), dispatch holat o'tishi, router yordamchilari (bazasiz)."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.api import public
from app.api.v1 import integrations as integ
from app.api.v1.settings_integrations import normalize_base_url, recording_settings_out
from app.core.errors import ApiError
from app.schemas_integrations import OriginatePayload
from app.services import recordings
from app.services.integrations import dispatch, ssrf
from app.services.integrations.providers import DeliveryContext, DeliveryResult, EventView, SubscriptionView
from app.services.integrations.webhook import WebhookProvider

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _ctx(url="http://10.0.0.5/hook", secret="whsec_x"):
    sub = SubscriptionView(id="s1", tenant_id="t", kind="webhook", name="n", config={"url": url}, secret=secret)
    ev = EventView(id="e1", type="call.ended", call_id="1.1", payload={"id": "e1", "type": "call.ended"})
    return DeliveryContext(delivery_id="d1", attempt=1, subscription=sub, event=ev, session=None)


# ------------------------------------------------------------ webhook yetkazuvchisi
@pytest.mark.asyncio
async def test_webhook_provider_signs_and_succeeds():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"], seen["body"] = request.headers, request.content
        return httpx.Response(200, text="ok")

    result = await WebhookProvider(url_check=lambda u: None, transport=httpx.MockTransport(handler)).deliver(_ctx())
    assert result.ok and result.status_code == 200 and result.response_body == "ok"
    sig = dict(p.split("=", 1) for p in seen["headers"]["x-innova-signature"].split(","))
    expected = hmac.new(b"whsec_x", f"{sig['t']}.".encode() + seen["body"], hashlib.sha256).hexdigest()
    assert sig["v1"] == expected
    assert seen["headers"]["x-innova-delivery"] == "d1" and seen["headers"]["x-innova-event"] == "call.ended"
    assert json.loads(seen["body"]) == {"id": "e1", "type": "call.ended"}


@pytest.mark.asyncio
async def test_webhook_provider_does_not_follow_redirect_and_caps_body():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/"}, text="x" * 5000)

    result = await WebhookProvider(url_check=lambda u: None, transport=httpx.MockTransport(handler)).deliver(_ctx())
    assert not result.ok and result.status_code == 302 and len(result.response_body) == 1024


@pytest.mark.asyncio
async def test_webhook_provider_forbidden_url_is_permanent():
    def deny(url):
        raise ssrf.UrlForbidden("address")

    result = await WebhookProvider(url_check=deny, transport=httpx.MockTransport(lambda r: httpx.Response(200))
                                   ).deliver(_ctx())
    assert (result.ok, result.permanent, result.error) == (False, True, "url_forbidden:address")


@pytest.mark.asyncio
async def test_webhook_provider_network_error_is_transient_and_masks_secret():
    def handler(request):
        raise httpx.ConnectError("boom whsec_x")

    result = await WebhookProvider(url_check=lambda u: None, transport=httpx.MockTransport(handler)).deliver(_ctx())
    assert not result.ok and not result.permanent and "whsec_x" not in result.error


# ------------------------------------------------------------ dispatch holat o'tishi
def _delivery(attempts=0):
    return SimpleNamespace(attempts=attempts, status="pending", next_attempt_at=NOW, delivered_at=None,
                           last_attempt_at=None, last_status_code=None, last_error=None, response_body=None)


def test_apply_success_and_retry(monkeypatch):
    monkeypatch.setattr(dispatch.settings, "integration_retry_schedule_s", "2,2,2")
    row = _delivery()
    dispatch._apply(row, DeliveryResult(ok=False, status_code=500, response_body="err"), NOW)
    assert (row.status, row.attempts, row.next_attempt_at, row.last_error) == (
        "pending", 1, NOW + timedelta(seconds=2), "HTTP 500")
    dispatch._apply(row, DeliveryResult(ok=True, status_code=204), NOW)
    assert (row.status, row.attempts, row.delivered_at, row.last_error) == ("delivered", 2, NOW, None)


def test_apply_dead_after_schedule(monkeypatch):
    monkeypatch.setattr(dispatch.settings, "integration_retry_schedule_s", "2,2")
    row = _delivery(attempts=2)
    dispatch._apply(row, DeliveryResult(ok=False, error="ConnectError"), NOW)
    assert (row.status, row.attempts, row.last_error) == ("dead", 3, "ConnectError")


@pytest.mark.asyncio
async def test_update_subscription_success_clears_failing():
    sub = SimpleNamespace(failing_since=NOW, last_success_at=None)
    await dispatch._update_subscription(None, sub, DeliveryResult(ok=True), NOW)
    assert sub.failing_since is None and sub.last_success_at == NOW


@pytest.mark.asyncio
async def test_update_subscription_marks_failing_without_disable(monkeypatch):
    sub = SimpleNamespace(failing_since=None, enabled=True)
    await dispatch._update_subscription(None, sub, DeliveryResult(ok=False), NOW)
    assert sub.failing_since == NOW and sub.enabled


@pytest.mark.asyncio
async def test_update_subscription_auto_disables_after_24h(monkeypatch):
    calls = []

    async def fake_alert(session, tenant_id, kind, key, text):
        calls.append((kind, key))

    async def fake_lang(session, tenant_id):
        return "uz"

    import app.services.alerts as alerts
    monkeypatch.setattr(alerts, "raise_alert", fake_alert)
    monkeypatch.setattr(alerts, "tenant_language", fake_lang)
    sub = SimpleNamespace(id="s1", tenant_id="t", name="CRM", enabled=True, disabled_reason=None, updated_at=None,
                          failing_since=NOW - timedelta(hours=25))
    await dispatch._update_subscription(None, sub, DeliveryResult(ok=False, status_code=500), NOW)
    assert not sub.enabled and "500" in sub.disabled_reason and calls == [("webhook_disabled", "s1")]


# ------------------------------------------------------------ admin router yordamchilari
def test_delivery_out_maps_web_names():
    row = SimpleNamespace(id="d", event_id="e", call_id="c", status="pending", attempts=2, next_attempt_at=NOW,
                          last_attempt_at=NOW, last_status_code=500, last_error="HTTP 500", response_body="x",
                          delivered_at=None, created_at=NOW)
    out = integ.delivery_out(row, "call.ended")
    assert (out.http_status, out.next_retry_at, out.event_type) == (500, NOW, "call.ended")
    row.status = "dead"
    assert integ.delivery_out(row, "call.ended").next_retry_at is None


def test_webhook_out_never_exposes_secret():
    sub = SimpleNamespace(id="s", name="n", config={"url": "http://x"}, events=["call.ended"], include_internal=False,
                          enabled=True, secret_enc="ENC", disabled_reason=None, failing_since=None,
                          last_success_at=None, created_at=NOW, updated_at=NOW)
    out = integ.webhook_out(sub).model_dump()
    assert out["has_secret"] is True and "ENC" not in json.dumps(out, default=str)


def test_new_webhook_secret_unique():
    a, b = integ.new_webhook_secret(), integ.new_webhook_secret()
    assert a != b and a.startswith("whsec_") and len(a) > 40


@pytest.mark.asyncio
async def test_check_webhook_url_maps_to_422(monkeypatch):
    def deny(url):
        raise ssrf.UrlForbidden("address")

    monkeypatch.setattr(ssrf, "check_url_default", deny)
    with pytest.raises(ApiError) as exc:
        await integ.check_webhook_url("http://127.0.0.1/")
    assert (exc.value.status_code, exc.value.code) == (422, "url_forbidden")
    monkeypatch.setattr(ssrf, "check_url_default", lambda u: None)
    assert await integ.check_webhook_url("  http://10.0.0.9/h ") == "http://10.0.0.9/h"


def test_apply_webhook_changes_reenable_clears_reason():
    sub = SimpleNamespace(name="a", events=[], include_internal=False, enabled=False, config={"url": "u"},
                          disabled_reason="x", failing_since=NOW)
    integ._apply_webhook_changes(sub, {"enabled": True, "url": "http://n", "name": "b"})
    assert (sub.enabled, sub.disabled_reason, sub.failing_since, sub.config, sub.name) == (
        True, None, None, {"url": "http://n"}, "b")


# ------------------------------------------------------------ sozlamalar
@pytest.mark.parametrize("raw,expected", [("", ""), (None, ""), (" https://pbx.example.uz/ ", "https://pbx.example.uz"),
                                          ("http://10.0.0.2:8080/pbx", "http://10.0.0.2:8080/pbx")])
def test_normalize_base_url_ok(raw, expected):
    assert normalize_base_url(raw) == expected


@pytest.mark.parametrize("raw", ["ftp://x", "https://", "https://x/?a=1", "https://u:p@x", "https://x/#f"])
def test_normalize_base_url_rejects(raw):
    with pytest.raises(ApiError) as exc:
        normalize_base_url(raw)
    assert exc.value.field == "public_base_url"


def test_recording_settings_out_defaults():
    row = SimpleNamespace(recording={}, recording_retention_days=None, updated_at=NOW)
    out = recording_settings_out(row)
    assert (out.external_only, out.retention_days, out.format) == (False, 365, "wav")


# ------------------------------------------------------------ ochiq API
def test_bearer_key():
    req = lambda h: SimpleNamespace(headers=h)
    assert public.bearer_key(req({"authorization": "Bearer ipk_x"})) == "ipk_x"
    assert public.bearer_key(req({"authorization": "Basic abc"})) is None
    assert public.bearer_key(req({"authorization": "Bearer "})) is None
    assert public.bearer_key(req({})) is None


def test_cursor_roundtrip_and_bad():
    cur = public.encode_cursor(NOW, "1700.5")
    assert public.decode_cursor(cur) == (NOW, "1700.5")
    for bad in ("!!!", "bm9waXBl"):
        with pytest.raises(ApiError) as exc:
            public.decode_cursor(bad)
        assert exc.value.code == "bad_cursor"


def test_originate_validation_errors():
    with pytest.raises(ApiError) as exc:
        public._validated(OriginatePayload(extension="101", to="998\r\nAction: Command"))
    assert (exc.value.status_code, exc.value.code) == (422, "invalid_number")
    with pytest.raises(ApiError) as exc:
        public._validated(OriginatePayload(extension="101", to="99890", external_id="a b"))
    assert exc.value.code == "invalid_external_id"
    assert public._validated(OriginatePayload(extension="101", to="+998 90 123-45-67", external_id="crm:1")) == (
        "998901234567", "crm:1")


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Session:
    def __init__(self, *values):
        self.values = list(values)
        self.commits = 0

    async def execute(self, stmt):
        return _Result(self.values.pop(0))

    async def commit(self):
        self.commits += 1


def _key_row(**kw):
    from app.services.api_keys import generate_key

    new = generate_key()
    row = SimpleNamespace(id="k1", prefix=new.prefix, key_hash=new.key_hash, scopes=["calls:read"], tenant_id="t1",
                          expires_at=None, revoked_at=None, last_used_at=None)
    for k, v in kw.items():
        setattr(row, k, v)
    return new.plaintext, row


@pytest.mark.asyncio
async def test_authenticate_ok_touches_last_used():
    plaintext, row = _key_row()
    session = _Session(row, "t1code")
    ctx = await public.authenticate(session, plaintext, "calls:read")
    assert (ctx.tenant_code, ctx.prefix, session.commits) == ("t1code", row.prefix, 1)
    assert row.last_used_at is not None


@pytest.mark.asyncio
async def test_authenticate_errors():
    with pytest.raises(ApiError) as exc:
        await public.authenticate(_Session(), None, "calls:read")
    assert (exc.value.status_code, exc.value.code) == (401, "invalid_api_key")
    plaintext, row = _key_row(revoked_at=NOW)
    with pytest.raises(ApiError) as exc:
        await public.authenticate(_Session(row), plaintext, "calls:read")
    assert exc.value.code == "invalid_api_key"
    plaintext, row = _key_row()
    with pytest.raises(ApiError) as exc:
        await public.authenticate(_Session(row), plaintext[:-1] + ("A" if plaintext[-1] != "A" else "B"), "calls:read")
    assert exc.value.code == "invalid_api_key"
    plaintext, row = _key_row(id="k2")
    with pytest.raises(ApiError) as exc:
        await public.authenticate(_Session(row), plaintext, "calls:originate")
    assert (exc.value.status_code, exc.value.code) == (403, "insufficient_scope")


@pytest.mark.asyncio
async def test_authenticate_rate_limited(monkeypatch):
    monkeypatch.setattr(public.settings, "api_key_rate_limit_per_min", 2)
    plaintext, row = _key_row(id="k-rl")
    for _ in range(2):
        await public.authenticate(_Session(row, "c"), plaintext, "calls:read")
    with pytest.raises(ApiError) as exc:
        await public.authenticate(_Session(row), plaintext, "calls:read")
    assert (exc.value.status_code, exc.value.code) == (429, "rate_limited")


# ------------------------------------------------------------ yozuvga kirish
def test_leg_mentions():
    # Eski (tenant-prefiksli) kanal nomi — tarixiy CDR yozuvlarida hamon uchraydi.
    kw = dict(src="998901", dst="s", channel="PJSIP/t1-trunk-x-01", dstchannel="PJSIP/t1-101-0000002a")
    assert recordings.leg_mentions("101", "t1", **kw)
    assert not recordings.leg_mentions("10", "t1", **kw)
    assert recordings.leg_mentions("998901", "t1", **kw)
    assert not recordings.leg_mentions("102", "t1", src=None, dst=None, channel=None, dstchannel=None)


def test_leg_mentions_new_format_channel():
    # Yangi (prefiksiz, m-sip-login-plain-number) kanal nomi.
    kw = dict(src="998901", dst="s", channel="PJSIP/t1-trunk-x-01", dstchannel="PJSIP/101-0000002a")
    assert recordings.leg_mentions("101", "t1", **kw)
    assert not recordings.leg_mentions("102", "t1", **kw)


def test_link_is_valid(monkeypatch):
    monkeypatch.setattr(public.settings, "secret_key", "s" * 40)
    exp = int(datetime.now(timezone.utc).timestamp()) + 60
    sig = recordings.link_signature("r1", exp, "s" * 40)
    assert public.link_is_valid("r1", exp, sig)
    assert not public.link_is_valid("r2", exp, sig)
    assert not public.link_is_valid("r1", exp - 120, recordings.link_signature("r1", exp - 120, "s" * 40))


@pytest.mark.asyncio
async def test_public_extensions_lists_numbers_without_secrets(monkeypatch):
    # Regress: `_bulk_extension_out` imzosi o'zgarganda public API 500 berardi (m3b isboti ushladi).
    ext = SimpleNamespace(number="101", name="Ali", enabled=True)

    class _Res:
        def scalars(self):
            return SimpleNamespace(all=lambda: [ext])

    class _Session:
        async def execute(self, _stmt):
            return _Res()

    async def fake_bulk(ami, items):
        assert ami == "AMI" and items == [ext]
        return [SimpleNamespace(number="101", name="Ali", enabled=True, status="online")]

    monkeypatch.setattr(public, "_bulk_extension_out", fake_bulk)
    out = await public.public_extensions(session=_Session(), ami="AMI", key=SimpleNamespace(tenant_id="t"))
    assert [i.model_dump() for i in out["items"]] == [{"number": "101", "name": "Ali", "enabled": True, "status": "online"}]
