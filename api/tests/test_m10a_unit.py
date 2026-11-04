"""M10 Bo'lak A — qayta chaqirish vidjeti (A1), o'tkazib yuborilgan qo'ng'iroq
bildirishnomasi (A2), Yandex TTS (A3): sof qoidalar, dialplan, ichki endpoint, fon tsikl."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api import internal_callback as ic
from app.core.config import settings
from app.services import callback_rules as cr
from app.services import missed_call_rules as mr
from app.services import tts_yandex as tts
from app.services.compiler import compile_dialplan
from app.services.dialplan_callback import callback_context_lines
from tests.test_compiler_outbound import _snapshot

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ A1: callback_rules — AMI maydonlari
def _dial_req(**kw):
    base = dict(code="t1", request_id="r-1", dest_ctx="t1-dest-x1", phone="998901112233",
                callerid_prefix=None)
    return cr.CallbackDialRequest(**{**base, **kw})


def test_originate_fields_shape():
    f = cr.originate_fields(_dial_req(callerid_prefix="712000000"))
    assert f["Channel"] == "Local/s@t1-callback-dial/n"
    assert f["Context"] == "t1-callback-answer"
    assert (f["Exten"], f["Priority"], f["Async"]) == ("s", "1", "true")
    assert f["Timeout"] == str(cr.OPERATOR_RING_S * 1000)
    assert f["Variable"] == ("INNOVA_CB_REQUEST=r-1,INNOVA_CB_DESTCTX=t1-dest-x1,"
                             "INNOVA_CB_PHONE=998901112233,INNOVA_CB_CID=712000000")


def test_originate_fields_blank_callerid_prefix():
    f = cr.originate_fields(_dial_req())
    assert f["Variable"].endswith("INNOVA_CB_CID=")


@pytest.mark.parametrize("bad", ["1\r\nAction: Command", "a,b", "x;y", "a@b", "a b"])
def test_originate_fields_rejects_injection(bad):
    with pytest.raises(ValueError):
        cr.originate_fields(_dial_req(phone=bad))
    with pytest.raises(ValueError):
        cr.originate_fields(_dial_req(code=bad))


# ------------------------------------------------------------------ A1: callback_rules — natija
def test_operator_result_answer_is_noop():
    assert cr.operator_result("ANSWER", 1, 3, NOW, 60) is None


def test_operator_result_no_answer_retries_then_fails():
    retry = cr.operator_result("BUSY", 1, 3, NOW, 60)
    assert (retry.status, retry.last_error) == ("pending", "operator_BUSY")
    assert retry.next_attempt_at == NOW + timedelta(seconds=60)
    final = cr.operator_result("BUSY", 3, 3, NOW, 60)
    assert (final.status, final.next_attempt_at, final.last_error) == ("failed", None, "operator_BUSY")


def test_lost_result_treats_as_retry_tag():
    retry = cr.lost_result(1, 3, NOW, 60)
    assert (retry.status, retry.last_error) == ("pending", "lost")
    final = cr.lost_result(3, 3, NOW, 60)
    assert final.status == "failed"


def test_customer_result_answer_connected_terminal():
    decision = cr.customer_result("ANSWER", 1, 3, NOW, 60)
    assert (decision.status, decision.next_attempt_at, decision.last_error) == ("connected", None, None)


def test_customer_result_no_answer_retries_then_fails():
    retry = cr.customer_result("NOANSWER", 1, 3, NOW, 60)
    assert (retry.status, retry.last_error) == ("pending", "customer_NOANSWER")
    final = cr.customer_result("NOANSWER", 3, 3, NOW, 60)
    assert final.status == "failed"


# ------------------------------------------------------------------ A1: dialplan
def test_callback_context_lines_urls_and_flow():
    lines = callback_context_lines("t9", "http://api:8000", "tok")
    text = "\n".join(lines)
    assert "Set(CHANNEL(hangup_handler_push)=t9-callback-ophang,s,1)" in text
    assert "Goto(${INNOVA_CB_DESTCTX},s,1)" in text
    assert ("http://api:8000/internal/callback/result?token=tok&request=${INNOVA_CB_REQUEST}"
            "&stage=operator&status=${DIALSTATUS}") in text
    assert ("http://api:8000/internal/callback/result?token=tok&request=${INNOVA_CB_REQUEST}"
            "&stage=customer&status=${DIALSTATUS}&linkedid=${CHANNEL(linkedid)}") in text
    assert "Set(CHANNEL(hangup_handler_push)=t9-callback-custhang,s,1)" in text
    assert "Goto(t9-outbound-rg,${INNOVA_CB_PHONE},1)" in text
    assert lines.count(" same => n,Return()") == 2


def test_callback_context_lines_set_accountcode_to_tenant_code_only():
    """M12 A4: CDR `accountcode` tenant kodiga o'rnatiladi — boshqa CDR
    maydoni (userfield/disposition/...) soxtalashtirilmaydi."""
    lines = callback_context_lines("t9", "http://api:8000", "tok")
    text = "\n".join(lines)
    assert text.count("Set(CDR(accountcode)=t9)") == 2
    assert "CDR(disposition)" not in text
    assert "CDR(userfield)" not in text


def test_callback_contexts_in_compiled_dialplan():
    out = compile_dialplan(_snapshot())
    for ctx in ("t1-callback-dial", "t1-callback-ophang", "t1-callback-answer", "t1-callback-custhang"):
        assert f"[{ctx}]" in out
    assert out.index("[t1-outbound-rg]") < out.index("[t1-callback-dial]")


# ------------------------------------------------------------------ A1: ichki endpoint
def test_check_token(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    assert ic._check_token("good") is True
    assert ic._check_token("bad") is False


def test_check_token_empty_denies(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "")
    assert ic._check_token("") is False


async def test_callback_result_bad_token_no_db(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    resp = await ic.callback_result(token="bad", request="r-1", stage="operator", status="ANSWER", session=None)
    assert resp.body == b"0"


async def test_callback_result_missing_request_no_db(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    resp = await ic.callback_result(token="good", request="", stage="operator", session=None)
    assert resp.body == b"0"


async def test_callback_result_unknown_stage_no_db(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "good")
    resp = await ic.callback_result(token="good", request="r-1", stage="unknown", session=None)
    assert resp.body == b"0"


# ------------------------------------------------------------------ A1: fon tsikl (dialer)
async def test_callback_dialer_run_forever_skips_in_maintenance_and_survives_errors(monkeypatch):
    import asyncio

    from app.services import callback_dialer as dialer
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
    assert calls == ["cycle", "cycle"]
    assert sleeps == [1.5, 1.5, 1.5]


# ------------------------------------------------------------------ A2: missed_call_rules
@pytest.mark.parametrize(("scope_kind", "scope_value", "call", "ring_numbers", "expected"), [
    ("any", None, {}, frozenset(), True),
    ("did", "100200", {"did": "100200"}, frozenset(), True),
    ("did", "100200", {"did": "999"}, frozenset(), False),
    ("did", None, {"did": "100200"}, frozenset(), False),
    ("queue", "q1", {"queue": {"id": "q1"}}, frozenset(), True),
    ("queue", "q1", {"queue": {"id": "q2"}}, frozenset(), False),
    ("queue", "q1", {}, frozenset(), False),
    ("extension", "201", {"extension": "201"}, frozenset(), True),
    ("extension", "201", {"extension": "202"}, frozenset(), False),
    ("ring_group", "rg1", {"extension": "201"}, frozenset({"201", "202"}), True),
    ("ring_group", "rg1", {"extension": "203"}, frozenset({"201", "202"}), False),
    ("ring_group", "rg1", {}, frozenset({"201"}), False),
    ("unknown", "x", {}, frozenset(), False),
])
def test_rule_matches(scope_kind, scope_value, call, ring_numbers, expected):
    assert mr.rule_matches(scope_kind, scope_value, call, ring_group_numbers=ring_numbers) is expected


@pytest.mark.parametrize(("status", "expected"), [("missed", True), ("answered", False), ("", False), (None, False)])
def test_is_missed(status, expected):
    assert mr.is_missed({"status": status}) is expected


def test_missed_call_text_languages_and_fallback():
    call = {"from": "998901112233", "to": "100", "started_at": "2026-11-03T10:00:00+00:00"}
    uz = mr.missed_call_text("uz", call)
    ru = mr.missed_call_text("ru", call)
    en = mr.missed_call_text("en", call)
    fallback = mr.missed_call_text("fr", call)
    assert "O'tkazib yuborilgan" in uz
    assert "Пропущенный" in ru
    assert "Missed call" in en
    assert fallback == uz
    assert "998901112233" in uz and "100" in uz


def test_missed_call_text_missing_fields_use_placeholders():
    text = mr.missed_call_text("uz", {})
    assert "noma'lum" in text and "-" in text


@pytest.mark.parametrize(("include_internal", "direction", "expected"), [
    (True, "internal", True), (True, "external", True), (False, "internal", False), (False, "external", True),
])
def test_rule_included(include_internal, direction, expected):
    assert mr.rule_included(include_internal, direction) is expected


# ------------------------------------------------------------------ A2: fon tsikl (missed_call_notify)
async def test_missed_notify_run_forever_skips_in_maintenance_and_survives_errors(monkeypatch):
    import asyncio

    from app.services import maintenance
    from app.services import missed_call_notify as notify

    calls: list[str] = []
    sleeps: list[float] = []

    async def fake_cycle(factory):
        calls.append("cycle")
        raise RuntimeError("bazada xato")

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:
            monkeypatch.setattr(maintenance.state, "enabled", False)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(notify, "notify_cycle", fake_cycle)
    monkeypatch.setattr(notify.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(maintenance.state, "enabled", True)
    with pytest.raises(asyncio.CancelledError):
        await notify.run_forever(None, 2.0)
    assert calls == ["cycle", "cycle"]
    assert sleeps == [2.0, 2.0, 2.0]


# ------------------------------------------------------------------ A3: tts_yandex
def test_voice_for_language_then_uz_then_any():
    cfg = tts.TtsConfig(provider="yandex", api_key="k", folder_id="f", voices={"uz": "nigora", "ru": "alena"})
    assert tts.voice_for(cfg, "ru") == "alena"
    assert tts.voice_for(cfg, "en") == "nigora"  # uz zahira
    empty = tts.TtsConfig(provider="yandex", api_key="k", folder_id="f", voices={})
    assert tts.voice_for(empty, "en") == "alena"  # umuman bo'sh bo'lsa so'nggi zahira


def test_lpcm_ffmpeg_args():
    assert tts.lpcm_ffmpeg_args() == ("-f", "s16le", "-ar", "8000", "-ac", "1")


async def test_synthesize_lpcm_success_with_fake_transport():
    cfg = tts.TtsConfig(provider="yandex", api_key="sekret-kalit", folder_id="f1", voices={"uz": "nigora"})
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.read()
        return httpx.Response(200, content=b"\x00\x01\x02\x03")

    out = await tts.synthesize_lpcm(cfg, "Salom", "uz", transport=httpx.MockTransport(handler))
    assert out == b"\x00\x01\x02\x03"
    assert captured["auth"] == "Api-Key sekret-kalit"
    assert "speech/v1/tts:synthesize" in captured["url"]
    assert b"lang=uz-UZ" in captured["body"] and b"voice=nigora" in captured["body"]


async def test_synthesize_lpcm_non_200_raises_tts_error_without_leaking_key():
    cfg = tts.TtsConfig(provider="yandex", api_key="sekret-kalit", folder_id="f1", voices={"uz": "nigora"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden: sekret-kalit")

    with pytest.raises(tts.TtsError) as exc:
        await tts.synthesize_lpcm(cfg, "Salom", "uz", transport=httpx.MockTransport(handler))
    assert "403" in str(exc.value)


async def test_synthesize_lpcm_network_error_raises_tts_error():
    cfg = tts.TtsConfig(provider="yandex", api_key="k", folder_id="f1", voices={"uz": "nigora"})

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    with pytest.raises(tts.TtsError):
        await tts.synthesize_lpcm(cfg, "Salom", "uz", transport=httpx.MockTransport(handler))
