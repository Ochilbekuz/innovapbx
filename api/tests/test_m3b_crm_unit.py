"""M3b §5 — CRM (Bitrix24 / amoCRM) birlik testlari: xarita qoidalari, xato tasnifi, sirlar, hook, 1C namunalar."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest

from app.api import public_crm
from app.api.v1 import crm as crm_routes
from app.api.v1 import onec
from app.core.errors import ApiError
from app.db.models import CrmCallLink
from app.schemas_crm import CrmUserMapEntryIn, UpdateAmoPayload, UpdateBitrixPayload
from app.services import crm_settings
from app.services.audit import mask_secrets
from app.services.integrations import amocrm, bitrix24, crm, dispatch
from app.services.integrations.crm import CrmUserInfo
from app.services.integrations.providers import DeliveryContext, DeliveryResult, EventView, SubscriptionView

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
HOOK = "http://10.0.0.7/rest/1/abc123/"
LINKEDID = "1761739200.42"


# ------------------------------------------------------------ soxta muhit
class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.value or []))

    def all(self):
        return list(self.value or [])


class CrmSession:
    """`execute` — navbat (bo'sh bo'lsa xarita qatorlari); `get(CrmCallLink)` — bog'lanishlar lug'ati."""

    def __init__(self, *results, map_rows=(), links=None, objects=None):
        self.results, self.map_rows = list(results), list(map_rows)
        self.links = {} if links is None else links
        self.objects = objects or {}
        self.added, self.executed, self.commits = [], [], 0

    async def execute(self, stmt, params=None):
        self.executed.append(stmt)
        return _Result(self.results.pop(0) if self.results else self.map_rows)

    async def get(self, model, key):
        if model is CrmCallLink:
            return self.links.get(key)
        return self.objects.get(model.__name__)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, CrmCallLink):
            self.links[(obj.tenant_id, obj.provider, obj.linkedid)] = obj

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


class FakeCrm:
    """httpx MockTransport: so'rovlarni yozadi; `fail` — navbatdagi javoblar (status, tana) dan oldin."""

    def __init__(self, responses=None, fail=()):
        self.requests: list[tuple[str, dict]] = []
        self.responses = responses or {}
        self.fail = list(fail)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = request.content.decode()
        parsed = json.loads(body) if body.startswith("[") or body.startswith("{") else \
            {k: v[0] for k, v in parse_qs(body).items()}
        self.requests.append((path, parsed))
        if self.fail:
            status, payload, headers = self.fail.pop(0)
            return httpx.Response(status, json=payload, headers=headers)
        for suffix, (status, payload) in self.responses.items():
            if path.endswith(suffix):
                return httpx.Response(status, json=payload)
        return httpx.Response(200, json={"result": True})

    def methods(self):
        return [p.rsplit("/", 1)[-1].removesuffix(".json") for p, _ in self.requests]

    def last(self, method):
        return next(b for p, b in reversed(self.requests) if p.endswith(f"/{method}.json"))


class NoWait(crm.RateLimiter):
    def __init__(self):
        super().__init__(1000)

    async def wait(self, key):
        return None


def _bitrix(fake: FakeCrm, clock=lambda: NOW) -> bitrix24.Bitrix24Provider:
    return bitrix24.Bitrix24Provider(url_check=lambda url: None, transport=httpx.MockTransport(fake),
                                     limiter=NoWait(), clock=clock)


def _amo(fake: FakeCrm) -> amocrm.AmoCrmProvider:
    return amocrm.AmoCrmProvider(url_check=lambda url: None, transport=httpx.MockTransport(fake), limiter=NoWait())


def _call(**kw):
    call = {"id": LINKEDID, "direction": "inbound", "from": "+998901234567", "to": "712000000", "did": "712000000",
            "extension": "101", "status": "answered", "billsec": 42, "answered_by": None,
            "started_at": "2026-10-29T11:59:50Z", "recordings": []}
    call.update(kw)
    return call


def _ctx(session, event_type, call, *, kind="bitrix24", config=None, secret=None, occurred_at=NOW):
    secrets_raw = secret if secret is not None else crm.dump_secrets(
        {"webhook_url": HOOK} if kind == "bitrix24" else {"token": "tok-SECRET"})
    sub = SubscriptionView(id="s1", tenant_id="t1", kind=kind, name=kind, config=config or {}, secret=secrets_raw)
    payload = {"id": "e1", "type": event_type, "occurred_at": occurred_at.isoformat(), "call": call}
    ev = EventView(id="e1", type=event_type, call_id=call.get("id"), payload=payload)
    return DeliveryContext(delivery_id="d1", attempt=1, subscription=sub, event=ev, session=session)


REGISTER_OK = {"telephony.externalcall.register.json": (200, {"result": {"CALL_ID": "externalCall.X1"}})}
USERS = [("101", "7"), ("103", "9")]


# ------------------------------------------------------------ Bitrix24 sof qoidalar
@pytest.mark.parametrize("status,code", [("answered", "200"), ("missed", "304"), ("busy", "486"),
                                         ("failed", "603"), (None, "603")])
def test_bitrix_status_codes(status, code):
    assert bitrix24.status_code(status) == code


def test_bitrix_time_uses_numeric_offset():
    assert bitrix24.bitrix_time(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)) == "2026-01-02T03:04:05+00:00"


