"""Kompilyator — M2a §1–§3: DND/yo'naltirish (realtime), funksiya kodlari, pickup, transfer, park."""
from __future__ import annotations

import re

from app.services.compiler import (
    ConferenceSnapshot,
    DialNumberSnapshot,
    DialplanSnapshot,
    ExtensionSnapshot,
    InboundRouteSnapshot,
    OutboundPatternSnapshot,
    OutboundRouteSnapshot,
    OutboundTrunkSnapshot,
    RingGroupMemberSnapshot,
    RingGroupSnapshot,
    TargetSnapshot,
    VoicemailBoxSnapshot,
    compile_dialplan,
)
from app.services.dialplan_features import (
    FEATURE_ORDER,
    is_park_number,
    parking_conf_text,
)

_DEFAULT_CODES = {
    "voicemail": "*97", "voicemail_other": "*98", "dnd_toggle": "*76", "cf_always_on": "*72",
    "cf_always_off": "*73", "cf_busy_on": "*90", "cf_busy_off": "*91", "pickup_group": "*8",
    "pickup_direct": "**", "park": "*70", "echo_test": "*43", "speaking_clock": "*60",
}


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(
        tenant_code="t1",
        extensions=[
            ExtensionSnapshot(id="e1", number="201", name="Aziz", ring_seconds=15,
                              target_id="ext-201", no_answer_target_id="vm-201"),
            ExtensionSnapshot(id="e2", number="202", name="Vali", ring_seconds=30,
                              target_id="ext-202", no_answer_target_id="hang"),
            ExtensionSnapshot(id="e3", number="203", name="Soli", ring_seconds=25, target_id="ext-203"),
        ],
        targets={
            "ext-201": TargetSnapshot(id="ext-201", kind="extension", label="201"),
            "ext-202": TargetSnapshot(id="ext-202", kind="extension", label="202"),
            "ext-203": TargetSnapshot(id="ext-203", kind="extension", label="203"),
            "vm-201": TargetSnapshot(id="vm-201", kind="voicemail", label="VM 201"),
            "hang": TargetSnapshot(id="hang", kind="hangup", label="Uzish"),
        },
        inbound_routes=[InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="",
                                             target_id="ext-203")],
        voicemail_boxes=[VoicemailBoxSnapshot(target_id="vm-201", mailbox="201")],
        feature_codes=dict(_DEFAULT_CODES),
        internal_api_base_url="http://api:8000",
        internal_api_token="tok",
    )
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def _context(text: str, name: str) -> str:
    start = text.index(f"[{name}]\n")
    end = text.find("\n[", start + 1)
    return text[start:] if end == -1 else text[start:end]


# ------------------------------------------------------------ kirish nuqtasi
def test_from_internal_routes_every_number_through_ext_context():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert " same => n,Goto(t1-ext,${EXTEN},1)" in fi
    assert "Dial(PJSIP/t1-${EXTEN}" not in fi
    # Har yangi qo'ng'iroqda yo'naltirish holati tozalanadi (IVR to'g'ridan-to'g'ri terish ham).
    assert " same => n,Set(INNOVA_FWD_SEEN=)" in fi
    assert " same => n,Set(INNOVA_FWD_FROM=)" in fi


def test_ext_context_has_explicit_entry_with_ring_and_no_answer_dest():
    ext = _context(compile_dialplan(_snapshot()), "t1-ext")
    entry = ext[ext.index("exten => 201,1"):ext.index("exten => 202,1")]
    assert " same => n,Set(INNOVA_RING=15)" in entry
    assert " same => n,Set(INNOVA_NOANS=t1-dest-vm-201)" in entry
    assert " same => n,Goto(t1-ext-call,${EXTEN},1)" in entry


def test_dnd_goes_to_voicemail_only_when_no_answer_is_voicemail():
    ext = _context(compile_dialplan(_snapshot()), "t1-ext")
    e201 = ext[ext.index("exten => 201,1"):ext.index("exten => 202,1")]
    e202 = ext[ext.index("exten => 202,1"):ext.index("exten => 203,1")]
    assert " same => n,Set(INNOVA_DNDDEST=t1-dest-vm-201)" in e201
    assert " same => n,Set(INNOVA_NOANS=t1-dest-hang)" in e202
    assert " same => n,Set(INNOVA_DNDDEST=)" in e202


def test_unknown_number_falls_through_to_outbound_via_realtime_existence_check():
    ext = _context(compile_dialplan(_snapshot()), "t1-ext")
    assert ('exten => _X.,1,GotoIf($["${REALTIME_FIELD(ext_state,endpoint,t1-${EXTEN},endpoint)}"=""]'
            '?t1-outbound,${EXTEN},1)') in ext


