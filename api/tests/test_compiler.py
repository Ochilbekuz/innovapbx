"""Kompilyator — sof funksiya, bazasiz test qilinadi (ub-mode: TDD, mutator nishoni)."""
from __future__ import annotations

import re

import pytest

from app.services.compiler import (
    CompileError,
    DialNumberSnapshot,
    DialplanSnapshot,
    ExtensionSnapshot,
    InboundRouteSnapshot,
    IvrOptionSnapshot,
    IvrSnapshot,
    QueueSnapshot,
    RingGroupMemberSnapshot,
    RingGroupSnapshot,
    TargetSnapshot,
    TimeConditionSnapshot,
    TimeRangeSnapshot,
    compile_dialplan,
    dialplan_sha256,
)


def _ext(number="101", target_id="ext-101", no_answer=None) -> ExtensionSnapshot:
    return ExtensionSnapshot(id="e1", number=number, name="Dilnoza",
                              ring_seconds=25, target_id=target_id,
                              no_answer_target_id=no_answer)


def _route(did="712000000", target_id="ext-101", cid="", enabled=True) -> InboundRouteSnapshot:
    return InboundRouteSnapshot(id="r1", did=did, callerid_pattern=cid,
                                 target_id=target_id, enabled=enabled)


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(
        tenant_code="t1",
        extensions=[_ext()],
        targets={"ext-101": TargetSnapshot(id="ext-101", kind="extension", label="101 · Dilnoza")},
        inbound_routes=[_route()],
    )
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def test_generates_static_from_internal_context():
    text = compile_dialplan(_snapshot())
    assert "[t1-from-internal]" in text
    # M2a: ichki raqamga qo'ng'iroq — yagona `<code>-ext` oqimi (DND/yo'naltirish realtime).
    assert " same => n,Goto(t1-ext,${EXTEN},1)" in text.split("[t1-ext]")[0]
    assert "Dial(${INNOVA_DIAL:1},${INNOVA_RING}," in text


def test_from_internal_is_independent_of_extension_list():
    """Reload shart emas — kontekst ichki raqamlar ro'yxatiga bog'liq emas."""
    one = compile_dialplan(_snapshot(extensions=[_ext()]))
    many = compile_dialplan(_snapshot(extensions=[_ext(), _ext(number="102", target_id="ext-102")]))
    from_internal = lambda t: t.split("[t1-ext]")[0]
    assert from_internal(one) == from_internal(many)


def test_inbound_route_dials_target_extension():
    text = compile_dialplan(_snapshot())
    assert "exten => 712000000,1" in text
    assert "Set(CDR(userfield)=${EXTEN})" in text
    assert "Goto(t1-dest-ext-101,s,1)" in text
    assert "[t1-dest-ext-101]" in text
    assert "Goto(t1-ext,101,1)" in text.split("[t1-dest-ext-101]")[1]
    assert "exten => 101,1,NoOp(Innova: Dilnoza <101>)\n same => n,Set(INNOVA_RING=25)" in text


def test_disabled_route_is_excluded():
    text = compile_dialplan(_snapshot(inbound_routes=[_route(enabled=False)]))
    assert "712000000" not in text


def test_catchall_route_uses_dot_pattern():
    text = compile_dialplan(_snapshot(inbound_routes=[_route(did="")]))
    assert "exten => _.,1,NoOp(Innova: kiruvchi har qanday)" in text


def test_callerid_pattern_adds_conditional_match():
    """(LOW tuzatish) `CALLERID(num)` endi `FILTER(0-9+,...)` bilan tor
    belgi to'plamiga qisqartiriladi (qo'shtirnoq/operator in'ektsiyasidan
    himoya) — solishtiruvning o'zi o'zgarmagan, faqat chap tomon o'ralgan."""
    text = compile_dialplan(_snapshot(inbound_routes=[_route(cid="+99890*")]))
    assert '${FILTER(0-9+,${CALLERID(num)})}"="+99890*"' in text
    assert "(matched)" in text


def test_unknown_target_is_safe_fallback_not_crash():
    text = compile_dialplan(_snapshot(inbound_routes=[_route(target_id="missing")]))
    assert "[t1-dest-missing]" in text
    assert "Hangup(1)" in text


