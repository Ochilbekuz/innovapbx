"""`<code>-outbound`/`<code>-outbound-rg` kontekstlari — sof funksiya, bazasiz
(ub-mode TDD). m1b-contract.md bo'lim 2 va 9 (isbot ssenariylari 1-3,5)."""
from __future__ import annotations

from app.services.compiler import (
    DialplanSnapshot,
    ExtensionCallerIdSnapshot,
    OutboundPatternSnapshot,
    OutboundRouteSnapshot,
    OutboundTrunkSnapshot,
    compile_dialplan,
)


def _uz_route(**kw) -> OutboundRouteSnapshot:
    defaults = dict(
        id="route-uz", name="UZ", priority=1, enabled=True, international=False,
        patterns=(OutboundPatternSnapshot(strip_prefix="0", pattern="XXXXXXXXX", add_prefix="998"),),
        trunks=(
            OutboundTrunkSnapshot(position=1, id="trunk-a", name="Trunk A"),
            OutboundTrunkSnapshot(position=2, id="trunk-b", name="Trunk B"),
        ),
    )
    defaults.update(kw)
    return OutboundRouteSnapshot(**defaults)


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(tenant_code="t1", outbound_routes=[_uz_route()])
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def _outbound_ctx(text: str) -> str:
    return text.split("[t1-outbound]")[1].split("[t1-outbound-rg]")[0]


def test_outbound_context_exists_and_outbound_rg_context_exists():
    text = compile_dialplan(_snapshot())
    assert "[t1-outbound]" in text
    assert "[t1-outbound-rg]" in text


def test_from_internal_falls_through_to_outbound_on_chanunavail():
    text = compile_dialplan(_snapshot())
    # M2a: endpoint mavjudligi realtime'da tekshiriladi (CHANUNAVAIL emas) —
    # ro'yxatdan o'tmagan ichki raqam chiquvchi marshrutga ketmaydi.
    ext = text.split("[t1-ext]")[1].split("[t1-ext-call]")[0]
    assert ('exten => _X.,1,GotoIf($["${REALTIME_FIELD(ext_state,endpoint,${EXTEN},endpoint)}"=""]'
            '?t1-outbound,${EXTEN},1)') in ext


def test_pattern_strip_and_regex_present():
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert "Set(INNOVA_STRIPPED=${EXTEN:1})" in ctx
    assert 'REGEX("^[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]$"' in ctx
    assert "Set(INNOVA_DIALED=998${INNOVA_STRIPPED})" in ctx


def test_regex_call_uses_space_not_comma_before_subject_argument():
    """Ishlab chiqarish xatosi (m1b-contract.md bo'lim 9 ssenariy 1/4 orqali
    SIP darajasida topildi): Asterisk'ning `REGEX()` funksiyasi
    `AST_NONSTANDARD_APP_ARGS(args, parse, '"')` bilan `"<regex>" <satr>`
    (BO'SHLIQ bilan ajratilgan, VERGUL bilan EMAS) kutadi -- u faqat
    yopilgan qo'shtirnoqdan keyingi BO'SHLIQ/TAB'ni, vergulni EMAS, tashlab
    yuboradi (`funcs/func_strings.c`). Vergul bilan chaqirilsa
    `args.str` = ",<qiymat>" bo'lib qoladi -- natijada bosh `^` langar HECH
    QACHON mos kelmaydi (chunki satr har doim "," bilan boshlanadi), lekin
    langarsiz naqshlar tasodifan mos kelgandek ko'rinadi (yashiringan xato).
    Tasdiqlangan: `docker exec ... asterisk -rx` orqali jonli, `FUNCTION
    REGEX (^a)(,abc)` -> natija '0', bo'shliq bilan -> `(^a)(abc)` -> '1'."""
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert 'REGEX("^[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]$" ${INNOVA_STRIPPED})' in ctx
    assert 'REGEX("^[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]$",${INNOVA_STRIPPED})' not in ctx


def test_trunk_failover_goes_to_next_trunk_on_chanunavail_or_congestion():
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert 'Dial(PJSIP/${INNOVA_DIALED}@t1-trunk-trunk-a,30,U(innova-rec))' in ctx
    assert 'Dial(PJSIP/${INNOVA_DIALED}@t1-trunk-trunk-b,30,U(innova-rec))' in ctx
    # trunk A muvaffaqiyatsiz bo'lsa (CHANUNAVAIL/CONGESTION) — trunk B'ga o'tadi
    assert "r1_dial2" in ctx
    assert "r1_all_failed" in ctx


def test_no_trunk_route_has_no_dial_at_all():
    text = compile_dialplan(_snapshot(outbound_routes=[_uz_route(trunks=())]))
    ctx = _outbound_ctx(text)
    assert "Dial(PJSIP/${INNOVA_DIALED}" not in ctx
    assert "r1_all_failed" in ctx  # bo'sh trunk ro'yxati -> darhol Congestion