def test_ext_call_reads_dnd_and_forward_from_realtime():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    assert ' same => n,GotoIf($["${REALTIME_FIELD(ext_state,endpoint,t1-${EXTEN},dnd)}"="t"]?dnd)' in call
    assert " same => n,Set(INNOVA_FWD=${REALTIME_FIELD(ext_state,endpoint,t1-${EXTEN},forward_always)})" in call
    assert " same => n,Set(INNOVA_FWD=${REALTIME_FIELD(ext_state,endpoint,t1-${EXTEN},forward_busy)})" in call


def test_ext_call_dials_with_transfer_options_pickup_mark_and_transfer_context():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    assert (' same => n,Dial(PJSIP/t1-${EXTEN},${INNOVA_RING},'
            't${IF($["${INNOVA_FROM_TRUNK}"="1"]?:T)}U(innova-rec))') in call
    assert " same => n(dial),Set(__PICKUPMARK=t1-${EXTEN})" in call
    assert " same => n,Set(__TRANSFER_CONTEXT=t1-from-internal)" in call


def test_forward_busy_only_after_busy_dialstatus():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    busy_check = call.index('GotoIf($["${DIALSTATUS}"!="BUSY"]?noans)')
    assert call.index("Dial(PJSIP/") < busy_check < call.index("forward_busy")


def test_forward_loop_and_hop_limit_guard():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    assert " same => n(fwd),GotoIf($[${FIELDNUM(INNOVA_FWD_SEEN,-,${INNOVA_FWD})} > 0]?fwdstop)" in call
    assert " same => n,GotoIf($[${FIELDQTY(INNOVA_FWD_SEEN,-)} > 4]?fwdstop)" in call
    assert " same => n,Set(INNOVA_FWD_FROM=${EXTEN})" in call
    assert " same => n,Goto(t1-ext,${INNOVA_FWD},1)" in call
    assert " same => n,Goto(${INNOVA_FWD_STOP})" in call


def test_dnd_without_voicemail_is_busy_486():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    dnd = call[call.index("n(dnd)"):call.index("n(fwd)")]
    assert "Set(DIALSTATUS=BUSY)" in dnd
    assert " same => n(busy),Busy(5)" in dnd
    assert " same => n,Hangup(17)" in dnd


def test_extension_dest_jumps_into_ext_context():
    dest = _context(compile_dialplan(_snapshot()), "t1-dest-ext-203")
    assert " same => n,Goto(t1-ext,203,1)" in dest
    assert "Dial(" not in dest


# ------------------------------------------------------------ toll fraud
def test_outbound_uses_forwarder_permissions_and_blocks_trunk_origin():
    route = OutboundRouteSnapshot(
        id="o1", name="UZ", priority=1, enabled=True, international=False,
        patterns=(OutboundPatternSnapshot(strip_prefix="", pattern="9XXXXXXXX", add_prefix=""),),
        trunks=(OutboundTrunkSnapshot(position=1, id="tr1", name="T"),),
    )
    text = compile_dialplan(_snapshot(outbound_routes=[route], outbound_blocked_extension_numbers=("202",)))
    out = _context(text, "t1-outbound")
    assert ' same => n,ExecIf($["${INNOVA_FWD_FROM}"!=""]?Set(INNOVA_SRC_EXT=${INNOVA_FWD_FROM}))' in out
    assert ' same => n,GotoIf($["${INNOVA_FROM_TRUNK}${INNOVA_FWD_FROM}${BLINDTRANSFER}"="1"]?outbound_blocked)' in out
    assert ' same => n,GotoIf($["${INNOVA_SRC_EXT}"="202"]?outbound_blocked)' in out
    assert ' same => n,GotoIf($["${INNOVA_SRC_EXT}"="trunk"]?outbound_blocked)' in out
    assert ' same => n,ExecIf($["${BLINDTRANSFER}"!=""]?Set(INNOVA_SRC_EXT=${CUT(BLINDTRANSFER,-,2)}))' in out
    assert " same => n(outbound_blocked),NoOp(" in out
    # Ruxsat tekshiruvi marshrutdan OLDIN.
    assert out.index("outbound_blocked)") < out.index("r1_start")
    rg = _context(text, "t1-outbound-rg")
    assert "INNOVA_FROM_TRUNK" not in rg and "outbound_blocked" not in rg
    assert "outbound_blocked" not in _context(text, "t1-from-internal")


def test_trunk_inbound_marks_channel_origin():
    trunk = _context(compile_dialplan(_snapshot()), "t1-from-trunk")
    assert " same => n,Set(INNOVA_FROM_TRUNK=1)" in trunk