def test_target_kind_other_than_extension_hangs_up_safely():
    snap = _snapshot(
        targets={"q1": TargetSnapshot(id="q1", kind="queue", label="Navbat")},
        inbound_routes=[_route(target_id="q1")],
    )
    text = compile_dialplan(snap)
    assert "qo'llab-quvvatlanmagan manzil turi queue" in text
    assert "Hangup(34)" in text


def test_no_answer_forward_chain_is_compiled():
    snap = _snapshot(
        extensions=[_ext(no_answer="ext-102"), _ext(number="102", target_id="ext-102")],
        targets={
            "ext-101": TargetSnapshot(id="ext-101", kind="extension", label="101"),
            "ext-102": TargetSnapshot(id="ext-102", kind="extension", label="102"),
        },
    )
    text = compile_dialplan(snap)
    entry_101 = text.split("exten => 101,1,")[1].split("exten => 102,1,")[0]
    assert " same => n,Set(INNOVA_NOANS=t1-dest-ext-102)" in entry_101
    assert "[t1-dest-ext-102]" in text


def test_no_answer_self_cycle_raises_compile_error():
    snap = _snapshot(extensions=[_ext(no_answer="ext-101")])
    with pytest.raises(CompileError):
        compile_dialplan(snap)


def test_no_answer_two_node_cycle_raises_compile_error():
    snap = _snapshot(
        extensions=[_ext(no_answer="ext-102"), _ext(number="102", target_id="ext-102", no_answer="ext-101")],
    )
    with pytest.raises(CompileError):
        compile_dialplan(snap)


def test_sha256_is_deterministic_and_sensitive_to_change():
    a = compile_dialplan(_snapshot())
    b = compile_dialplan(_snapshot())
    assert dialplan_sha256(a) == dialplan_sha256(b)
    c = compile_dialplan(_snapshot(inbound_routes=[_route(did="799999999")]))
    assert dialplan_sha256(a) != dialplan_sha256(c)


# ============================================================ M1a: ish vaqti

def _tc(**kw) -> TimeConditionSnapshot:
    defaults = dict(
        id="tc1", target_id="tc-1", name="Ish kunlari",
        ranges=(TimeRangeSnapshot(weekdays=(1, 2, 3, 4, 5), start="09:00", end="18:00"),),
        honor_holidays=False, override="auto",
        open_target_id="ext-101", closed_target_id="hangup-1", toggle_code=None,
    )
    defaults.update(kw)
    return TimeConditionSnapshot(**defaults)


def _tc_targets() -> dict[str, TargetSnapshot]:
    return {
        "tc-1": TargetSnapshot(id="tc-1", kind="time_condition", label="Ish kunlari"),
        "ext-101": TargetSnapshot(id="ext-101", kind="extension", label="101"),
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
    }


def test_time_condition_auto_mode_checks_schedule_then_branches():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc()],
    )
    text = compile_dialplan(snap)
    assert "[t1-dest-tc-1]" in text
    # Hafta kunlari `&` bilan: vergul GotoIfTime maydon ajratuvchisi — `mon,tue,...` da Asterisk
    # faqat `mon` ni kun deb oladi (jonli isbot 2026-11-04: chorshanba kun bo'yi «yopiq» edi).
    assert "GotoIfTime(09:00-18:00,mon&tue&wed&thu&fri,*,*?open)" in text
    ctx = text.split("[t1-dest-tc-1]")[1].split("[t1-dest-")[0]
    assert "Goto(t1-dest-ext-101,s,1)" in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx
    assert "[t1-dest-hangup-1]" in text and "Busy()" not in text.split("[t1-dest-hangup-1]")[1]


def test_time_condition_force_open_override_skips_schedule():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(override="force_open")],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-tc-1]")[1].split("[t1-dest-")[0]
    assert "GotoIfTime" not in ctx
    assert "Goto(t1-dest-ext-101,s,1)" in ctx


def test_time_condition_force_closed_override_skips_schedule():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(override="force_closed")],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-tc-1]")[1].split("[t1-dest-")[0]
    assert "GotoIfTime" not in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx


def test_time_condition_honors_holidays_with_gotoiftime_date_check():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(honor_holidays=True)], holidays_mmdd=((3, 21), (1, 1)),
    )
    text = compile_dialplan(snap)
    assert "GotoIfTime(*,*,21,3?closed)" in text
    assert "GotoIfTime(*,*,1,1?closed)" in text