def test_register_params_inbound_and_outbound():
    params = bitrix24.register_params(_call(), user_id="7", create_lead=True, show=True, started_at=NOW)
    assert params == {"USER_ID": "7", "PHONE_NUMBER": "+998901234567", "TYPE": "2",
                      "CALL_START_DATE": "2026-10-29T12:00:00+00:00", "CRM_CREATE": "1", "SHOW": "1",
                      "EXTERNAL_CALL_ID": LINKEDID, "LINE_NUMBER": "712000000"}
    out = bitrix24.register_params(_call(direction="outbound", did=None, to="998935550000"), user_id="7",
                                   create_lead=False, show=False, started_at=NOW)
    assert (out["TYPE"], out["PHONE_NUMBER"], out["CRM_CREATE"], out["SHOW"]) == ("1", "998935550000", "0", "0")
    assert "LINE_NUMBER" not in out


def test_finish_params_record_url_and_duration():
    call = _call(billsec=17.9, recordings=[{"url": None}, {"url": "https://pbx/r/1"}, {"url": "https://pbx/r/2"}])
    assert bitrix24.finish_params(call, call_id="C", user_id="9", upload_records=False) == {
        "CALL_ID": "C", "USER_ID": "9", "DURATION": "17", "STATUS_CODE": "200", "ADD_TO_CHAT": "1",
        "RECORD_URL": "https://pbx/r/1"}
    assert "RECORD_URL" not in bitrix24.finish_params(_call(), call_id="C", user_id="9", upload_records=False)
    # M-CRM §2: `upload_records=True` — `RECORD_URL` HECH QACHON (fayl alohida `attachRecord` orqali).
    assert "RECORD_URL" not in bitrix24.finish_params(call, call_id="C", user_id="9", upload_records=True)


def test_is_late():
    assert bitrix24.is_late(NOW - timedelta(seconds=21), NOW, 20)
    assert not bitrix24.is_late(NOW - timedelta(seconds=20), NOW, 20)
    assert not bitrix24.is_late(None, NOW, 20)


@pytest.mark.parametrize("raw", ["https://b24.uz/rest/1/abc", "http://10.0.0.7/rest/12/Ab_9/"])
def test_normalize_webhook_url_ok(raw):
    assert bitrix24.normalize_webhook_url(raw).endswith("/")


@pytest.mark.parametrize("raw", ["ftp://b24.uz/rest/1/abc/", "https://b24.uz/rest/x/abc/", "https://b24.uz/api/",
                                 "https://b24.uz/rest/1/abc/?a=1", "not a url"])
def test_normalize_webhook_url_rejects(raw):
    with pytest.raises(bitrix24.InvalidWebhookUrl):
        bitrix24.normalize_webhook_url(raw)


def test_classify_bitrix_envelope_and_http():
    assert bitrix24.classify(200, {}, {"result": 1}, what="m") is None
    rate = bitrix24.classify(503, {}, {"error": "QUERY_LIMIT_EXCEEDED"}, what="m").result
    assert rate.retry_after_s == crm.DEFAULT_RETRY_AFTER_S and not rate.permanent
    auth = bitrix24.classify(401, {}, {"error": "expired_token"}, what="m").result
    assert not auth.permanent and auth.retry_after_s is None
    assert not bitrix24.classify(503, {}, {"error": "WEIRD"}, what="m").result.permanent
    assert bitrix24.classify(200, {}, {"error": "WEIRD"}, what="m").result.permanent
    assert not bitrix24.classify(503, {}, None, what="m").result.permanent
    assert bitrix24.classify(400, {}, None, what="m").result.permanent


def test_user_info_and_settings_parse():
    info = bitrix24.user_info({"ID": 7, "NAME": "Ali", "LAST_NAME": "Valiyev", "UF_PHONE_INNER": " 101 "})
    assert info == CrmUserInfo(id="7", name="Ali Valiyev", inner_phone="101")
    assert bitrix24.user_info({"ID": 8, "EMAIL": "a@b"}).name == "a@b"
    parsed = bitrix24.BitrixSettings.parse({"popup_max_delay_s": 0, "default_user_id": ""}, {})
    assert (parsed.popup_max_delay_s, parsed.default_user_id, parsed.create_lead) == (20, None, True)


# ------------------------------------------------------------ Bitrix24 oqim (§7.5)
async def test_bitrix_queue_flow_register_show_hide_finish():
    fake = FakeCrm(REGISTER_OK)
    provider, session = _bitrix(fake), CrmSession(map_rows=USERS)
    assert (await provider.deliver(_ctx(session, "call.ringing", _call(extension="101")))).ok
    assert (await provider.deliver(_ctx(session, "call.ringing", _call(extension="103")))).ok
    assert (await provider.deliver(_ctx(session, "call.ringing", _call(extension="103")))).response_body \
        == "skipped:shown"
    assert (await provider.deliver(_ctx(session, "call.answered", _call(extension="103")))).ok
    ended = _call(extension="103", answered_by="103", recordings=[{"url": "https://pbx/r/1"}])
    result = await provider.deliver(_ctx(session, "call.ended", ended, config={"upload_records": False}))
    assert result == DeliveryResult(ok=True, status_code=200, response_body="finish:externalCall.X1")
    assert fake.methods() == ["telephony.externalcall.register", "telephony.externalcall.show",
                              "telephony.externalcall.hide", "telephony.externalcall.finish"]
    assert fake.last("telephony.externalcall.register")["USER_ID"] == "7"
    assert fake.last("telephony.externalcall.show") == {"CALL_ID": "externalCall.X1", "USER_ID": "9"}
    assert fake.last("telephony.externalcall.hide") == {"CALL_ID": "externalCall.X1", "USER_ID": "7"}
    finish = fake.last("telephony.externalcall.finish")
    assert (finish["USER_ID"], finish["STATUS_CODE"], finish["DURATION"], finish["RECORD_URL"]) == \
        ("9", "200", "42", "https://pbx/r/1")
    link = session.links[("t1", "bitrix24", LINKEDID)]
    assert (link.origin, link.user_id, link.shown_users) == ("pbx", "7", ["7", "9"])


