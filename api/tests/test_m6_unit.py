"""M6 — kampaniyalar: sof qoidalar (CSV, oyna, natija, DTMF, AMI oq ro'yxat), sxema, dialplan, ichki endpoint."""
from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from app.api import internal_campaigns as ic
from app.core.config import settings
from app.core.errors import ApiError
from app.services import campaign_rules as r
from app.services import campaigns as svc
from app.services.campaign_dialer import tenant_now
from app.services.compiler import compile_dialplan
from app.services.dialplan_campaign import campaign_context_lines
from tests.test_compiler_outbound import _snapshot

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)  # dushanba


# ------------------------------------------------------------------ CSV
def test_parse_number_normalizes_and_rejects():
    assert r.parse_number(" +998 (90) 111-22-33 ") == "998901112233"
    assert r.parse_number("12") is None
    assert r.parse_number("1" * 16) is None
    assert r.parse_number("abc123") is None
    assert r.parse_number("") is None
    assert r.parse_number("100") == "100"


def test_csv_header_semicolon_duplicates_and_invalid():
    text = "Telefon;Ism\n998901112233;Ali\n+998 90 111 22 33;Takror\nxato;Vali\n\n998901112234\n"
    out = r.parse_contacts_csv(text)
    assert out.rows == [("998901112233", "Ali"), ("998901112234", None)]
    assert out.duplicates == 1
    assert out.invalid_count == 1
    assert out.invalid == [{"line": 4, "value": "xato"}]


def test_csv_header_only_on_first_line_and_existing_counted():
    out = r.parse_contacts_csv("998901112233,Ali\nnumber,name\n998901112235", existing={"998901112235"})
    assert out.rows == [("998901112233", "Ali")]
    assert out.invalid == [{"line": 2, "value": "number"}]
    assert out.duplicates == 1


def test_csv_comma_with_quoted_name_and_long_name():
    out = r.parse_contacts_csv('998901112233,"Aliyev, Ali"\n998901112234,' + "x" * 100)
    assert out.rows[0] == ("998901112233", "Aliyev, Ali")
    assert out.rows[1][1] == "x" * 80


def test_csv_invalid_report_is_capped():
    out = r.parse_contacts_csv("\n".join(["99", "98"] * 40))
    assert out.invalid_count == 80
    assert len(out.invalid) == r.MAX_INVALID_REPORTED


# ------------------------------------------------------------------ oyna
@pytest.mark.parametrize(("local", "expected"), [
    (datetime(2026, 11, 2, 9, 0), True),     # Du 09:00 — chegarada
    (datetime(2026, 11, 2, 8, 59), False),
    (datetime(2026, 11, 2, 20, 0), False),   # oxiri kirmaydi
    (datetime(2026, 11, 8, 12, 0), False),   # Yakshanba
])
def test_in_window_day(local, expected):
    assert r.in_window(local, time(9), time(20), [1, 2, 3, 4, 5, 6]) is expected


@pytest.mark.parametrize(("local", "expected"), [
    (datetime(2026, 11, 2, 23, 0), True),    # Du 23:00 — Du oynasi
    (datetime(2026, 11, 3, 1, 0), True),     # Se 01:00 — kechagi (Du) oyna
    (datetime(2026, 11, 3, 2, 0), False),
    (datetime(2026, 11, 2, 1, 0), False),    # Du 01:00 — Yakshanba oynasi, Ya yo'q
    (datetime(2026, 11, 2, 12, 0), False),
])
def test_in_window_overnight(local, expected):
    assert r.in_window(local, time(22), time(2), [1]) is expected


def test_tenant_now_converts_and_falls_back():
    assert tenant_now("Asia/Tashkent", NOW).hour == 15
    assert tenant_now("Yo'q/Zona", NOW).hour == 15
    assert tenant_now("UTC", NOW).hour == 10


# ------------------------------------------------------------------ natija
@pytest.mark.parametrize(("raw", "expected"), [
    ("ANSWER", "ANSWER"), ("busy", "BUSY"), ("NOANSWER", "NOANSWER"), ("CHANUNAVAIL", "CHANUNAVAIL"),
    ("CONGESTION", "CONGESTION"), ("CANCEL", "NOANSWER"), ("", "NOROUTE"), (" ", "NOROUTE"), ("XYZ", "CONGESTION"),
])
def test_classify_dial_status(raw, expected):
    assert r.classify_dial_status(raw) == expected


def test_parse_billsec():
    assert r.parse_billsec("12") == 12
    assert r.parse_billsec("7.9") == 7
    assert r.parse_billsec("") == 0
    assert r.parse_billsec("-3") == 0