def test_international_false_blocks_foreign_numbers_before_dial():
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert 'GotoIf($["${EXTEN:0:2}"="00"]?r1_intl00)' in ctx
    assert 'GotoIf($["${EXTEN:0:1}"="+"]?r1_intlplus)' in ctx
    assert 'GotoIf($["${EXTEN:2:3}"="998"]?r1_patterns)' in ctx
    assert 'GotoIf($["${EXTEN:1:3}"="998"]?r1_patterns)' in ctx


def test_international_true_route_has_no_block_check():
    text = compile_dialplan(_snapshot(outbound_routes=[_uz_route(international=True)]))
    ctx = _outbound_ctx(text)
    assert "r1_intl00" not in ctx


def test_pin_route_uses_curl_to_internal_endpoint():
    text = compile_dialplan(_snapshot(
        outbound_routes=[_uz_route(has_pin=True)],
        internal_api_base_url="http://api:8000", internal_api_token="secret-tok",
    ))
    ctx = _outbound_ctx(text)
    # "beep" FAYL NOMI ataylab ISHLATILMAYDI -- core-sounds o'rnatilmagan
    # muhitda (masalan shu loyihaning Asterisk image'ida) fayl topilmay,
    # Read() raqam terish tsikliga kirmasdan "User disconnected" bilan
    # darhol chiqib ketadi (jonli SIP isbotida topilgan ishlab chiqarish
    # xatosi, 2026-10-28 -- compiler.py "_route_pin_lines" izohi).
    assert "Read(INNOVA_PIN,,8)" in ctx
    assert "beep" not in ctx
    assert "CURL(http://api:8000/internal/outbound-routes/route-uz/pin-check?token=secret-tok" in ctx
    assert 'GotoIf($["${INNOVA_PIN_OK}"="1"]?r1_cid)' in ctx


def test_route_without_pin_has_no_pin_check_curl_call():
    """PIN yo'q bo'lsa `pin-check`ga CURL chiqmaydi — lekin M2c §3 toll-fraud
    `/internal/toll/check` CURL'i har doim (PIN bor-yo'qligidan qat'i nazar,
    `-outbound` kontekstida) chiqadi, shuning uchun "CURL( umuman yo'q" emas,
    aniq `pin-check` yo'qligi tekshiriladi."""
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert "pin-check" not in ctx
    assert "/internal/toll/check" in ctx


def test_callerid_override_sets_route_callerid_unconditionally():
    text = compile_dialplan(_snapshot(outbound_routes=[
        _uz_route(callerid="999000", override_extension_callerid=True),
    ]))
    ctx = _outbound_ctx(text)
    assert "Set(CALLERID(num)=999000)" in ctx


def test_callerid_extension_cid_lookup_present_for_known_extensions():
    text = compile_dialplan(_snapshot(
        extension_callerids=(ExtensionCallerIdSnapshot(number="101", outbound_callerid="555111"),),
    ))
    ctx = text.split("[t1-outbound]")[1].split("[t1-outbound-rg]")[0]
    assert 'IF($["${INNOVA_SRC_EXT}"="101"?"555111":${INNOVA_EXT_CID})' in ctx


def test_trunk_outbound_callerid_set_only_when_cid_not_already_resolved():
    text = compile_dialplan(_snapshot(outbound_routes=[_uz_route(
        trunks=(OutboundTrunkSnapshot(position=1, id="trunk-a", name="Trunk A",
                                       outbound_callerid="998712223344"),),
    )]))
    ctx = _outbound_ctx(text)
    assert "Set(CALLERID(num)=998712223344)" in ctx


def test_extension_allow_list_filters_by_callerid_num():
    text = compile_dialplan(_snapshot(outbound_routes=[
        _uz_route(allowed_extension_numbers=("101", "102")),
    ]))
    ctx = _outbound_ctx(text)
    assert '$["${INNOVA_SRC_EXT}"="101"] | $["${INNOVA_SRC_EXT}"="102"]' in ctx


def test_outbound_rg_context_has_no_extension_filter_even_when_route_restricts():
    text = compile_dialplan(_snapshot(outbound_routes=[
        _uz_route(allowed_extension_numbers=("101",)),
    ]))
    rg_ctx = text.split("[t1-outbound-rg]")[1]
    assert "INNOVA_SRC_EXT" not in rg_ctx


def test_disabled_route_is_not_compiled_at_all():
    text = compile_dialplan(_snapshot(outbound_routes=[_uz_route(enabled=False)]))
    ctx = _outbound_ctx(text)
    assert "r1_start" not in ctx
    assert "no_route" in ctx


def test_route_priority_order_lower_number_checked_first():
    second = _uz_route(id="route-any", name="Any", priority=2,
                        patterns=(OutboundPatternSnapshot(strip_prefix="", pattern=".", add_prefix=""),))
    text = compile_dialplan(_snapshot(outbound_routes=[second, _uz_route(priority=1)]))
    ctx = _outbound_ctx(text)
    # priority=1 (UZ) r1 bo'lib kompilyatsiya qilinishi kerak (birinchi tekshiriladi)
    assert ctx.index("marshrut UZ") < ctx.index("marshrut Any")