async def test_bitrix_late_ringing_registers_hidden_and_no_show():
    fake = FakeCrm(REGISTER_OK)
    provider, session = _bitrix(fake), CrmSession(map_rows=USERS)
    late = NOW - timedelta(seconds=60)
    await provider.deliver(_ctx(session, "call.ringing", _call(), occurred_at=late))
    await provider.deliver(_ctx(session, "call.ringing", _call(extension="103"), occurred_at=late))
    assert fake.methods() == ["telephony.externalcall.register"]
    assert fake.last("telephony.externalcall.register")["SHOW"] == "0"
    assert fake.last("telephony.externalcall.register")["CALL_START_DATE"] == "2026-10-29T11:59:00+00:00"


async def test_bitrix_finish_without_register_registers_first():
    fake = FakeCrm(REGISTER_OK)
    provider = _bitrix(fake)
    result = await provider.deliver(_ctx(CrmSession(map_rows=USERS), "call.ended", _call(status="missed"),
                                         config={"upload_records": False}))
    assert result.ok
    assert fake.methods() == ["telephony.externalcall.register", "telephony.externalcall.finish"]
    assert fake.last("telephony.externalcall.register")["SHOW"] == "0"
    finish = fake.last("telephony.externalcall.finish")
    assert (finish["STATUS_CODE"], finish["USER_ID"]) == ("304", "7")


async def test_bitrix_outbound_type_1():
    fake = FakeCrm(REGISTER_OK)
    call = _call(direction="outbound", to="998935550000", **{"from": "101"})
    await _bitrix(fake).deliver(_ctx(CrmSession(map_rows=USERS), "call.ended", call,
                                     config={"upload_records": False}))
    assert fake.last("telephony.externalcall.register")["TYPE"] == "1"
    assert fake.last("telephony.externalcall.register")["PHONE_NUMBER"] == "998935550000"


@pytest.mark.parametrize("event", ["call.ringing", "call.answered", "call.ended"])
async def test_bitrix_internal_call_sends_nothing(event):
    fake = FakeCrm(REGISTER_OK)
    result = await _bitrix(fake).deliver(_ctx(CrmSession(map_rows=USERS), event, _call(direction="internal")))
    assert (result.ok, result.response_body, fake.requests) == (True, "skipped", [])


async def test_bitrix_unknown_event_skipped():
    fake = FakeCrm()
    result = await _bitrix(fake).deliver(_ctx(CrmSession(), "call.held", _call()))
    assert (result.response_body, fake.requests) == ("skipped", [])


async def test_bitrix_unmapped_uses_default_user():
    fake = FakeCrm(REGISTER_OK)
    ctx = _ctx(CrmSession(map_rows=[]), "call.ringing", _call(extension="555"), config={"default_user_id": "1"})
    assert (await _bitrix(fake).deliver(ctx)).ok
    assert fake.last("telephony.externalcall.register")["USER_ID"] == "1"


async def test_bitrix_no_user_and_no_default_skips():
    fake = FakeCrm(REGISTER_OK)
    provider = _bitrix(fake)
    assert (await provider.deliver(_ctx(CrmSession(), "call.ringing", _call()))).response_body == "skipped:no_user"
    assert (await provider.deliver(_ctx(CrmSession(), "call.ended", _call()))).response_body == "skipped:no_user"
    assert (await provider.deliver(_ctx(CrmSession(), "call.answered", _call()))).response_body == "skipped:no_link"
    assert fake.requests == []


async def test_bitrix_crm_origin_link_prevents_second_register():
    fake = FakeCrm(REGISTER_OK)
    link = CrmCallLink(tenant_id="t1", provider="bitrix24", linkedid=LINKEDID, external_call_id="B-CALL",
                       origin="crm", user_id="7", shown_users=["7"])
    session = CrmSession(map_rows=USERS, links={("t1", "bitrix24", LINKEDID): link})
    out = _call(direction="outbound", to="998935550000", extension="101")
    await _bitrix(fake).deliver(_ctx(session, "call.ringing", out))
    await _bitrix(fake).deliver(_ctx(session, "call.ended", out, config={"upload_records": False}))
    assert fake.methods() == ["telephony.externalcall.finish"]
    assert fake.last("telephony.externalcall.finish")["CALL_ID"] == "B-CALL"


async def test_bitrix_503_is_transient_then_keeps_link():
    fake = FakeCrm(REGISTER_OK, fail=[(503, {}, {})])
    provider, session = _bitrix(fake), CrmSession(map_rows=USERS)
    first = await provider.deliver(_ctx(session, "call.ringing", _call()))
    assert (first.ok, first.permanent, first.status_code) == (False, False, 503)
    assert (await provider.deliver(_ctx(session, "call.ringing", _call()))).ok


async def test_bitrix_register_without_call_id_is_permanent():
    fake = FakeCrm({"telephony.externalcall.register.json": (200, {"result": {}})})
    result = await _bitrix(fake).deliver(_ctx(CrmSession(map_rows=USERS), "call.ringing", _call()))
    assert (result.ok, result.permanent) == (False, True)


async def test_bitrix_not_configured_and_ssrf_are_permanent():
    fake = FakeCrm()
    result = await _bitrix(fake).deliver(_ctx(CrmSession(), "call.ringing", _call(), secret="{}"))
    assert result.permanent and "not_configured" in result.error

    def forbid(url):
        raise bitrix24.ssrf.UrlForbidden("loopback")

    provider = bitrix24.Bitrix24Provider(url_check=forbid, transport=httpx.MockTransport(fake), limiter=NoWait())
    result = await provider.deliver(_ctx(CrmSession(map_rows=USERS), "call.ringing", _call()))
    assert result.permanent and result.error == "url_forbidden:loopback" and fake.requests == []