def test_contact_outcome():
    assert r.contact_outcome("ANSWER", 3, 3, NOW, 60) == ("done", None)
    assert r.contact_outcome("BUSY", 3, 3, NOW, 60) == ("failed", None)
    status, at = r.contact_outcome("BUSY", 2, 3, NOW, 60)
    assert status == "retry"
    assert (at - NOW).total_seconds() == 60
    assert r.contact_outcome("BUSY", 2, 3, NOW, 60, stopped=True) == ("skipped", None)
    assert r.contact_outcome("ANSWER", 1, 3, NOW, 60, stopped=True) == ("done", None)
    assert r.contact_outcome("BUSY", 3, 3, NOW, 60, stopped=True) == ("failed", None)


def test_key_action():
    kw = dict(mode="message", dtmf_connect=True, dtmf_optout=True, target_number="201")
    assert r.key_action("1", **kw) == "connect"
    assert r.key_action("9", **kw) == "optout"
    assert r.key_action("5", **kw) == "none"
    assert r.key_action("1", **{**kw, "dtmf_connect": False}) == "none"
    assert r.key_action("1", **{**kw, "target_number": None}) == "none"
    assert r.key_action("9", **{**kw, "dtmf_optout": False}) == "none"
    assert r.key_action("1", **{**kw, "mode": "connect"}) == "none"


# ------------------------------------------------------------------ AMI
def _req(**kw):
    base = dict(code="t1", number="998901112233", attempt_id=7, campaign_id="c-1", mode="message",
                ring_seconds=20, audio_path="/var/lib/innova/sounds/t1/a1")
    return r.DialRequest(**{**base, **kw})


def test_originate_fields():
    f = r.originate_fields(_req(callerid="712000000", dtmf=True, target_number="201"))
    assert f["Channel"] == "Local/998901112233@t1-campaign-dial/n"
    assert f["Context"] == "t1-campaign-answer"
    assert (f["Exten"], f["Priority"], f["Timeout"], f["Async"]) == ("s", "1", "20000", "true")
    assert f["CallerID"] == "<712000000>"
    assert f["Variable"] == ("INNOVA_CAMP_ATTEMPT=7,INNOVA_CAMP_ID=c-1,INNOVA_CAMP_NUM=998901112233,"
                             "INNOVA_CAMP_MODE=message,INNOVA_CAMP_AUDIO=/var/lib/innova/sounds/t1/a1,"
                             "INNOVA_CAMP_DTMF=1,INNOVA_CAMP_TO=201,INNOVA_CAMP_CID=712000000")
    assert "CallerID" not in r.originate_fields(_req())


@pytest.mark.parametrize("bad", ["1\r\nAction: Command", "a,b", "x;y", "a@b", "a b"])
def test_originate_fields_rejects_injection(bad):
    with pytest.raises(ValueError):
        r.originate_fields(_req(audio_path=bad))
    with pytest.raises(ValueError):
        r.originate_fields(_req(number=bad))


# ------------------------------------------------------------------ sxema/tekshiruv
def _fields(**kw):
    base = dict(name="Aksiya", mode="message", audio_id="a1")
    return svc.merge_fields({}, {**base, **kw})


def test_merge_fields_validation_error_has_field():
    with pytest.raises(ApiError) as exc:
        svc.merge_fields({"name": "A", "mode": "message"}, {"ring_seconds": 5})
    assert (exc.value.status_code, exc.value.code, exc.value.field) == (422, "validation_error", "ring_seconds")


def test_merge_fields_blank_to_none_and_strip():
    f = _fields(name="  Aksiya  ", target_number=" ", callerid="")
    assert (f.name, f.target_number, f.callerid) == ("Aksiya", None, None)


@pytest.mark.parametrize(("kw", "code"), [
    ({"audio_id": None}, "campaign_audio_required"),
    ({"mode": "connect", "audio_id": None}, "campaign_target_required"),
    ({"mode": "connect", "target_number": "201", "dtmf_optout": True}, "campaign_dtmf_mode"),
    ({"dtmf_connect": True}, "campaign_target_required"),
    ({"window_start": time(9), "window_end": time(9)}, "campaign_window"),
    ({"days": [1, 1]}, "campaign_days"),
    ({"days": [0]}, "campaign_days"),
])
def test_check_shape_codes(kw, code):
    with pytest.raises(ApiError) as exc:
        svc._check_shape(_fields(**kw))
    assert (exc.value.status_code, exc.value.code) == (422, code)


def test_check_shape_ok():
    svc._check_shape(_fields(dtmf_connect=True, dtmf_optout=True, target_number="201"))
    svc._check_shape(_fields(mode="connect", audio_id=None, target_number="300"))