def test_dialplan_is_deterministic_same_input_same_output():
    a = compile_dialplan(_snapshot())
    b = compile_dialplan(_snapshot())
    assert a == b


def test_from_internal_blocks_outbound_for_extension_with_outbound_allowed_false():
    """m1b-contract.md bo'lim 9 ssenariy 3: `outbound_allowed=false` ichki
    raqam -> rad. Extension.outbound_allowed hozircha FAQAT
    /outbound-routes/simulate'da tekshirilardi, haqiqiy dialplan'da
    (`[t1-from-internal]`) hech qachon tekshirilmasdi -- ishlab chiqarish
    xatosi. Bloklangan raqam chiquvchi kontekstga O'TMASLIGI kerak."""
    text = compile_dialplan(_snapshot(outbound_blocked_extension_numbers=("102",)))
    # M2a: tekshiruv chiquvchi kontekstning o'zida (yo'naltirishda ham — yo'naltiruvchi ext).
    out = _outbound_ctx(text)
    assert 'GotoIf($["${INNOVA_SRC_EXT}"="102"]?outbound_blocked)' in out
    assert " same => n(outbound_blocked),NoOp(" in out
    assert out.index("?outbound_blocked)") < out.index("n(r1_start)")
    assert "Congestion()" in out.split("n(outbound_blocked)")[1]


def test_from_internal_has_no_block_check_when_no_blocked_extensions():
    """Bloklangan raqamlar ro'yxati bo'sh bo'lsa -- qo'shimcha tekshiruv
    umuman qo'shilmasligi kerak (mavjud ssenariylarga ta'sir qilmasligi uchun)."""
    text = compile_dialplan(_snapshot())
    fi = text.split("[t1-from-internal]")[1].split("[t1-from-trunk]")[0]
    assert "outbound_blocked" not in fi


def test_toll_curl_uri_encodes_caller_controlled_values():
    """Terilgan raqam (SIP URI user qismida `&`/`=` bo'lishi mumkin) va ext URL'ga
    URIENCODE bilan qo'yiladi — aks holda `0099..&ext=102` terib, limitni boshqa
    ichki raqam hisobiga o'tkazish (toll-fraud chetlab o'tish) mumkin edi."""
    ctx = _outbound_ctx(compile_dialplan(_snapshot()))
    assert "&ext=${URIENCODE(${INNOVA_SRC_EXT})}" in ctx
    assert "&number=${URIENCODE(${INNOVA_DIALED})}" in ctx
    assert "number=${INNOVA_DIALED}" not in ctx


# ------------------------------------------------------------ M3b §1 yozuv
def test_every_dial_and_queue_goes_through_innova_rec():
    """Bitta yordamchi: har `Dial(`/`Queue(` oldidan prep, oxirida `U(innova-rec)`/gosub."""
    from tests.test_compiler import _rg, _rg_targets, _route
    from app.services.compiler import ExtensionSnapshot, QueueSnapshot, TargetSnapshot

    targets = {**_rg_targets(), "queue-1": TargetSnapshot(id="queue-1", kind="queue", label="Q"),
               "ext-101": TargetSnapshot(id="ext-101", kind="extension", label="101")}
    text = compile_dialplan(_snapshot(
        extensions=[ExtensionSnapshot(id="e1", number="101", name="A", ring_seconds=20, target_id="ext-101")],
        targets=targets, ring_groups=[_rg()],
        inbound_routes=[_route(target_id="rg-1"), _route(did="712000001", target_id="queue-1")],
        queues=[QueueSnapshot(id="q1", target_id="queue-1", name="Q", max_wait_seconds=60,
                              timeout_target_id="hangup-1")],
    ))
    lines = text.splitlines()
    dials = [i for i, line in enumerate(lines) if ",Dial(" in line or ",Queue(" in line]
    assert len(dials) >= 5  # ext-call, RG, navbat, 2 trunk (outbound) + 2 trunk (outbound-rg)
    for i in dials:
        assert lines[i - 1] == " same => n,Gosub(innova-rec-prep,s,1)", lines[i]
        assert lines[i].endswith("U(innova-rec))") or lines[i].endswith(",,innova-rec)"), lines[i]
    assert " same => n,Set(__INNOVA_QUEUE=q1)" in text
    assert " same => n,Set(__INNOVA_DID=${EXTEN})" in text
    assert text.count("[innova-rec]") == 1 and "[t1-originate]" in text


def test_outbound_sets_inherited_recording_source_only_with_extension_filter():
    text = compile_dialplan(_snapshot())
    outbound = _outbound_ctx(text)
    rg = text.split("[t1-outbound-rg]")[1]
    src = " same => n,Set(__INNOVA_REC_SRC=t1-${INNOVA_SRC_EXT})"
    assert src in outbound and src not in rg