async def test_bitrix_network_error_hides_webhook_secret():
    def boom(request):
        raise httpx.ConnectError(f"cannot connect {request.url}")

    provider = bitrix24.Bitrix24Provider(url_check=lambda u: None, transport=httpx.MockTransport(boom),
                                         limiter=NoWait())
    result = await provider.deliver(_ctx(CrmSession(map_rows=USERS), "call.ringing", _call()))
    assert not result.permanent and "abc123" not in result.error and "10.0.0.7" not in result.error


async def test_bitrix_users_paginates():
    pages = iter([{"result": [{"ID": 7, "NAME": "A", "UF_PHONE_INNER": "101"}], "next": 50},
                  {"result": [{"ID": 9, "NAME": "B"}]}])
    fake = FakeCrm()

    def handler(request):
        fake(request)
        return httpx.Response(200, json=next(pages))

    client = bitrix24.Bitrix24Provider(url_check=lambda u: None, transport=httpx.MockTransport(handler),
                                       limiter=NoWait()).client("s1", HOOK)
    users = await client.users()
    assert [u.id for u in users] == ["7", "9"] and [b["start"] for _, b in fake.requests] == ["0", "50"]


# ------------------------------------------------------------ amoCRM (§7.6)
def test_amo_call_body_fields():
    call = _call(recordings=[{"url": "https://pbx/r/1"}])
    body = amocrm.call_body(call, responsible_user_id="55")
    assert body == {"direction": "inbound", "uniq": LINKEDID, "duration": 42, "source": "Innova PBX",
                    "phone": "+998901234567", "call_result": "Suhbat bo'ldi", "call_status": 4,
                    "created_at": int(datetime(2026, 10, 29, 11, 59, 50, tzinfo=timezone.utc).timestamp()),
                    "link": "https://pbx/r/1", "responsible_user_id": 55}
    assert amocrm.call_body(_call(status="busy", direction="outbound", to="777"), responsible_user_id=None)[
        "call_status"] == 7
    missed = amocrm.call_body(_call(status="missed"), responsible_user_id=None)
    assert (missed["call_status"], "responsible_user_id" in missed, "link" in missed) == (6, False, False)


def test_amo_unsorted_body():
    body = amocrm.unsorted_body(_call(recordings=[{"url": "https://pbx/r/1"}]))
    assert body["source_uid"] == LINKEDID and body["metadata"]["from"] == "+998901234567"
    assert body["metadata"]["link"] == "https://pbx/r/1"
    assert body["_embedded"]["contacts"] == [{"name": "+998901234567"}]


@pytest.mark.parametrize("status,body,missing", [
    (404, None, True), (200, {"_embedded": {"errors": [{"msg": "x"}], "calls": []}}, True),
    (400, {"_embedded": {"errors": [{"msg": "x"}]}}, True), (200, {"_embedded": {"calls": [{"id": 1}]}}, False),
    (200, {"_embedded": {"errors": [1], "calls": [{"id": 1}]}}, False), (500, {"_embedded": {"errors": [1]}}, False),
    (200, None, False)])
def test_amo_contact_missing(status, body, missing):
    assert amocrm.contact_missing(status, body) is missing


@pytest.mark.parametrize("raw", ["https://firm.amocrm.ru/", "http://10.0.0.8:8080"])
def test_amo_normalize_base_url_ok(raw):
    assert not amocrm.normalize_base_url(raw).endswith("/")


@pytest.mark.parametrize("raw", ["firm.amocrm.ru", "https://firm.amocrm.ru/api", "https://u:p@firm.amocrm.ru",
                                 "https://firm.amocrm.ru?x=1", "ftp://firm.amocrm.ru"])
def test_amo_normalize_base_url_rejects(raw):
    with pytest.raises(amocrm.InvalidBaseUrl):
        amocrm.normalize_base_url(raw)


AMO_CONFIG = {"base_url": "http://10.0.0.8", "unsorted_for_unknown": True, "default_user_id": "1"}


async def test_amo_known_contact_logs_call_with_bearer():
    seen = []
    fake = FakeCrm({"/api/v4/calls": (200, {"_embedded": {"calls": [{"id": 1}]}})})

    def handler(request):
        seen.append(request.headers["authorization"])
        return fake(request)

    provider = amocrm.AmoCrmProvider(url_check=lambda u: None, transport=httpx.MockTransport(handler),
                                     limiter=NoWait())
    ctx = _ctx(CrmSession(map_rows=[("103", "55")]), "call.ended", _call(answered_by="103"), kind="amocrm",
               config=AMO_CONFIG)
    result = await provider.deliver(ctx)
    assert (result.ok, result.response_body) == (True, "calls")
    path, body = fake.requests[0]
    assert path == "/api/v4/calls" and body[0]["responsible_user_id"] == 55 and body[0]["call_status"] == 4
    assert seen == ["Bearer tok-SECRET"]


async def test_amo_unknown_contact_goes_to_unsorted():
    fake = FakeCrm({"/api/v4/calls": (200, {"_embedded": {"errors": [{"code": 404}], "calls": []}})})
    ctx = _ctx(CrmSession(), "call.ended", _call(), kind="amocrm", config=AMO_CONFIG)
    result = await _amo(fake).deliver(ctx)
    assert result.response_body == "unsorted"
    assert [p for p, _ in fake.requests] == ["/api/v4/calls", "/api/v4/leads/unsorted/sip"]
    assert fake.requests[0][1][0]["responsible_user_id"] == 1  # xaritasiz → default