def test_time_condition_uses_pbx_timezone_not_asterisk_utc():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(honor_holidays=True)], holidays_mmdd=((3, 21),), timezone="Asia/Tashkent",
    )
    text = compile_dialplan(snap)
    assert "GotoIfTime(*,*,21,3,Asia/Tashkent?closed)" in text
    assert "GotoIfTime(09:00-18:00,mon&tue&wed&thu&fri,*,*,Asia/Tashkent?open)" in text


def test_time_condition_rejects_timezone_unsafe_for_dialplan():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc()], timezone="Asia/Tashkent?open)\nexten => x",
    )
    with pytest.raises(CompileError) as exc:
        compile_dialplan(snap)
    assert exc.value.code == "bad_dialplan_value"


def test_time_condition_toggle_code_stub_added_to_from_internal():
    snap = _snapshot(
        extensions=[_ext()], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(toggle_code="*21")],
    )
    text = compile_dialplan(snap)
    assert "exten => *21,1,NoOp(Innova: Ish kunlari rejim almashtirish" in text


def test_time_condition_open_target_missing_falls_back_safely():
    targets = {k: v for k, v in _tc_targets().items() if k != "ext-101"}
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(open_target_id="ghost-1")],
    )
    text = compile_dialplan(snap)
    assert "[t1-dest-ghost-1]" in text
    assert "Hangup(1)" in text.split("[t1-dest-ghost-1]")[1]


def test_time_condition_open_closed_cycle_raises_loop_error():
    snap = _snapshot(
        extensions=[], targets=_tc_targets(), inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(open_target_id="tc-1")],
    )
    with pytest.raises(CompileError) as exc:
        compile_dialplan(snap)
    assert exc.value.code == "loop"
    assert "path" in exc.value.details


# ===================================================================== IVR

def _ivr(**kw) -> IvrSnapshot:
    defaults = dict(
        id="ivr1", target_id="ivr-1", name="Asosiy menyu", greeting_audio_id="audio-1",
        invalid_audio_id=None, timeout_seconds=7, repeats=2, direct_dial=False,
        timeout_target_id="rg-1", invalid_target_id="hangup-1",
        options=(IvrOptionSnapshot(digit="1", target_id="queue-1"),),
    )
    defaults.update(kw)
    return IvrSnapshot(**defaults)


def _ivr_targets() -> dict[str, TargetSnapshot]:
    return {
        "ivr-1": TargetSnapshot(id="ivr-1", kind="ivr", label="Asosiy menyu"),
        "rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="Guruh"),
        "queue-1": TargetSnapshot(id="queue-1", kind="queue", label="Navbat"),
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
    }


def test_ivr_background_waitexten_and_digit_option():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr()], audio_paths={"audio-1": "/var/lib/innova/sounds/t1/audio-1"},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "Background(/var/lib/innova/sounds/t1/audio-1)" in ctx
    assert "WaitExten(7)" in ctx
    assert "exten => 1,1,Goto(t1-dest-queue-1,s,1)" in ctx


def test_ivr_repeats_then_goes_to_timeout_target():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr()], audio_paths={},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "GotoIf($[${IVR_REPEAT} <= 2]?s,menu)" in ctx
    assert "Goto(t1-dest-rg-1,s,1)" in ctx


def test_ivr_invalid_goes_to_invalid_target():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr()], audio_paths={},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "exten => i,1" in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx


def test_ivr_direct_dial_true_adds_internal_catchall():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr(direct_dial=True)], audio_paths={},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "exten => _X.,1,Goto(t1-from-internal,${EXTEN},1)" in ctx


def test_ivr_direct_dial_false_has_no_internal_catchall():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr(direct_dial=False)], audio_paths={},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "_X." not in ctx


def test_ivr_timeout_self_loop_raises_loop_error_with_path():
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr(timeout_target_id="ivr-1")],
    )
    with pytest.raises(CompileError) as exc:
        compile_dialplan(snap)
    assert exc.value.code == "loop"
    assert "Asosiy menyu" in exc.value.details["path"]


def test_ivr_digit_option_self_reference_is_allowed_not_a_loop():
    """Tugma orqali halqa — qo'ng'iroq qiluvchi tanlaydi, ruxsat (m1a-contract.md)."""
    snap = _snapshot(
        extensions=[], targets=_ivr_targets(), inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr(options=(IvrOptionSnapshot(digit="9", target_id="ivr-1"),))],
    )
    text = compile_dialplan(snap)  # CompileError ko'tarilmasligi kerak
    assert "exten => 9,1,Goto(t1-dest-ivr-1,s,1)" in text


