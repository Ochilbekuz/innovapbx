"""Ko'p qurilmali ichki raqam (max_contacts>1): `Dial(PJSIP/<ep>)` faqat BIRINCHI
kontaktga INVITE yuboradi — har bir ichki raqam terish nuqtasi `innova-dial-contacts`
orqali BARCHA kontaktlarni (`PJSIP_DIAL_CONTACTS`) yig'ishi shart."""
from __future__ import annotations

import re

from app.services import dialplan_contacts as dc
from app.services import dialplan_features as feat
from app.services.compiler import (
    DialNumberSnapshot,
    PageGroupSnapshot,
    RingGroupMemberSnapshot,
    RingGroupSnapshot,
    TargetSnapshot,
    compile_dialplan,
)
from tests.test_compiler_call_features import _context, _snapshot


def test_subroutine_collects_all_contacts_with_unregistered_fallback():
    lines = dc.context_lines()
    assert lines == [
        "[innova-dial-contacts]",
        "exten => s,1,Set(LOCAL(C)=${PJSIP_DIAL_CONTACTS(${ARG1})})",
        # Hech kim ro'yxatda emas → `PJSIP/<ep>`: Dial CHANUNAVAIL, ovozli pochta oqimi o'zgarmaydi.
        " same => n,ExecIf($[${LEN(${C})}=0]?Set(C=PJSIP/${ARG1}))",
        " same => n,Set(INNOVA_DIAL=${INNOVA_DIAL}&${C})",
        " same => n,Return()",
    ]


def test_caller_lines_never_carry_contact_uri_into_if_or_execif():
    # URI ichida `:` bor — chaqiruvchi qatorda faqat endpoint id bo'ladi.
    assert dc.add_endpoint_line("201") == " same => n,Gosub(innova-dial-contacts,s,1(201))"
    assert (dc.add_endpoint_line("201", when='"x"!="t"')
            == ' same => n,GosubIf($["x"!="t"]?innova-dial-contacts,s,1(201))')
    assert dc.endpoint_targets_lines("${EXTEN}") == [
        " same => n,Set(INNOVA_DIAL=)",
        " same => n,Gosub(innova-dial-contacts,s,1(${EXTEN}))",
    ]
    assert dc.add_raw_line("Local/9@t1-outbound-rg") == " same => n,Set(INNOVA_DIAL=${INNOVA_DIAL}&Local/9@t1-outbound-rg)"


def _rich_snapshot():
    rg = RingGroupSnapshot(
        id="g1", target_id="rg-1", name="Sotuv", strategy="ringall", ring_seconds=20,
        no_answer_target_id="hang",
        members=(RingGroupMemberSnapshot(position=1, extension_number="201"),),
    )
    base = _snapshot()
    return _snapshot(
        ring_groups=[rg],
        targets={**base.targets, "rg-1": TargetSnapshot(id="rg-1", kind="ring_group", label="RG")},
        dial_numbers=[DialNumberSnapshot(number="600", target_id="rg-1")],
        page_groups=[PageGroupSnapshot(id="p1", name="Ofis", number="601", member_numbers=("201", "202"))],
    )


def test_compiled_dialplan_has_no_first_contact_only_endpoint_dial():
    text = compile_dialplan(_rich_snapshot())
    assert text.count("[innova-dial-contacts]") == 1
    # Trunk (`PJSIP/x@trunk`) bundan mustasno — u kontakt emas, `@` bilan. `Page()`
    # bu yerga kirmaydi: u `ast_device_state()` bilan oldindan tekshiradi va kompozit
    # `tech/ep/contact-uri`ni "Invalid" deb sanab UMUMAN chaqirmaydi — shu sabab
    # paging bare `PJSIP/<ep>` bilan qoladi (quyida alohida tasdiqlanadi).
    bare = re.findall(r"Dial\(PJSIP/[^,@)]*[,)]", text)
    assert bare == []
    assert "Page(PJSIP/201&PJSIP/202,is)" in text


def test_ext_call_dials_every_contact_of_the_extension():
    call = _context(compile_dialplan(_snapshot()), "t1-ext-call")
    collect = call.index(" same => n,Gosub(innova-dial-contacts,s,1(${EXTEN}))")
    assert call.index(" same => n,Set(INNOVA_DIAL=)") < collect < call.index("Dial(${INNOVA_DIAL:1},${INNOVA_RING},")


def test_follow_me_internal_leg_dials_every_contact():
    text = "\n".join(feat.fm_leg_lines("t1"))
    assert " same => n,Gosub(innova-dial-contacts,s,1(${EXTEN}))" in text
    assert "Dial(${INNOVA_DIAL:1},," in text


def test_intercom_reaches_every_contact():
    text = "\n".join(feat._intercom("t1", "*80"))
    assert " same => n,Gosub(innova-dial-contacts,s,1(${INNOVA_NUM}))" in text
    assert "Dial(${INNOVA_DIAL:1},20," in text


def test_paging_stays_bare_pjsip_because_page_app_checks_device_state():
    # `Page()` har manzilni `ast_device_state()` bilan tekshiradi; kompozit
    # `tech/ep/contact-uri` "Invalid" chiqadi va UMUMAN chaqirilmaydi (jonli
    # isbot, 2026-11-04). Shu sabab bu yerda `innova-dial-contacts` ISHLATILMAYDI —
    # a'zoning faqat birinchi kontakti jiringlaydi (Queue/Originate kabi cheklov).
    page = feat.page_group_lines("601", ("201", "202"), duplex=False, skip_busy=False, beep=True)
    assert "innova-dial-contacts" not in "\n".join(page)
    assert " same => n,Page(PJSIP/201&PJSIP/202,i)" in page