async def test_amo_unknown_contact_without_unsorted_is_skipped():
    fake = FakeCrm({"/api/v4/calls": (404, {})})
    ctx = _ctx(CrmSession(), "call.ended", _call(), kind="amocrm", config={**AMO_CONFIG, "unsorted_for_unknown": False})
    assert (await _amo(fake).deliver(ctx)).response_body == "skipped:contact_not_found"
    assert len(fake.requests) == 1


async def test_amo_429_retry_after_and_401_transient_error():
    fake = FakeCrm(fail=[(429, {}, {"Retry-After": "7"}), (401, {}, {})])
    ctx = _ctx(CrmSession(), "call.ended", _call(), kind="amocrm", config=AMO_CONFIG)
    limited = await _amo(fake).deliver(ctx)
    assert (limited.ok, limited.retry_after_s, limited.status_code) == (False, 7.0, 429)
    denied = await _amo(fake).deliver(ctx)
    assert (denied.ok, denied.permanent, denied.status_code) == (False, False, 401)
    assert "tok-SECRET" not in denied.error


async def test_amo_400_without_errors_is_permanent():
    fake = FakeCrm({"/api/v4/calls": (400, {"title": "Bad"})})
    result = await _amo(fake).deliver(_ctx(CrmSession(), "call.ended", _call(), kind="amocrm", config=AMO_CONFIG))
    assert (result.ok, result.permanent) == (False, True)


async def test_amo_skips_non_ended_internal_and_unconfigured():
    fake = FakeCrm()
    provider = _amo(fake)
    assert (await provider.deliver(_ctx(CrmSession(), "call.ringing", _call(), kind="amocrm",
                                        config=AMO_CONFIG))).response_body == "skipped"
    assert (await provider.deliver(_ctx(CrmSession(), "call.ended", _call(direction="internal"), kind="amocrm",
                                        config=AMO_CONFIG))).response_body == "skipped"
    unconfigured = await provider.deliver(_ctx(CrmSession(), "call.ended", _call(), kind="amocrm", config={}))
    assert unconfigured.permanent and fake.requests == []


async def test_amo_users_follow_next_link():
    pages = iter([{"_embedded": {"users": [{"id": 5, "name": "Ali"}]}, "_links": {"next": {"href": "x"}}},
                  {"_embedded": {"users": [{"id": 6, "email": "b@c"}]}}])
    client = amocrm.AmoCrmProvider(
        url_check=lambda u: None, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=next(pages))),
        limiter=NoWait()).client("s1", amocrm.AmoSettings("http://10.0.0.8", "tok", True, None))
    assert [(u.id, u.name) for u in await client.users()] == [("5", "Ali"), ("6", "b@c")]


async def test_amo_users_rejected_is_error():
    client = _amo(FakeCrm({"/api/v4/users": (403, {})})).client("s1", amocrm.AmoSettings("http://h", "t", True, None))
    with pytest.raises(crm.CrmCallError):
        await client.users()