# ============================================================ qo'ng'iroq guruhi

def _rg(**kw) -> RingGroupSnapshot:
    defaults = dict(
        id="rg1", target_id="rg-1", name="Savol-javob", strategy="ringall", ring_seconds=20,
        no_answer_target_id="hangup-1",
        members=(RingGroupMemberSnapshot(position=1, extension_number="101"),
                 RingGroupMemberSnapshot(position=2, extension_number="102")),
    )
    defaults.update(kw)
    return RingGroupSnapshot(**defaults)


def _rg_sets(ctx: str) -> list[list[str]]:
    """Runtime'da yig'iladigan `Dial()` to'plamlari (M2a: DND a'zo tashlab ketiladi).
    Ichki a'zo `PJSIP/<n>` ko'rinishida — `innova-dial-contacts` uning BARCHA kontaktlarini qo'shadi."""
    sets: list[list[str]] = []
    for line in ctx.splitlines():
        if line == " same => n,Set(INNOVA_DIAL=)":
            sets.append([])
        elif "INNOVA_DIAL=${INNOVA_DIAL}&" in line:
            sets[-1].append(line.split("INNOVA_DIAL=${INNOVA_DIAL}&")[1].rstrip(")"))
        elif "innova-dial-contacts,s,1(" in line:
            sets[-1].append("PJSIP/" + line.split("innova-dial-contacts,s,1(")[1].rstrip(")"))
    return sets


def _rg_targets() -> dict[str, TargetSnapshot]:
    return {
        "rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="Savol-javob"),
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
    }


def test_ring_group_ringall_dials_all_members_at_once():
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg()],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-rg-1]")[1].split("[t1-dest-")[0]
    assert _rg_sets(ctx) == [["PJSIP/101", "PJSIP/102"]]
    assert "Dial(${INNOVA_DIAL:1},20," in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx


def test_ring_group_hunt_dials_members_sequentially():
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg(strategy="hunt")],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-rg-1]")[1].split("[t1-dest-")[0]
    assert _rg_sets(ctx) == [["PJSIP/101"], ["PJSIP/102"]]


def test_ring_group_memoryhunt_rings_growing_set_of_members():
    """memoryhunt: 1-a'zo, keyin 1+2, keyin 1+2+3 — oldingilar jiringlashda davom etadi."""
    members = tuple(RingGroupMemberSnapshot(position=i, extension_number=n)
                    for i, n in enumerate(("101", "102", "103"), start=1))
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg(strategy="memoryhunt", members=members)],
    )
    ctx = compile_dialplan(snap).split("[t1-dest-rg-1]")[1].split("[t1-dest-")[0]
    assert _rg_sets(ctx) == [["PJSIP/101"], ["PJSIP/101", "PJSIP/102"],
                             ["PJSIP/101", "PJSIP/102", "PJSIP/103"]]


def test_ring_group_without_members_falls_back_to_no_answer():
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg(members=())],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-rg-1]")[1].split("[t1-dest-")[0]
    assert "PJSIP" not in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx


def test_ring_group_dial_has_no_cdr_mutation_in_dialplan():
    """QAT'IY TAQIQ (koordinator tuzatishi, 2026-10-27): dialplan hech qachon
    `CDR(...)` ga yozmaydi — bu CDR'ni soxtalashtirish bo'lardi. Haqiqiy
    "javob berildi" holati faqat `/calls` API qatlamida, xom CDR qatorlarini
    uniqueid bo'yicha yig'ib (`_call_out_from_group`), hisoblanadi."""
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg()],
    )
    text = compile_dialplan(snap)
    assert "CDR(disposition)" not in text
    assert "exten => h,1" not in text
    # `DIALSTATUS` M1b'da `t1-outbound`/`t1-from-internal`da haqiqiy trunk
    # failover uchun ishlatiladi (m1b-contract.md bo'lim 2) — bu CDR'ni
    # soxtalashtirmaydi (Set(CDR(...))ga ULANMAGAN), shuning uchun taqiq
    # faqat qo'ng'iroq GURUHI dest-kontekstiga tegishli bo'lishi kerak.
    rg_ctx = text.split("[t1-dest-rg-1]")[1].split("\n[")[0]  # faqat shu kontekst (keyingi `[...]` gacha)
    assert "DIALSTATUS" not in rg_ctx
    # Qonuniy metama'lumot yozuvlari (tenant/DID) — bular disposition emas,
    # qolishi SHART (M0; `/calls` ularga tayanadi).
    assert "CDR(accountcode)" in text


