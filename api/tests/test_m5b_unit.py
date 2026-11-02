"""M5b — Follow Me (validatsiya, saqlash, dialplan) va QR orqali sozlash (token, Linphone XML, /prov/qr)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1 import follow_me as fm_api
from app.core.errors import ApiError
from app.schemas_follow_me import FollowMe, FollowMePayload
from app.services import dialplan_features as feat
from app.services import dialplan_recording as rec
from app.services import follow_me as fm
from app.services import qr_provisioning as qr
from app.services.compiler import compile_dialplan
from app.services.prov_guard import FailureGuard
from app.services.prov_serve import ProvRequest
from tests.test_compiler_outbound import _snapshot
from tests.test_m4a_services import TID, FakeSession, _tp

NOW = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
EXT_ID = "e1"


def _ext(**kw):
    base = dict(id=EXT_ID, tenant_id=TID, number="201", name="Ali", webrtc=False, outbound_allowed=True,
                toll_blocked_at=None, follow_me=FollowMe().model_dump(), updated_at=NOW)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def audits(monkeypatch):
    seen = []

    async def fake_audit(_session, **kw):
        seen.append(kw)

    monkeypatch.setattr(fm, "record_audit", fake_audit)
    monkeypatch.setattr(qr, "record_audit", fake_audit)
    return seen


# ------------------------------------------------------------------ sxema
@pytest.mark.parametrize("kw", [{"ring_seconds": 4}, {"ring_seconds": 121}, {"strategy": "random"},
                                {"numbers": [str(n) for n in range(200, 207)]}])
def test_schema_limits(kw) -> None:
    with pytest.raises(ValidationError):
        FollowMe(**kw)


def test_schema_defaults_match_db_default() -> None:
    assert FollowMe().model_dump() == {"enabled": False, "numbers": [], "strategy": "ring_all",
                                       "include_extension": True, "ring_seconds": 20, "confirm": True}
    assert FollowMePayload(updated_at=NOW).updated_at == NOW


# ------------------------------------------------------------------ normalizatsiya / tasnif
def test_normalize_numbers_ok() -> None:
    assert fm.normalize_numbers(["202", "+998 90 123-45-67"], "201") == ["202", "998901234567"]


@pytest.mark.parametrize(("raw", "code", "field"), [
    (["abc"], "bad_number", "numbers.0"),
    (["202", "1"], "bad_number", "numbers.1"),
    (["201"], "follow_me_self", "numbers.0"),
    (["202", "202"], "follow_me_duplicate", "numbers.1"),
])
def test_normalize_numbers_errors(raw, code, field) -> None:
    with pytest.raises(ApiError) as err:
        fm.normalize_numbers(raw, "201")
    assert (err.value.status_code, err.value.code, err.value.field) == (422, code, field)


@pytest.mark.asyncio
async def test_classify_kinds_and_errors() -> None:
    assert await fm._classify(FakeSession(), TID, []) == {}
    kinds = await fm._classify(FakeSession(["202"], []), TID, ["202", "998901234567"])
    assert kinds == {"202": "internal", "998901234567": "external"}
    for numbers, others, code in ((["600"], ["600"], "follow_me_bad_target"),
                                  (["701"], [], "follow_me_bad_target"),
                                  (["299"], [], "follow_me_unknown_extension")):
        with pytest.raises(ApiError) as err:
            await fm._classify(FakeSession([], others), TID, numbers)
        assert err.value.code == code and err.value.field == "numbers.0"


@pytest.mark.asyncio
async def test_validate_enabled_rules() -> None:
    with pytest.raises(ApiError) as err:
        await fm.validate_follow_me(FakeSession(), _ext(), FollowMe(enabled=True))
    assert err.value.code == "follow_me_empty"
    for ext in (_ext(outbound_allowed=False), _ext(toll_blocked_at=NOW)):
        with pytest.raises(ApiError) as err:
            await fm.validate_follow_me(FakeSession([], []), ext, FollowMe(enabled=True, numbers=["99890"]))
        assert err.value.code == "follow_me_outbound_forbidden"
    # O'chirilgan holatda tashqi raqamni saqlash — ruxsat; ichki raqam — doim.
    off = await fm.validate_follow_me(FakeSession([], []), _ext(outbound_allowed=False),
                                      FollowMe(numbers=["+99890"]))
    assert off.numbers == ["99890"]
    on = await fm.validate_follow_me(FakeSession(["202"], []), _ext(outbound_allowed=False),
                                     FollowMe(enabled=True, numbers=["202"]))
    assert on.enabled and on.numbers == ["202"]


@pytest.mark.asyncio
async def test_save_audits_only_on_change(audits) -> None:
    ext = _ext()
    session = FakeSession(["202"], [])
    out = await fm.save_follow_me(session, ext, FollowMe(enabled=True, numbers=["202"], strategy="sequential"),
                                  user_id="u1")
    assert ext.follow_me == out.model_dump() and ext.follow_me["strategy"] == "sequential"
    assert audits[0]["diff"]["follow_me"]["to"]["numbers"] == ["202"] and session.commits == 1
    await fm.save_follow_me(FakeSession(["202"], []), ext, out, user_id="u1")
    assert len(audits) == 1


# ------------------------------------------------------------------ endpointlar
@pytest.mark.asyncio
async def test_endpoints_admin_and_me(monkeypatch, audits) -> None:
    ext = _ext()

    async def fake_get(_s, tid, ext_id):
        assert (tid, ext_id) == (TID, EXT_ID)
        return ext

    monkeypatch.setattr(fm_api, "_get_extension_or_404", fake_get)
    user = SimpleNamespace(id="u1", tenant_id=TID, extension=ext)
    got = await fm_api.get_follow_me(EXT_ID, session=FakeSession(), user=user)
    assert got.number == "201" and got.follow_me == FollowMe()
    put = await fm_api.put_my_follow_me(FollowMePayload(numbers=["202"], updated_at=NOW),
                                        session=FakeSession(["202"], []), user=user)
    assert put.follow_me.numbers == ["202"]
    with pytest.raises(ApiError) as err:
        await fm_api.put_follow_me(EXT_ID, FollowMePayload(updated_at=NOW - timedelta(seconds=1)),
                                   session=FakeSession(), user=user)
    assert err.value.code == "stale"
    with pytest.raises(ApiError) as err:
        await fm_api.get_my_follow_me(user=SimpleNamespace(extension=None))
    assert err.value.code == "no_extension"


# ------------------------------------------------------------------ dialplan
def test_ext_call_goes_to_follow_me_before_noanswer_dest() -> None:
    lines = feat.ext_call_lines("t1")
    noans = next(i for i, line in enumerate(lines) if "n(noans)," in line)
    assert "fm_enabled)}" in lines[noans] and lines[noans].endswith('"!="t"]?noans2)')
    assert lines[noans + 1] == " same => n,Goto(t1-fm,${EXTEN},1)"
    assert lines[noans + 2].startswith(' same => n(noans2),GotoIf($["${INNOVA_NOANS}"=""]?done)')


def test_fm_context_ring_all_and_sequential() -> None:
    text = "\n".join(feat.fm_context_lines("t1"))
    assert "[t1-fm]" in text and "Set(__INNOVA_FM_OWNER=${EXTEN})" in text
    assert "Set(__INNOVA_FM_TRUNK=${INNOVA_FROM_TRUNK})" in text
    assert "Dial(${INNOVA_FM_DIAL},${INNOVA_FM_RING},U(innova-rec))" in text
    assert "Dial(Local/${INNOVA_FM_LEG}@t1-fm-leg/n,${INNOVA_FM_RING},U(innova-rec))" in text
    assert "CUT(INNOVA_FM_LIST,&,${INNOVA_FM_I})" in text
    assert text.endswith("n(after),Goto(t1-ext-call,${EXTEN},noans2)")


def test_fm_leg_internal_and_external() -> None:
    text = "\n".join(feat.fm_leg_lines("t1"))
    assert "Set(INNOVA_FROM_TRUNK=${INNOVA_FM_TRUNK})" in text
    assert "Dial(PJSIP/t1-${EXTEN},," in text and '"t"]?skip)' in text
    assert "n(external),Set(INNOVA_FWD_FROM=${INNOVA_FM_OWNER})" in text
    assert "Set(__INNOVA_FM_CONFIRM=${INNOVA_FM_CONF})" in text and text.endswith("Goto(t1-outbound,${EXTEN},1)")


def test_followme_toggle_builder() -> None:
    lines = feat.FEATURE_BUILDERS["followme_toggle"]("t1", "*21")
    assert lines[0] == "exten => *21,1,NoOp(Innova: Follow Me almashtirish)"
    assert any("REALTIME(ext_state,endpoint,${INNOVA_EP},fm_enabled)=${INNOVA_NEW}" in x for x in lines)
    assert " same => n(err),Playback(invalid)" in lines


def test_confirm_on_trunk_leg_aborts_only_that_leg() -> None:
    text = "\n".join(rec.recording_context_lines())
    assert ' same => n(trunk),GotoIf($["${INNOVA_FM_CONFIRM}"!="t"]?trunkrec)' in text
    assert "Read(INNOVA_FM_KEY,followme/options,1,,2,5)" in text
    assert " same => n,Set(GOSUB_RESULT=ABORT)" in text and "n(trunkrec),Set(INNOVA_REC_P=" in text


def test_compiled_dialplan_has_fm_contexts() -> None:
    text = compile_dialplan(_snapshot())
    assert "[t1-fm]" in text and "[t1-fm-leg]" in text


# ------------------------------------------------------------------ QR
def _settings(base="https://pbx.uz", transport="tls"):
    return SimpleNamespace(tenant_id=TID, integrations={"public_base_url": base},
                           provisioning={"sip_transport": transport}, sip_udp_port=5060, sip_tls_port=5061)


@pytest.mark.asyncio
async def test_issue_token(audits) -> None:
    session = FakeSession(objects={("SystemSettings", TID): _settings()})
    issued = await qr.issue_token(session, _ext(), user_id="u1", now=NOW)
    token = issued.url.split("/")[-2]
    assert issued.url == f"https://pbx.uz/prov/qr/{token}/linphone.xml" and len(token) >= 43
    assert issued.expires_at == NOW + timedelta(minutes=15) and issued.transport == "tls"
    params = session.executed[0].compile().params
    assert params["token_hash"] == qr.token_hash(token) and token not in str(params)
    assert audits[0]["diff"] == {"qr_provisioning": "issued", "expires_at": issued.expires_at.isoformat()}
    assert session.commits == 1


@pytest.mark.asyncio
async def test_issue_token_conflicts() -> None:
    with pytest.raises(ApiError) as err:
        await qr.issue_token(FakeSession(), _ext(webrtc=True), user_id="u1")
    assert (err.value.status_code, err.value.code) == (409, "extension_webrtc_only")
    session = FakeSession(objects={("SystemSettings", TID): _settings(base="")})
    with pytest.raises(ApiError) as err:
        await qr.issue_token(session, _ext(), user_id="u1")
    assert err.value.code == "public_host_not_configured"
    with pytest.raises(ApiError) as err:
        await qr.issue_token(FakeSession(), _ext(), user_id="u1")
    assert err.value.status_code == 404


def test_token_usable_window() -> None:
    row = SimpleNamespace(expires_at=NOW + timedelta(minutes=5), first_used_at=None)
    assert qr.token_usable(row, NOW)
    row.first_used_at = NOW
    assert qr.token_usable(row, NOW + timedelta(seconds=60))
    assert not qr.token_usable(row, NOW + timedelta(seconds=61))
    assert not qr.token_usable(SimpleNamespace(expires_at=NOW, first_used_at=None), NOW)


def test_render_linphone_escapes() -> None:
    body = qr.render_linphone(qr.LinphoneCtx(username="t1-201", password='p<&>"x', host="pbx.uz", port=5061,
                                             transport="tls", display_name="Ali & Co")).decode()
    assert "<sip:pbx.uz:5061;transport=tls>" not in body  # XML ichida escape qilingan
    assert "&lt;sip:pbx.uz:5061;transport=tls&gt;" in body
    assert '<entry name="passwd" overwrite="true">p&lt;&amp;&gt;"x</entry>' in body
    assert '"Ali &amp; Co" &lt;sip:t1-201@pbx.uz&gt;' in body
    assert '<entry name="username" overwrite="true">t1-201</entry>' in body


def _qr_req(token="x" * 43, ip="10.0.0.9"):
    return ProvRequest(token=token, filename="linphone.xml", ip=ip, user_agent="Linphone/5", host="pbx.uz",
                       path_prefix="/prov/qr")


def _logged(session):
    return [o for o in session.added if type(o).__name__ == "ProvisionRequest"]


@pytest.fixture
def renders(monkeypatch):
    async def code(_s, _tid):
        return "t1"

    async def load(_s, _row, _code, _host):
        return _tp(sip_transport="udp")

    async def passwords(_s, ids):
        return {i: "s3cret" for i in ids}

    monkeypatch.setattr(qr, "get_tenant_code", code)
    monkeypatch.setattr(qr.svc, "load_tenant_prov", load)
    monkeypatch.setattr(qr.svc, "sip_passwords", passwords)


@pytest.mark.asyncio
async def test_serve_qr_first_use_then_grace(renders, audits) -> None:
    token_row = SimpleNamespace(extension_id=EXT_ID, tenant_id=TID, expires_at=NOW + timedelta(minutes=10),
                                first_used_at=None)
    objects = {("Extension", EXT_ID): _ext(), ("SystemSettings", TID): _settings()}
    session = FakeSession(token_row, objects=objects)
    result = await qr.serve_qr(session, _qr_req(), FailureGuard(lambda: 0.0), now=NOW)
    assert (result.status, result.reason, result.content_type) == (200, "ok", "application/xml")
    assert b"<entry name=\"passwd\" overwrite=\"true\">s3cret</entry>" in result.body
    assert b"transport=udp" in result.body and token_row.first_used_at == NOW
    assert _logged(session)[0].path == "/prov/qr/***/linphone.xml" and "x" * 43 not in str(audits)
    assert audits[0]["diff"]["qr_provisioning"] == "used"
    again = await qr.serve_qr(FakeSession(token_row, objects=objects), _qr_req(), FailureGuard(lambda: 0.0),
                              now=NOW + timedelta(seconds=30))
    assert again.status == 200 and len(audits) == 1
    late = await qr.serve_qr(FakeSession(token_row, objects=objects), _qr_req(), FailureGuard(lambda: 0.0),
                             now=NOW + timedelta(seconds=61))
    assert (late.status, late.reason) == (404, "bad_token")


@pytest.mark.asyncio
async def test_serve_qr_bad_short_missing_and_rate_limit(renders) -> None:
    guard = FailureGuard(lambda: 0.0, limit=2)
    short = FakeSession()
    assert (await qr.serve_qr(short, _qr_req(token="abc"), guard)).reason == "bad_token"
    assert short.executed == []
    assert (await qr.serve_qr(FakeSession(None), _qr_req(), guard)).reason == "bad_token"
    assert (await qr.serve_qr(FakeSession(), _qr_req(), guard)).reason == "rate_limited"
    gone = SimpleNamespace(extension_id=EXT_ID, tenant_id=TID, expires_at=NOW + timedelta(minutes=1),
                           first_used_at=None)
    result = await qr.serve_qr(FakeSession(gone), _qr_req(ip="10.0.0.10"), FailureGuard(lambda: 0.0), now=NOW)
    assert (result.status, result.reason) == (404, "not_found")


# ------------------------------------------------------------------ FreePBX import (findmefollow)
from app.services.fpbx.mappers import extension as fpbx_ext  # noqa: E402


def _fm_row(**kw):
    row = {"grpnum": "101", "grplist": "101-102-0901234567#", "grptime": "30", "strategy": "ringallv2-prim",
           "needsconf": "CHECKED"}
    row.update(kw)
    return {"101": row}


def test_fpbx_follow_me_full_mapping() -> None:
    warns: list = []
    got = fpbx_ext._follow_me("101", _fm_row(), "DIRECT", warns)
    assert got == {"enabled": True, "numbers": ["102", "0901234567"], "strategy": "ring_all",
                   "include_extension": True, "ring_seconds": 30, "confirm": True}
    assert FollowMe.model_validate(got) and len(warns) == 1


@pytest.mark.parametrize(("kw", "ddial", "expect"), [
    ({"grptime": "7"}, None, {"enabled": False, "ring_seconds": 7}),
    ({"grplist": "101", "grptime": "500"}, "DIRECT", {"enabled": False, "numbers": [], "include_extension": True,
                                                  "ring_seconds": 120}),
    ({"strategy": "hunt", "needsconf": ""}, "EXTENSION", {"enabled": False, "strategy": "sequential",
                                                         "confirm": False}),
    ({"grplist": "102-1*2-102-+99890", "grptime": ""}, "DIRECT", {"enabled": True, "numbers": ["102", "99890"],
                                                                "include_extension": False, "ring_seconds": 20}),
])
def test_fpbx_follow_me_variants(kw, ddial, expect) -> None:
    got = fpbx_ext._follow_me("101", _fm_row(**kw), ddial, [])
    assert {k: got[k] for k in expect} == expect


def test_fpbx_follow_me_limits_and_default() -> None:
    warns: list = []
    got = fpbx_ext._follow_me("101", _fm_row(grplist="-".join(str(n) for n in range(200, 209)),
                                             strategy="memoryhunt"), None, warns)
    assert got["numbers"] == [str(n) for n in range(200, 206)] and got["strategy"] == "sequential"
    assert len(warns) == 3
    assert fpbx_ext._follow_me("105", {}, None, []) == FollowMe().model_dump()