# ------------------------------------------------------------ umumiy yordamchilar
async def test_rate_limiter_spaces_calls_per_key():
    now, slept = [100.0], []

    async def sleep(seconds):
        slept.append(round(seconds, 3))

    limiter = crm.RateLimiter(2, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        await limiter.wait("a")
    await limiter.wait("b")
    assert slept == [0.5, 1.0]


def test_secrets_roundtrip_and_garbage():
    assert crm.load_secrets(crm.dump_secrets({"token": "x", "empty": ""})) == {"token": "x"}
    assert crm.load_secrets("not json") == {} and crm.load_secrets("[1]") == {} and crm.load_secrets(None) == {}


def test_retry_after_and_http_failure():
    assert crm.retry_after({"retry-after": "0"}) == 1.0 and crm.retry_after({"retry-after": "x"}) == 2.0
    assert crm.http_failure(204, {}, what="m") is None
    assert crm.http_failure(500, {}, what="m").result.permanent is False
    assert crm.http_failure(404, {}, what="m").result.permanent is True


def test_user_map_fallback_order():
    users = crm.UserMap({"101": "7", "103": "9"}, "1")
    assert users.user_for(None, "103") == "9"
    assert users.user_for("103", "101") == "9"
    assert users.user_for("555") == "1"
    assert crm.UserMap({}).user_for("555") is None


async def test_dispatch_records_last_error():
    sub = SimpleNamespace(failing_since=None, last_success_at=None, last_error=None, enabled=True,
                          disabled_reason=None)
    await dispatch._update_subscription(None, sub, DeliveryResult(ok=False, status_code=503, error=None), NOW)
    assert sub.last_error == "HTTP 503"
    await dispatch._update_subscription(None, sub, DeliveryResult(ok=True, status_code=200), NOW)
    assert (sub.last_error, sub.last_success_at, sub.failing_since) == (None, NOW, None)


# ------------------------------------------------------------ admin sozlamalari
def _sub(kind="bitrix24", **kw):
    base = dict(id="s1", tenant_id="t1", kind=kind, enabled=False, config=crm_settings.default_config(kind),
                secret_enc=None, last_error=None, last_success_at=None, disabled_reason=None, failing_since=None,
                updated_at=NOW)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def plain_crypto(monkeypatch):
    async def decrypt(session, value):
        return value

    async def encrypt(session, value):
        return value

    monkeypatch.setattr(crm_settings, "decrypt_secret", decrypt)
    monkeypatch.setattr(crm_settings, "encrypt_secret", encrypt)


def test_config_out_never_exposes_secrets():
    secrets = {"webhook_url": HOOK, "application_token": "app-SECRET"}
    out = crm_settings.config_out("bitrix24", {"hook_token": "h1", "default_user_id": "1"}, secrets).model_dump()
    assert out["has_webhook_url"] and out["application_token_set"] and out["hook_token"] == "h1"
    assert "abc123" not in json.dumps(out) and "app-SECRET" not in json.dumps(out)
    amo = crm_settings.config_out("amocrm", {"base_url": "https://a.amocrm.ru"}, {"token": "tok-SECRET"})
    assert amo.token_set and "tok-SECRET" not in amo.model_dump_json()


def test_status_out_states():
    assert crm_settings.status_out(_sub(disabled_reason="auto"), ["101"]).model_dump() == {
        "state": "disabled", "last_ok_at": None, "last_error": "auto", "unmapped_extensions": []}
    assert crm_settings.status_out(_sub(enabled=True), ["101"]).state == "ok"
    err = crm_settings.status_out(_sub(enabled=True, last_error="HTTP 401"), ["101"])
    assert (err.state, err.unmapped_extensions) == ("error", ["101"])


def test_merge_user_map():
    rows = {"101": crm_settings.MapRow("7", "auto"), "103": crm_settings.MapRow("9", "manual")}
    entries, unmapped = crm_settings.merge_user_map([("101", True), ("102", True), ("103", True), ("104", False)],
                                                    rows, {"7": "Ali"})
    assert [(e.extension, e.crm_user_id, e.crm_user_name, e.source) for e in entries] == [
        ("101", "7", "Ali", "auto"), ("102", None, None, "auto"), ("103", "9", None, "manual"),
        ("104", None, None, "auto")]
    assert unmapped == ["102"]


def test_auto_map_skips_manual_and_duplicates():
    users = [CrmUserInfo("7", "A", "101"), CrmUserInfo("8", "B", "101"), CrmUserInfo("9", "C", "103"),
             CrmUserInfo("10", "D", "999"), CrmUserInfo("11", "E")]
    assert crm_settings.auto_map(users, {"101", "103"}, {"103"}) == {"101": "7"}


def test_changes_audit_masks_secrets():
    changes = crm_settings.Changes(enabled=True, config={"create_lead": True},
                                   secrets={"webhook_url": HOOK, "application_token": "app-SECRET"})
    diff = mask_secrets(changes.audit_diff())
    assert diff["webhook_url"] == "***" and diff["application_token"] == "***"
    assert "abc123" not in json.dumps(diff)


async def test_apply_changes_keeps_old_secret(plain_crypto):
    sub = _sub(secret_enc=crm.dump_secrets({"webhook_url": HOOK, "application_token": "old"}))
    changes = crm_settings.Changes(enabled=True, config={"popup_max_delay_s": 5}, secrets={"application_token": "new"})
    await crm_settings.apply_changes(CrmSession(), sub, changes)
    assert crm.load_secrets(sub.secret_enc) == {"webhook_url": HOOK, "application_token": "new"}
    assert sub.enabled and sub.config["popup_max_delay_s"] == 5 and sub.config["hook_token"]


async def test_apply_changes_reenable_clears_reason(plain_crypto):
    sub = _sub(secret_enc=crm.dump_secrets({"webhook_url": HOOK}), disabled_reason="x", failing_since=NOW)
    await crm_settings.apply_changes(CrmSession(), sub, crm_settings.Changes(enabled=True, config={}))
    assert (sub.disabled_reason, sub.failing_since, sub.secret_enc) == (None, None, crm.dump_secrets(
        {"webhook_url": HOOK}))


@pytest.mark.parametrize("kind,config,secrets", [("bitrix24", {}, {}), ("amocrm", {"base_url": ""}, {"token": "t"}),
                                                 ("amocrm", {"base_url": "http://h"}, {})])
async def test_apply_changes_enable_requires_configuration(plain_crypto, kind, config, secrets):
    sub = _sub(kind, config=config, secret_enc=crm.dump_secrets(secrets) if secrets else None)
    with pytest.raises(ApiError) as exc:
        await crm_settings.apply_changes(CrmSession(), sub, crm_settings.Changes(enabled=True, config={}))
    assert (exc.value.status_code, exc.value.code) == (422, "not_configured")
    await crm_settings.apply_changes(CrmSession(), sub, crm_settings.Changes(enabled=False, config={}))
    assert sub.enabled is False


async def test_bitrix_changes_validation(monkeypatch):
    checked = []

    async def check(url, field="url"):
        checked.append((url, field))
        return url

    monkeypatch.setattr(crm_routes, "check_webhook_url", check)
    payload = UpdateBitrixPayload(enabled=True, updated_at=NOW, webhook_url="http://10.0.0.7/rest/1/abc123",
                                  application_token=" tok ", default_user_id="")
    changes = await crm_routes.bitrix_changes(payload)
    assert changes.secrets == {"webhook_url": HOOK, "application_token": "tok"}
    assert changes.config == {"create_lead": True, "popup_max_delay_s": 20, "default_user_id": None,
                              "route_to_responsible": False, "responsible_ring_s": 20, "set_caller_name": True,
                              "upload_records": True, "auto_sync_users": True}
    assert checked == [(HOOK, "webhook_url")]
    empty = await crm_routes.bitrix_changes(UpdateBitrixPayload(enabled=False, updated_at=NOW, webhook_url=" "))
    assert empty.secrets == {}
    with pytest.raises(ApiError) as exc:
        await crm_routes.bitrix_changes(UpdateBitrixPayload(enabled=True, updated_at=NOW, webhook_url="https://x/y"))
    assert (exc.value.code, exc.value.field) == ("bad_webhook_url", "webhook_url")


async def test_amo_changes_validation(monkeypatch):
    async def check(url, field="url"):
        return url

    monkeypatch.setattr(crm_routes, "check_webhook_url", check)
    changes = await crm_routes.amo_changes(UpdateAmoPayload(enabled=True, updated_at=NOW,
                                                            base_url="https://a.amocrm.ru/", token=" t "))
    assert (changes.config["base_url"], changes.secrets) == ("https://a.amocrm.ru", {"token": "t"})
    assert (await crm_routes.amo_changes(UpdateAmoPayload(enabled=False, updated_at=NOW))).secrets == {}
    with pytest.raises(ApiError) as exc:
        await crm_routes.amo_changes(UpdateAmoPayload(enabled=True, updated_at=NOW, base_url="https://a/path"))
    assert exc.value.code == "bad_base_url"


async def test_crm_url_ssrf_forbidden(monkeypatch):
    from app.api.v1 import integrations as integ

    def forbid(url):
        raise integ.ssrf.UrlForbidden("loopback")

    monkeypatch.setattr(integ.ssrf, "check_url_default", forbid)
    with pytest.raises(ApiError) as exc:
        await crm_routes.amo_changes(UpdateAmoPayload(enabled=True, updated_at=NOW, base_url="http://127.0.0.1"))
    assert (exc.value.code, exc.value.field) == ("url_forbidden", "base_url")


async def test_update_bitrix_stale_409(monkeypatch):
    sub = _sub()

    async def ensure(session, tenant_id, provider):
        return sub

    monkeypatch.setattr(crm_settings, "ensure_subscription", ensure)
    user = SimpleNamespace(tenant_id="t1", id="u1")
    with pytest.raises(ApiError) as exc:
        await crm_routes.update_bitrix24(UpdateBitrixPayload(enabled=False, updated_at=NOW - timedelta(seconds=1)),
                                         session=CrmSession(), user=user)
    assert (exc.value.status_code, exc.value.code) == (409, "stale")


async def test_test_connection_success_and_failure(plain_crypto, monkeypatch):
    sub = _sub(secret_enc=crm.dump_secrets({"webhook_url": HOOK}), last_error="old")
    users = [CrmUserInfo("7", "Ali", "101")]

    async def fetch_ok(sub_, secrets):
        return users

    monkeypatch.setattr(crm_settings, "fetch_users", fetch_ok)
    session = CrmSession(None, None, ["101", "103"], [], None, None)  # users del/ins, raqamlar, manual, auto del/ins
    result = await crm_settings.test_connection(session, sub)
    assert (result.ok, result.users_loaded, sub.last_error) == (True, 1, None)
    assert "avto-xarita: 1" in result.message

    async def fetch_fail(sub_, secrets):
        raise crm.failure("user.get: autentifikatsiya rad etildi (HTTP 401)", status=401)

    monkeypatch.setattr(crm_settings, "fetch_users", fetch_fail)
    result = await crm_settings.test_connection(CrmSession(), sub)
    assert (result.ok, result.users_loaded) == (False, None) and sub.last_error.startswith("user.get")


async def test_test_connection_not_configured(plain_crypto):
    with pytest.raises(ApiError) as exc:
        await crm_settings.test_connection(CrmSession(), _sub("amocrm"))
    assert (exc.value.status_code, exc.value.code) == (422, "not_configured")


async def test_update_user_map_unknown_extension():
    with pytest.raises(ApiError) as exc:
        await crm_settings.update_user_map(CrmSession(["101"]), "t1", "bitrix24",
                                           [CrmUserMapEntryIn(extension="101", crm_user_id="7"),
                                            CrmUserMapEntryIn(extension="999", crm_user_id="")])
    assert (exc.value.code, exc.value.details) == ("unknown_extension", {"extensions": ["999"]})


async def test_update_user_map_upsert_and_delete():
    session = CrmSession(["101", "102"])
    await crm_settings.update_user_map(session, "t1", "bitrix24", [
        CrmUserMapEntryIn(extension="101", crm_user_id="7"), CrmUserMapEntryIn(extension="102", crm_user_id=None)])
    sql = [str(s).lower() for s in session.executed[1:]]
    assert sql[0].startswith("insert into crm_user_map") and "on conflict" in sql[0]
    assert sql[1].startswith("delete from crm_user_map")


def test_user_map_entry_rejects_bad_ids():
    with pytest.raises(ValueError):
        CrmUserMapEntryIn(extension="101", crm_user_id="abc")
    with pytest.raises(ValueError):
        CrmUserMapEntryIn(extension="../1", crm_user_id="1")


# ------------------------------------------------------------ Bitrix click-to-call hook
class FakeForm:
    def __init__(self, data):
        self.data = data

    async def form(self):
        return self.data


class FakeAmi:
    def __init__(self, response=None):
        self.actions = []
        self.response = response or {"Response": "Success"}

    async def action(self, name, **fields):
        self.actions.append((name, fields))
        return self.response


def _hook_form(token="app-tok", event="ONEXTERNALCALLSTART", **data):
    form = {"event": event, "auth[application_token]": token, "data[USER_ID]": "7",
            "data[PHONE_NUMBER]": "+998901234567", "data[CALL_ID]": "externalCall.B1"}
    form.update(data)
    return FakeForm({k: v for k, v in form.items() if v is not None})


def _hook_sub(enabled=True, **kw):
    return _sub(enabled=enabled, secret_enc=crm.dump_secrets({"webhook_url": HOOK, "application_token": "app-tok"}), **kw)


def test_token_matches():
    assert public_crm.token_matches("abc", "abc")
    assert not public_crm.token_matches("abc", "abd")
    assert not public_crm.token_matches("", "")
    assert not public_crm.token_matches(None, "abc")


async def test_hook_starts_call_and_links_before_originate(plain_crypto):
    ext = SimpleNamespace(number="101", enabled=True)
    session = CrmSession(_hook_sub(), "101", ext, objects={"Tenant": SimpleNamespace(code="acme")})
    ami = FakeAmi()
    resp = await public_crm.bitrix_call_start("h1", _hook_form(), session=session, ami=ami)
    request_id = json.loads(resp.body)["request_id"]
    assert resp.status_code == 202 and session.commits == 1
    link = session.links[("t1", "bitrix24", request_id)]
    assert (link.external_call_id, link.origin, link.user_id, link.shown_users) == \
        ("externalCall.B1", "crm", "7", ["7"])
    assert session.added.index(link) == 0  # bog'lanish originate'dan OLDIN
    name, fields = ami.actions[0]
    assert name == "Originate" and fields["ChannelId"] == request_id


async def test_hook_wrong_or_missing_token_403(plain_crypto):
    for form in (_hook_form(token="wrong"), _hook_form(token=None)):
        ami = FakeAmi()
        with pytest.raises(ApiError) as exc:
            await public_crm.bitrix_call_start("h1", form, session=CrmSession(_hook_sub()), ami=ami)
        assert exc.value.status_code == 403 and ami.actions == []


async def test_hook_unknown_or_disabled_404(plain_crypto):
    for sub in (None, _hook_sub(enabled=False)):
        with pytest.raises(ApiError) as exc:
            await public_crm.bitrix_call_start("h1", _hook_form(), session=CrmSession(sub), ami=FakeAmi())
        assert exc.value.status_code == 404


async def test_hook_other_event_ignored(plain_crypto):
    ami = FakeAmi()
    resp = await public_crm.bitrix_call_start("h1", _hook_form(event="ONEXTERNALCALLBACKSTART"),
                                              session=CrmSession(_hook_sub()), ami=ami)
    assert resp.status_code == 200 and ami.actions == []


async def test_hook_validation_errors(plain_crypto):
    cases = [(_hook_form(**{"data[CALL_ID]": None}), [], "invalid_request"),
             (_hook_form(**{"data[PHONE_NUMBER]": "abc"}), [], "invalid_number"),
             (_hook_form(), [None], "unknown_user")]
    for form, extra, code in cases:
        with pytest.raises(ApiError) as exc:
            await public_crm.bitrix_call_start("h1", form, session=CrmSession(_hook_sub(), *extra), ami=FakeAmi())
        assert exc.value.code == code


def test_hook_external_id():
    assert public_crm.external_id("externalCall.B1") == "externalCall.B1"
    assert public_crm.external_id("x" * 65) is None


# ------------------------------------------------------------ 1C namunalar
def _samples(tmp_path, manifest):
    if manifest is not None:
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "A.bsl").write_text("// modul", encoding="utf-8")
    return tmp_path