def test_ring_group_no_answer_self_loop_raises_loop_error():
    snap = _snapshot(
        extensions=[], targets=_rg_targets(), inbound_routes=[_route(target_id="rg-1")],
        ring_groups=[_rg(no_answer_target_id="rg-1")],
    )
    with pytest.raises(CompileError) as exc:
        compile_dialplan(snap)
    assert exc.value.code == "loop"


# ===================================================================== navbat

def test_queue_dest_uses_queue_app_and_timeout_target():
    targets = {
        "queue-1": TargetSnapshot(id="queue-1", kind="queue", label="Qabul"),
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
    }
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="queue-1")],
        queues=[QueueSnapshot(id="q1", target_id="queue-1", name="Qabul",
                               max_wait_seconds=120, timeout_target_id="hangup-1")],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-queue-1]")[1].split("[t1-dest-")[0]
    assert "Queue(t1-q-q1,,,,120,,innova-rec)" in ctx
    assert "Goto(t1-dest-hangup-1,s,1)" in ctx


def test_queue_timeout_self_loop_raises_loop_error():
    targets = {"queue-1": TargetSnapshot(id="queue-1", kind="queue", label="Qabul")}
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="queue-1")],
        queues=[QueueSnapshot(id="q1", target_id="queue-1", name="Qabul",
                               max_wait_seconds=120, timeout_target_id="queue-1")],
    )
    with pytest.raises(CompileError) as exc:
        compile_dialplan(snap)
    assert exc.value.code == "loop"


# =========================================================== hangup / busy

def test_hangup_and_busy_terminal_targets_emit_correct_apps():
    targets = {
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
        "busy-1": TargetSnapshot(id="busy-1", kind="busy", label="Mashg'ul"),
    }
    snap = _snapshot(
        extensions=[_ext(no_answer="busy-1")], targets=targets,
        inbound_routes=[_route(target_id="ext-101")],
    )
    text = compile_dialplan(snap)
    assert "[t1-dest-busy-1]" in text
    assert "Busy()" in text.split("[t1-dest-busy-1]")[1]


# ============================================================ raqam ro'yxati

# ===================================================== qo'shimcha chegara holatlari

def test_diamond_shaped_targets_are_not_falsely_flagged_as_loop():
    """Ikki mustaqil yo'l bir xil joyga qo'shilishi (romb shakli) — halqa EMAS."""
    targets = {
        "tc-1": TargetSnapshot(id="tc-1", kind="time_condition", label="Ish kunlari"),
        "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band"),
    }
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="tc-1")],
        time_conditions=[_tc(open_target_id="hangup-1", closed_target_id="hangup-1")],
    )
    text = compile_dialplan(snap)  # CompileError ko'tarilmasligi kerak
    assert "[t1-dest-hangup-1]" in text


def test_ivr_invalid_audio_plays_background_before_goto():
    targets = _ivr_targets()
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="ivr-1")],
        ivrs=[_ivr(invalid_audio_id="audio-invalid")],
        audio_paths={"audio-invalid": "/var/lib/innova/sounds/t1/audio-invalid"},
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ivr-1]")[1].split("[t1-dest-")[0]
    assert "Background(/var/lib/innova/sounds/t1/audio-invalid)" in ctx


def test_extension_target_without_extension_record_falls_back_safely():
    targets = {"ext-ghost": TargetSnapshot(id="ext-ghost", kind="extension", label="Yo'q")}
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[_route(target_id="ext-ghost")],
    )
    text = compile_dialplan(snap)
    ctx = text.split("[t1-dest-ext-ghost]")[1]
    assert "ichki raqam yozuvi yo'q" in ctx
    assert "Hangup(1)" in ctx


def test_dial_numbers_route_from_internal_before_catchall():
    targets = {"rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="Guruh"),
               "hangup-1": TargetSnapshot(id="hangup-1", kind="hangup", label="Band")}
    snap = _snapshot(
        extensions=[], targets=targets, inbound_routes=[],
        ring_groups=[_rg(no_answer_target_id="hangup-1")],
        dial_numbers=[DialNumberSnapshot(number="301", target_id="rg-1")],
    )
    text = compile_dialplan(snap)
    from_internal = text.split("[t1-from-trunk]")[0]
    assert "exten => 301,1,Goto(t1-dest-rg-1,s,1)" in from_internal
    assert from_internal.index("301,1,Goto") < from_internal.index("_X.,1,NoOp")
    # Regressiya (2026-10-28, m1c-proof 5): marshrutga ulanmagan guruhning ichki raqami
    # mavjud bo'lmagan kontekstga Goto qilardi — CDR FAILED, chaqiruvchi 603.
    assert "[t1-dest-rg-1]" in text
    assert _rg_sets(text.split("[t1-dest-rg-1]")[1]) == [["PJSIP/101", "PJSIP/102"]]


