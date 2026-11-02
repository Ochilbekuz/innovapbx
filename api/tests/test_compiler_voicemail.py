"""Kompilyator — ovozli pochta (m1c-contract.md §2): `dest-<vm>` konteksti,
`*97`/`*98` xususiyat kodlari, javobsiz ichki qo'ng'iroq -> ovozli pochta."""
from __future__ import annotations

from app.services.compiler import (
    DialplanSnapshot,
    ExtensionSnapshot,
    InboundRouteSnapshot,
    TargetSnapshot,
    VoicemailBoxSnapshot,
    compile_dialplan,
)

_VM = "vm-201"


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(
        tenant_code="t1",
        extensions=[ExtensionSnapshot(id="e1", number="201", name="Aziz", ring_seconds=15,
                                       target_id="ext-201", no_answer_target_id=_VM)],
        targets={
            "ext-201": TargetSnapshot(id="ext-201", kind="extension", label="201 · Aziz"),
            _VM: TargetSnapshot(id=_VM, kind="voicemail", label="Ovozli pochta · 201"),
        },
        voicemail_boxes=[VoicemailBoxSnapshot(target_id=_VM, mailbox="201")],
        internal_api_base_url="http://api:8000",
        internal_api_token="tok",
        feature_codes={"voicemail": "*97", "voicemail_other": "*98"},
    )
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def _context(text: str, name: str) -> str:
    start = text.index(f"[{name}]")
    end = text.find("\n[", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_voicemail_dest_uses_unavailable_greeting_and_busy_greeting_on_busy():
    dest = _context(compile_dialplan(_snapshot()), f"t1-dest-{_VM}")
    assert " same => n,VoiceMail(201@t1,u)" in dest
    assert ' same => n,GotoIf($["${DIALSTATUS}"="BUSY"]?busy)' in dest
    assert " same => n(busy),VoiceMail(201@t1,b)" in dest
    # BUSY tekshiruvi `u` dan OLDIN bo'lishi shart (aks holda doim `u`).
    assert dest.index("DIALSTATUS") < dest.index("VoiceMail(201@t1,u)")


def test_extension_no_answer_reaches_voicemail_dest():
    text = compile_dialplan(_snapshot())
    ext_dest = _context(text, "t1-dest-ext-201")
    assert " same => n,Goto(t1-ext,201,1)" in ext_dest
    entry = _context(text, "t1-ext").split("exten => _X.")[0]
    assert " same => n,Set(INNOVA_RING=15)" in entry
    assert f" same => n,Set(INNOVA_NOANS=t1-dest-{_VM})" in entry
    assert f"[t1-dest-{_VM}]" in text


def test_internal_call_to_extension_with_no_answer_target_goes_through_its_dest():
    """Ichki qo'ng'iroq ham (`_X.` umumiy Dial emas) javob bo'lmasa ovozli
    pochtaga tushishi kerak — aniq raqam `_X.` dan ustun."""
    text = compile_dialplan(_snapshot())
    assert " same => n,Goto(t1-ext,${EXTEN},1)" in _context(text, "t1-from-internal")
    ext = _context(text, "t1-ext")
    assert ext.index("exten => 201,1") < ext.index("exten => _X.,1")
    assert f" same => n,Set(INNOVA_NOANS=t1-dest-{_VM})" in ext


def test_extension_without_no_answer_target_keeps_generic_internal_dial_only():
    snap = _snapshot(extensions=[ExtensionSnapshot(id="e1", number="201", name="Aziz", ring_seconds=15,
                                                    target_id="ext-201")])
    text = compile_dialplan(snap)
    assert "exten => 201,1" not in _context(text, "t1-from-internal")
    assert "[t1-dest-ext-201]" not in text


def test_own_mailbox_feature_code_uses_caller_number():
    from_internal = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => *97,1,NoOp(Innova: o'z ovozli pochtasi)" in from_internal
    assert " same => n,Set(INNOVA_VM_BOX=${CALLERID(num)})" in from_internal
    assert " same => n,Goto(t1-vm-main,s,1)" in from_internal


def test_any_mailbox_feature_code_reads_box_number():
    from_internal = _context(compile_dialplan(_snapshot()), "t1-from-internal")
    assert "exten => *98,1,NoOp(Innova: istalgan ovozli pochta)" in from_internal
    assert " same => n,Read(INNOVA_VM_BOX,vm-login,10)" in from_internal


def test_vm_main_checks_pin_via_internal_curl_before_voicemailmain():
    main = _context(compile_dialplan(_snapshot()), "t1-vm-main")
    url = ("http://api:8000/internal/voicemail/pin-check?token=tok&context=t1"
           "&mailbox=${INNOVA_VM_BOX}&pin=${INNOVA_PIN}")
    assert " same => n,Answer()" in main
    assert " same => n,Read(INNOVA_PIN,vm-password,8)" in main
    assert f" same => n,Set(INNOVA_PIN_OK=${{CURL({url})}})" in main
    assert ' same => n,GotoIf($["${INNOVA_PIN_OK}"="1"]?ok)' in main
    assert " same => n(ok),VoiceMailMain(${INNOVA_VM_BOX}@t1,s)" in main
    # Rad yo'li VoiceMailMain'dan OLDIN uziladi.
    assert main.index("Hangup()") < main.index("VoiceMailMain")
    assert " same => n,Playback(vm-incorrect)" in main


def test_feature_codes_present_even_without_boxes():
    """Kodlar doim bor (quti yo'q bo'lsa PIN tekshiruvi baribir rad etadi) —
    quti qo'shish/o'chirish `from-internal` ni o'zgartirmasin."""
    snap = _snapshot(extensions=[], voicemail_boxes=[], targets={})
    text = compile_dialplan(snap)
    assert "exten => *97,1" in text
    assert "[t1-vm-main]" in text


def test_voicemail_target_without_box_is_safe_hangup():
    snap = _snapshot(voicemail_boxes=[])
    dest = _context(compile_dialplan(snap), f"t1-dest-{_VM}")
    assert "VoiceMail(" not in dest
    assert "Hangup(" in dest


def test_inbound_route_to_voicemail_target():
    snap = _snapshot(inbound_routes=[InboundRouteSnapshot(id="r1", did="712000201", callerid_pattern="",
                                                           target_id=_VM)])
    text = compile_dialplan(snap)
    assert f" same => n,Goto(t1-dest-{_VM},s,1)" in _context(text, "t1-from-trunk")
    assert f"[t1-dest-{_VM}]" in text