# ------------------------------------------------------------------ dialplan
def test_campaign_contexts_in_compiled_dialplan():
    snap = _snapshot()
    out = compile_dialplan(snap)
    assert "[t1-campaign-dial]" in out and "[t1-campaign-hangup]" in out and "[t1-campaign-answer]" in out
    assert out.index("[t1-outbound-rg]") < out.index("[t1-campaign-dial]")


def test_campaign_context_lines_urls_and_flow():
    lines = campaign_context_lines("t9", "http://api:8000", "tok")
    text = "\n".join(lines)
    assert "Set(CHANNEL(hangup_handler_push)=t9-campaign-hangup,s,1)" in text
    assert "Goto(t9-outbound-rg,${EXTEN},1)" in text
    assert ("http://api:8000/internal/campaigns/result?token=tok&attempt=${INNOVA_CAMP_ATTEMPT}"
            "&status=${DIALSTATUS}&answered=${ANSWEREDTIME}") in text
    assert "/internal/campaigns/key?token=tok&attempt=${INNOVA_CAMP_ATTEMPT}&key=${URIENCODE(${INNOVA_CAMP_KEY})}" in text
    assert "Read(INNOVA_CAMP_KEY,${INNOVA_CAMP_AUDIO},1,,2,6)" in text
    assert " same => n(connect),Goto(t9-from-internal,${INNOVA_CAMP_TO},1)" in lines
    assert " same => n,Return()" in lines
    labels = [ln.split("(")[1].split(")")[0] for ln in lines if ln.startswith(" same => n(")]
    assert sorted(labels) == ["connect", "done", "menu", "optout"]


# ------------------------------------------------------------------ ichki endpoint
@pytest.mark.parametrize(("token", "attempt", "expected"), [
    ("good", "12", 12), ("bad", "12", None), ("good", "", None), ("good", "1x", None), ("good", "-1", None),
])
def test_internal_attempt_id(monkeypatch, token, attempt, expected):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    assert ic._attempt_id(token, attempt) == expected


def test_internal_attempt_id_empty_token_denies(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "")
    assert ic._attempt_id("", "12") is None


async def test_internal_result_bad_token_no_db(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    resp = await ic.campaign_result(token="bad", attempt="1", status="ANSWER", answered="3", session=None)
    assert resp.body == b"0"
    resp = await ic.campaign_key(token="bad", attempt="1", key="1", session=None)
    assert resp.body == b"none"


# ------------------------------------------------------------------ fon tsikl / filtr
async def test_run_forever_skips_in_maintenance_and_survives_errors(monkeypatch):
    import asyncio

    from app.services import campaign_dialer as dialer
    from app.services import maintenance

    calls: list[str] = []
    sleeps: list[float] = []

    async def fake_cycle(factory, ami):
        calls.append("cycle")
        raise RuntimeError("bazada xato")

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:
            monkeypatch.setattr(maintenance.state, "enabled", False)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(dialer, "dialer_cycle", fake_cycle)
    monkeypatch.setattr(dialer.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(maintenance.state, "enabled", True)
    with pytest.raises(asyncio.CancelledError):
        await dialer.run_forever(None, None, 1.5)
    assert calls == ["cycle", "cycle"]          # 1-aylanish texnik rejimda o'tkazildi, xato tsiklni to'xtatmadi
    assert sleeps == [1.5, 1.5, 1.5]


async def test_run_forever_propagates_cancel_from_cycle(monkeypatch):
    import asyncio

    from app.services import campaign_dialer as dialer
    from app.services import maintenance

    async def cancelled(factory, ami):
        raise asyncio.CancelledError

    monkeypatch.setattr(dialer, "dialer_cycle", cancelled)
    monkeypatch.setattr(maintenance.state, "enabled", False)
    with pytest.raises(asyncio.CancelledError):
        await dialer.run_forever(None, None, 1)


def test_contact_filter():
    from app.api.v1.campaigns import _contact_filter

    assert len(_contact_filter("c-1", None, None)) == 1
    assert len(_contact_filter("c-1", "done", "  ")) == 2
    conds = _contact_filter("c-1", "done", " 9989 ")
    assert len(conds) == 3
    assert "%9989%" in str(conds[2].compile(compile_kwargs={"literal_binds": True}))


def test_export_value():
    from app.api.v1.campaigns import _export_value

    assert _export_value(NOW) == "2026-11-02T10:00:00+00:00"
    assert _export_value(5) == 5
    assert _export_value(None) is None


def test_csv_delimiter_only_line_is_invalid():
    out = r.parse_contacts_csv("998901112233\n;\n")
    assert out.invalid == [{"line": 2, "value": ""}]