# --------------------------------------------------------------------------- dialplan injection (CONFIRMED HIGH)
# Render vaqtidagi IKKINCHI himoya chizig'i (`app/services/dialplan_safety.py`):
# CSV import/FreePBX migratsiyasi `app/schemas.py` Pydantic validatsiyasini chetlab
# o'tishi mumkin, shu sabab `DialplanSnapshot`ga TO'G'RIDAN-TO'G'RI (schema'siz)
# tushgan xavfli qiymat ham kompilyatorda to'xtatilishi/zararsizlanishi SHART.

def _no_injected_line(text: str) -> bool:
    """Haqiqiy yangi dialplan qatori (qator boshida `exten =>`/`same =>`)
    HOSIL BO'LMAGANINI tekshiradi — in'ektsiya qilingan matnning qoldiq
    bo'laklari (masalan, ajratuvchi vergul olib tashlangandan keyingi
    harflar) zararsiz, chunki ular qator boshida EMAS."""
    return not re.search(r"(?m)^\s*(exten|same) => 999\b", text)


def test_extension_name_crlf_is_sanitized_not_injected():
    """Erkin matn (`name`) — qator ko'chirish/boshqaruv belgilar olib tashlanadi
    VA `(`/`)`/`,` kabi ilova-chegara belgilari olib tashlanadi, shu sabab
    in'ektsiya qilingan `System(...)` qatori chaqirilMAYDI, yangi haqiqiy
    `exten =>` qatori HOSIL BO'LMAYDI."""
    evil_name = "Dilnoza\nexten => 999,1,System(rm -rf /)"
    evil_ext = ExtensionSnapshot(id="e1", number="101", name=evil_name, ring_seconds=25, target_id="ext-101")
    text = compile_dialplan(_snapshot(extensions=[evil_ext]))
    assert "System(rm -rf /)" not in text
    assert _no_injected_line(text)


def test_inbound_route_did_with_bad_chars_raises_compile_error():
    """Raqam maydoni (`did`) — faqat tor belgi to'plamiga ruxsat; `$`/`{`/`}`
    kabi o'zgaruvchi almashtirish belgilari KIRITILSA `CompileError` (422)."""
    snap = _snapshot(inbound_routes=[
        InboundRouteSnapshot(id="r1", did="${SHELL(id)}", callerid_pattern="", target_id="ext-101"),
    ])
    with pytest.raises(CompileError) as exc_info:
        compile_dialplan(snap)
    assert exc_info.value.code == "bad_dialplan_value"


def test_inbound_route_cid_name_prefix_crlf_is_sanitized():
    snap = _snapshot(inbound_routes=[
        InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="", target_id="ext-101",
                              cid_name_prefix="X\nexten => 999,1,System(rm -rf /)"),
    ])
    text = compile_dialplan(snap)
    assert "System(rm -rf /)" not in text
    assert _no_injected_line(text)


def test_inbound_route_alert_info_valid_value_is_rendered():
    snap = _snapshot(inbound_routes=[
        InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="", target_id="ext-101",
                              alert_info="Ringtone=1"),
    ])
    text = compile_dialplan(snap)
    assert "Set(__INNOVA_ALERT_INFO=Ringtone=1)" in text


def test_inbound_route_alert_info_injection_raises_compile_error():
    """`alert_info` — `app/schemas.py`da `pattern=_ALERT_INFO_PATTERN` bilan
    tekshiriladi, LEKIN `DialplanSnapshot`ga schema'siz (CSV/FreePBX) kelsa
    ham render vaqtida `CompileError` berilishi SHART (ikkinchi himoya chizig'i)."""
    snap = _snapshot(inbound_routes=[
        InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="", target_id="ext-101",
                              alert_info='x","evil")'),
    ])
    with pytest.raises(CompileError) as exc_info:
        compile_dialplan(snap)
    assert exc_info.value.code == "bad_dialplan_value"