# ------------------------------------------------------------ qora ro'yxat (§5)
def test_inbound_route_gosubs_blacklist_check_right_after_from_trunk_marker():
    trunk = _context(compile_dialplan(_snapshot()), "t1-from-trunk")
    marker = trunk.index(" same => n,Set(INNOVA_FROM_TRUNK=1)")
    gosub = trunk.index(" same => n,Gosub(t1-blacklist-check,s,1)")
    assert gosub == marker + len(" same => n,Set(INNOVA_FROM_TRUNK=1)") + 1


def test_blacklist_check_context_hangs_up_when_matched_and_returns_otherwise():
    bl = _context(compile_dialplan(_snapshot()), "t1-blacklist-check")
    assert "REALTIME_FIELD(blacklist,endpoint,t1-${INNOVA_BL_NUM},reason)" in bl
    assert " same => n,Set(CDR(userfield)=blacklisted)" in bl
    assert " same => n,Hangup(21)" in bl
    assert " same => n(s-return),Return()" in bl
    assert bl.index("Hangup(21)") < bl.index("(s-return),Return()")


def test_blacklist_check_treats_empty_callerid_as_anonymous():
    bl = _context(compile_dialplan(_snapshot()), "t1-blacklist-check")
    assert '?anonymous:${INNOVA_BL_NUM})' in bl