def test_onec_manifest_list_and_missing(tmp_path):
    directory = _samples(tmp_path, [{"name": "A.bsl", "title": "Modul"}, {"title": "nomsiz"}, "x"])
    assert [(s.name, s.title) for s in onec.load_manifest(directory)] == [("A.bsl", "Modul")]
    assert onec.load_manifest(tmp_path / "yoq") == []
    (tmp_path / "manifest.json").write_text("{buzuq", encoding="utf-8")
    assert onec.load_manifest(tmp_path) == []
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [{"name": "A.bsl"}]}), encoding="utf-8")
    assert onec.load_manifest(tmp_path)[0].title == "A.bsl"


@pytest.mark.parametrize("name", ["../secret.txt", "..%2Fsecret.txt", "/etc/passwd", "B.bsl", "sub/A.bsl",
                                  "manifest.json"])
def test_onec_path_traversal_404(tmp_path, name):
    root = tmp_path / "onec"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    directory = _samples(root, [{"name": n, "title": n} for n in
                                ("A.bsl", "../secret.txt", "/etc/passwd", "B.bsl", "sub/A.bsl")])
    with pytest.raises(ApiError) as exc:
        onec.sample_path(directory, name)
    assert exc.value.status_code == 404


async def test_onec_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(onec, "SAMPLES_DIR", _samples(tmp_path, [{"name": "A.bsl", "title": "Modul"}]))
    assert [s.name for s in (await onec.list_samples(None))["items"]] == ["A.bsl"]
    resp = await onec.download_sample("A.bsl", None)
    assert resp.path == tmp_path / "A.bsl" and "attachment" in resp.headers["content-disposition"]
    assert resp.media_type.startswith("text/plain")


def test_amo_users_page_tolerates_garbage():
    assert amocrm.users_page(None) == ([], False)
    assert amocrm.users_page({"_embedded": {"users": ["x", {"id": 1}]}}) == ([CrmUserInfo("1", "1")], False)


async def test_fetch_users_uses_provider_clients(monkeypatch):
    seen = []

    class Client:
        def __init__(self, arg):
            self.arg = arg

        async def users(self):
            return [CrmUserInfo("1", "x")]

    class Provider:
        def client(self, sub_id, arg):
            seen.append((sub_id, arg))
            return Client(arg)

    monkeypatch.setattr(bitrix24, "PROVIDER", Provider())
    monkeypatch.setattr(amocrm, "PROVIDER", Provider())
    assert len(await crm_settings.fetch_users(_sub(), {"webhook_url": HOOK})) == 1
    await crm_settings.fetch_users(_sub("amocrm", config=AMO_CONFIG), {"token": "t"})
    assert seen[0] == ("s1", HOOK) and seen[1][1] == amocrm.AmoSettings("http://10.0.0.8", "t", True, "1")
