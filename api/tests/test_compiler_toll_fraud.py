"""`app/services/compiler.py` — M2c §3: toll-fraud dialplan satrlari
(`_toll_intl_detect_lines`, `_toll_concurrent_lines`, `_toll_ext_check_lines`)
va ularning `-outbound`/`-outbound-rg` kontekstlariga ulanishi. Sof funksiya,
bazasiz (ub-mode TDD). m2c-contract.md §3/§7 ssenariy 5-6."""
from __future__ import annotations

from app.services.compiler import (
    DialplanSnapshot,
    OutboundPatternSnapshot,
    OutboundRouteSnapshot,
    OutboundTrunkSnapshot,
    compile_dialplan,
)


def _uz_route(**kw) -> OutboundRouteSnapshot:
    defaults = dict(
        id="route-uz", name="UZ", priority=1, enabled=True, international=False,
        patterns=(OutboundPatternSnapshot(strip_prefix="0", pattern="XXXXXXXXX", add_prefix="998"),),
        trunks=(OutboundTrunkSnapshot(position=1, id="trunk-a", name="Trunk A"),),
    )
    defaults.update(kw)
    return OutboundRouteSnapshot(**defaults)


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(
        tenant_code="t1", outbound_routes=[_uz_route()],
        internal_api_base_url="http://127.0.0.1:8710", internal_api_token="sekret-tok",
    )
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def _ctx(text: str, name: str, next_name: str) -> str:
    return text.split(f"[{name}]")[1].split(f"[{next_name}]")[0]


def _outbound_ctx(text: str) -> str:
    return _ctx(text, "t1-outbound", "t1-outbound-rg")


def _outbound_rg_ctx(text: str) -> str:
    return text.split("[t1-outbound-rg]")[1]


# --------------------------------------------------------------- aniqlash
def test_intl_detect_lines_only_in_outbound_not_outbound_rg():
    """`-outbound-rg` ichki raqam filtrisiz (ring-group) -- xalqaro aniqlash
    ham FAQAT `enforce_extension_filter` bilan birga keladi (599-qator)."""
    text = compile_dialplan(_snapshot())
    assert "INNOVA_TOLL_INTL" in _outbound_ctx(text)
    assert "INNOVA_TOLL_INTL" not in _outbound_rg_ctx(text)


def test_intl_detect_00_prefix_non_uz_sets_flag():
    from app.services.compiler import _toll_intl_detect_lines
    lines = "\n".join(_toll_intl_detect_lines())
    assert 'GotoIf($["${EXTEN:0:2}"="00"]?toll_intl00)' in lines
    assert 'GotoIf($["${EXTEN:2:3}"="998"]?toll_intl_done)' in lines


# ----------------------------------------------------------- bir vaqtdagi
def test_concurrent_lines_absent_when_zero():
    text = compile_dialplan(_snapshot(toll_max_concurrent_outbound=0))
    ctx = _outbound_ctx(text)
    assert "GROUP(" not in ctx
    assert "GROUP_COUNT(" not in ctx


def test_concurrent_lines_present_when_positive_in_both_outbound_contexts():
    """`toll_max_concurrent` -outbound VA -outbound-rg ikkisiga ham o'tadi
    (compile_dialplan ikkalasiga ham `snapshot.toll_max_concurrent_outbound`ni
    beradi) -- ring-group orqali chiquvchi ham umumiy limitga kiradi."""
    text = compile_dialplan(_snapshot(toll_max_concurrent_outbound=3))
    assert "GROUP_COUNT(all@innova_out)} > 3]" in _outbound_ctx(text)
    assert "GROUP_COUNT(all@innova_out)} > 3]" in _outbound_rg_ctx(text)


def test_concurrent_lines_have_curl_timeouts_and_tenant_param():
    text = compile_dialplan(_snapshot(toll_max_concurrent_outbound=1))
    ctx = _outbound_ctx(text)
    assert "Set(CURLOPT(conntimeout)=2)" in ctx
    assert "Set(CURLOPT(httptimeout)=3)" in ctx
    assert "/internal/toll/event?token=sekret-tok&tenant=t1&kind=concurrent_limit" in ctx


def test_concurrent_limit_response_is_ignored_call_continues_on_congestion_path():
    """CURL javobi `INNOVA_TOLL_EVT`ga yoziladi-yu, HECH QANDAY shart
    tekshirilmaydi -- chaqiruv har doim shu yo'lda `Congestion()`ga tushadi
    (hodisa faqat ogohlantirish uchun, javob mazmuni ahamiyatsiz)."""
    text = compile_dialplan(_snapshot(toll_max_concurrent_outbound=1))
    ctx = _outbound_ctx(text)
    assert "Set(INNOVA_TOLL_EVT=${CURL(" in ctx
    assert "same => n,Congestion()" in ctx


# ------------------------------------------------------- ichki raqam limiti
def test_ext_check_only_in_outbound_not_outbound_rg():
    """`-outbound-rg`da `enforce_extension_filter=False` -> `toll_ext_check`
    ham False (compiler.py 665-qator: `toll_ext_check=enforce_extension_filter`)."""
    text = compile_dialplan(_snapshot())
    assert "/internal/toll/check" in _outbound_ctx(text)
    assert "/internal/toll/check" not in _outbound_rg_ctx(text)


def test_ext_check_url_has_tenant_ext_number_intl_params():
    text = compile_dialplan(_snapshot())
    ctx = _outbound_ctx(text)
    assert ("/internal/toll/check?token=sekret-tok&tenant=t1&ext=${URIENCODE(${INNOVA_SRC_EXT})}"
            "&number=${URIENCODE(${INNOVA_DIALED})}&intl=${INNOVA_TOLL_INTL}") in ctx


def test_ext_check_blocks_on_explicit_zero_allows_on_explicit_one():
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert 'GotoIf($["${INNOVA_TOLL_OK}"="0"]?r1_toll_blocked)' in ctx
    assert 'GotoIf($["${INNOVA_TOLL_OK}"="1"]?r1_toll_ok)' in ctx


def test_ext_check_fails_open_for_local_fails_closed_for_international():
    """API bo'sh javob qaytarsa (na "0" na "1") -- xalqaro bo'lsa bloklanadi,
    mahalliy bo'lsa o'tadi (m2c-contract.md §3: fail-closed FAQAT xalqaro)."""
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert 'GotoIf($["${INNOVA_TOLL_INTL}"="1"]?r1_toll_blocked)' in ctx
    assert "same => n,Goto(r1_toll_ok)" in ctx


def test_ext_check_has_curl_timeouts():
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert "Set(CURLOPT(conntimeout)=2)" in ctx
    assert "Set(CURLOPT(httptimeout)=3)" in ctx


# ------------------------------------------------------------- tartib
def test_toll_checks_come_after_callerid_and_before_trunk_dial():
    ctx = _outbound_ctx(compile_dialplan(_snapshot(toll_max_concurrent_outbound=1)))
    order = ["r1_toll1", "GROUP(innova_out)", "/internal/toll/check", "r1_dial1"]
    positions = [ctx.index(token) for token in order]
    assert positions == sorted(positions)