# ------------------------------------------------------------ qo'ng'iroq guruhi
def test_ring_group_skips_dnd_members_at_runtime_and_keeps_external():
    rg = RingGroupSnapshot(
        id="g1", target_id="rg-1", name="Sotuv", strategy="ringall", ring_seconds=20,
        no_answer_target_id="hang",
        members=(RingGroupMemberSnapshot(position=1, extension_number="201"),
                 RingGroupMemberSnapshot(position=2, extension_number="998901234567", is_external=True)),
    )
    snap = _snapshot(ring_groups=[rg], targets={**_snapshot().targets,
                                                "rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="RG")},
                     dial_numbers=[DialNumberSnapshot(number="600", target_id="rg-1")])
    dest = _context(compile_dialplan(snap), "t1-dest-rg-1")
    assert (' same => n,ExecIf($["${REALTIME_FIELD(ext_state,endpoint,t1-201,dnd)}"!="t"]'
            '?Set(INNOVA_RG=${INNOVA_RG}&PJSIP/t1-201))') in dest
    assert " same => n,Set(INNOVA_RG=${INNOVA_RG}&Local/998901234567@t1-outbound-rg)" in dest
    assert ' same => n,GotoIf($["${INNOVA_RG}"=""]?rg1_skip)' in dest
    assert " same => n,Dial(${INNOVA_RG:1},20,t${IF($[\"${INNOVA_FROM_TRUNK}\"=\"1\"]?:T)}U(innova-rec))" in dest


# ------------------------------------------------------------ funksiya kodlari
def test_feature_codes_follow_the_table_and_disabled_are_absent():
    codes = dict(_DEFAULT_CODES, dnd_toggle="*77")
    del codes["echo_test"]
    fi = _context(compile_dialplan(_snapshot(feature_codes=codes)), "t1-from-internal")
    assert "exten => *77,1,NoOp(Innova: DND almashtirish)" in fi
    assert "exten => *76," not in fi
    assert "exten => *43," not in fi
    assert "exten => *97,1,NoOp(Innova: o'z ovozli pochtasi)" in fi


def test_dnd_toggle_writes_realtime_and_verifies_by_read_back():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    toggle = fi[fi.index("exten => *76,1"):]
    # CALLERID emas: trunk CLI soxtalashtirilsa ham boshqa ext holatini yoza olmaydi.
    assert " same => n,Set(INNOVA_EP=${CHANNEL(endpoint)})" in toggle
    assert " same => n,Set(REALTIME(ext_state,endpoint,${INNOVA_EP},dnd)=${INNOVA_NEW})" in toggle
    assert ' same => n,GotoIf($["${REALTIME_FIELD(ext_state,endpoint,${INNOVA_EP},dnd)}"!="${INNOVA_NEW}"]?err)' in toggle


def test_queue_login_toggles_agent_state_and_verifies_by_read_back():
    codes = dict(_DEFAULT_CODES, queue_login="*45")
    fi = _context(compile_dialplan(_snapshot(feature_codes=codes)), "t1-from-internal")
    login = fi[fi.index("exten => *45,1"):]
    assert " same => n,Set(INNOVA_EP=${CHANNEL(endpoint)})" in login
    assert ' same => n,Set(INNOVA_NEW=${IF($["${REALTIME_FIELD(agent_state,endpoint,${INNOVA_EP},logged_in)}"="t"]?f:t)})' in login
    assert " same => n,Set(REALTIME(agent_state,endpoint,${INNOVA_EP},logged_in)=${INNOVA_NEW})" in login
    assert (' same => n,GotoIf($["${REALTIME_FIELD(agent_state,endpoint,${INNOVA_EP},logged_in)}"'
            '!="${INNOVA_NEW}"]?err)') in login
    assert " same => n(err),Playback(invalid)" in login


def test_queue_pause_toggles_and_nudges_live_asterisk_state():
    codes = dict(_DEFAULT_CODES, queue_pause="*46")
    fi = _context(compile_dialplan(_snapshot(feature_codes=codes)), "t1-from-internal")
    pause = fi[fi.index("exten => *46,1"):]
    assert " same => n,Set(REALTIME(agent_state,endpoint,${INNOVA_EP},paused)=${INNOVA_NEW})" in pause
    # Barcha navbatlarga (bo'sh navbat nomi) — *46 BUTUN a'zoliklarga ta'sir qiladi.
    assert ' same => n,ExecIf($["${INNOVA_NEW}"="t"]?PauseQueueMember(,PJSIP/${INNOVA_EP}))' in pause
    assert ' same => n,ExecIf($["${INNOVA_NEW}"="f"]?UnpauseQueueMember(,PJSIP/${INNOVA_EP}))' in pause
    assert pause.index("REALTIME(agent_state") < pause.index("PauseQueueMember")


def test_call_forward_codes_with_number_and_with_prompt():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => _*72X.,1,NoOp(" in fi
    assert " same => n,Set(INNOVA_NUM=${EXTEN:3})" in fi
    assert " same => n,Read(INNOVA_NUM,call-fwd-unconditional,15,,1,10)" in fi
    assert " same => n,Goto(t1-cf,forward_always,1)" in fi
    assert "exten => _*90X.,1,NoOp(" in fi
    assert " same => n,Goto(t1-cf,forward_busy,1)" in fi
    off = fi[fi.index("exten => *73,1"):]
    assert " same => n,Set(INNOVA_NUM=)" in off


def test_cf_context_writes_and_reads_back_each_column():
    cf = _context(compile_dialplan(_snapshot()), "t1-cf")
    for column in ("forward_always", "forward_busy"):
        assert f" same => n,Set(REALTIME(ext_state,endpoint,${{INNOVA_EP}},{column})=${{INNOVA_NUM}})" in cf
        assert (f' same => n,GotoIf($["${{REALTIME_FIELD(ext_state,endpoint,${{INNOVA_EP}},{column})}}"'
                f'!="${{INNOVA_NUM}}"]?err)') in cf
    # Yoqishda bo'sh raqam va o'ziga yo'naltirish — xato.
    assert " same => n,Set(INNOVA_EP=${CHANNEL(endpoint)})" in cf
    assert ' same => n,GotoIf($["${INNOVA_CF_ON}${INNOVA_NUM}"="1"]?err)' in cf
    assert ' same => n,GotoIf($["${INNOVA_NUM}"="${CALLERID(num)}"]?err)' in cf


def test_pickup_codes():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => *8,1,Pickup()" in fi
    assert "exten => _**X.,1,Pickup(t1-${EXTEN:2}@PICKUPMARK)" in fi


def test_park_lot_and_slots_are_explicit_in_from_internal():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => 700,1,Park(t1-park)" in fi
    assert "exten => *70,1,Park(t1-park)" in fi
    assert "exten => 701,1,ParkedCall(t1-park,701)" in fi
    assert "exten => 720,1,ParkedCall(t1-park,720)" in fi
    assert "exten => 721," not in fi


def test_echo_and_clock():
    fi = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => *43,1,Answer()" in fi and " same => n,Echo()" in fi
    assert "exten => *60,1,Answer()" in fi and " same => n,SayUnixTime()" in fi


def test_feature_order_matches_contract():
    assert FEATURE_ORDER == ("voicemail", "voicemail_other", "dnd_toggle", "cf_always_on", "cf_always_off",
                             "cf_busy_on", "cf_busy_off", "pickup_group", "pickup_direct", "park",
                             "echo_test", "speaking_clock", "queue_login", "queue_pause", "followme_toggle")


# ------------------------------------------------------------ yaxlitlik
_CTX_REF = re.compile(r"(?:Goto\(|\?)([a-z][a-z0-9-]*),[^,()]+,(?:1|s)\b")


def test_every_referenced_context_exists():
    rg = RingGroupSnapshot(
        id="g1", target_id="rg-1", name="Sotuv", strategy="hunt", ring_seconds=20, no_answer_target_id="hang",
        members=(RingGroupMemberSnapshot(position=1, extension_number="201"),
                 RingGroupMemberSnapshot(position=2, extension_number="0901", is_external=True)),
    )
    snap = _snapshot(ring_groups=[rg], targets={**_snapshot().targets,
                                                "rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="RG")},
                     dial_numbers=[DialNumberSnapshot(number="600", target_id="rg-1")])
    text = compile_dialplan(snap)
    defined = set(re.findall(r"^\[([^\]]+)\]$", text, flags=re.M))
    referenced = set(_CTX_REF.findall(text)) | set(re.findall(r"Local/[^@]+@([a-z][a-z0-9-]*)", text))
    referenced -= {"PICKUPMARK"}
    assert {"t1-ext", "t1-ext-call", "t1-cf", "t1-outbound", "t1-outbound-rg", "t1-vm-main", "t1-dest-hang"} <= referenced
    assert referenced <= defined, referenced - defined


def test_dynamic_dest_variables_only_point_to_defined_dest_contexts():
    text = compile_dialplan(_snapshot())
    defined = set(re.findall(r"^\[([^\]]+)\]$", text, flags=re.M))
    dynamic = set(re.findall(r"Set\(INNOVA_(?:NOANS|DNDDEST)=([^)]+)\)", text))
    assert dynamic == {"t1-dest-vm-201", "t1-dest-hang"}
    assert dynamic <= defined


# ------------------------------------------------------------ park sozlamasi
def test_parking_conf_lot():
    conf = parking_conf_text("t1")
    assert "[t1-park]\n" in conf
    assert "parkpos => 701-720\n" in conf
    assert "parkingtime => 60\n" in conf
    assert "comebacktoorigin => yes\n" in conf
    assert "context => t1-parkedcalls\n" in conf


def test_park_numbers_are_reserved():
    assert is_park_number("700") and is_park_number("701") and is_park_number("720")
    assert not is_park_number("699") and not is_park_number("721") and not is_park_number("0701")


# ------------------------------------------------------------ konferensiya (§4)
def _conf_snapshot(conf: ConferenceSnapshot) -> DialplanSnapshot:
    return _snapshot(
        conferences=[conf],
        targets={**_snapshot().targets, "conf-1": TargetSnapshot(id="conf-1", kind="conference", label="Yig'ilish")},
        dial_numbers=[DialNumberSnapshot(number="600", target_id="conf-1")],
    )


def test_conference_without_pin_joins_directly_no_curl():
    conf = ConferenceSnapshot(id="c1", target_id="conf-1", name="Yig'ilish", has_pin=False, has_admin_pin=False)
    dest = _context(compile_dialplan(_conf_snapshot(conf)), "t1-dest-conf-1")
    assert " same => n,ConfBridge(t1-conf-c1,t1-conf-c1-bridge,t1-conf-c1-user,innova-conf-menu)" in dest
    assert "CURL(" not in dest
    assert " same => n,Hangup()" in dest


def test_conference_with_pin_asks_and_joins_user_profile_via_curl():
    conf = ConferenceSnapshot(id="c1", target_id="conf-1", name="Yig'ilish", has_pin=True, has_admin_pin=False)
    dest = _context(compile_dialplan(_conf_snapshot(conf)), "t1-dest-conf-1")
    assert " same => n,Set(INNOVA_CONF_TRY=0)" in dest
    assert " same => n(pin),Set(INNOVA_CONF_TRY=$[${INNOVA_CONF_TRY} + 1])" in dest
    assert " same => n,Read(INNOVA_PIN,,8)" in dest
    assert "/internal/conferences/c1/pin-check?token=tok&pin=${INNOVA_PIN}" in dest
    assert ' same => n,GotoIf($["${INNOVA_CONF_ROLE}"="user"]?join_user)' in dest
    assert " same => n(join_user),ConfBridge(t1-conf-c1,t1-conf-c1-bridge,t1-conf-c1-user,innova-conf-menu)" in dest
    assert ' same => n,GotoIf($[${INNOVA_CONF_TRY} < 3]?pin)' in dest


def test_conference_with_admin_pin_joins_admin_profile():
    conf = ConferenceSnapshot(id="c1", target_id="conf-1", name="Yig'ilish", has_pin=True, has_admin_pin=True)
    dest = _context(compile_dialplan(_conf_snapshot(conf)), "t1-dest-conf-1")
    assert " same => n(join_admin),ConfBridge(t1-conf-c1,t1-conf-c1-bridge,t1-conf-c1-admin,innova-conf-menu)" in dest
