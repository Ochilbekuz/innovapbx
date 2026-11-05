"""Kompilyator — M-CRM §3: `_crm_route_lines`/`_inbound_route_lines`ga ulanish
(Bitrix24 javobkor menejeriga yo'naltirish + chaqiruvchi ismi)."""
from __future__ import annotations

from app.services.compiler import (
    CrmRouteSnapshot,
    DialplanSnapshot,
    ExtensionSnapshot,
    InboundRouteSnapshot,
    TargetSnapshot,
    compile_dialplan,
)


def _snapshot(**kw) -> DialplanSnapshot:
    defaults = dict(
        tenant_code="t1",
        extensions=[ExtensionSnapshot(id="e1", number="101", name="Dilnoza",
                                       ring_seconds=25, target_id="ext-101")],
        targets={"ext-101": TargetSnapshot(id="ext-101", kind="extension", label="101 · Dilnoza")},
        inbound_routes=[InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="",
                                             target_id="ext-101")],
        internal_api_base_url="http://api:8000",
        internal_api_token="tok",
    )
    defaults.update(kw)
    return DialplanSnapshot(**defaults)


def _from_trunk(text: str) -> str:
    start = text.index("[t1-from-trunk]\n")
    end = text.find("\n[", start + 1)
    return text[start:end]


def test_no_crm_route_means_no_extra_lines():
    text = _from_trunk(compile_dialplan(_snapshot()))
    assert "INNOVA_CRMRT" not in text


def test_crm_route_disabled_still_sets_caller_name_by_default():
    cr = CrmRouteSnapshot(subscription_id="sub-1", ring_s=20, route=False, set_name=True)
    text = _from_trunk(compile_dialplan(_snapshot(crm_route=cr)))
    assert "http://api:8000/internal/crm-route/sub-1?token=tok" in text
    assert "num=${URIENCODE(${CALLERID(num)})}" in text
    assert "Set(INNOVA_CRMRT_NAME=${CUT(INNOVA_CRMRT,|,2)})" in text
    assert "Set(CALLERID(name)=${INNOVA_CRMRT_NAME})" in text
    # `route=False` -- javobkorga YO'NALTIRISH qatorlari chiqmaydi.
    assert "INNOVA_CRMRT_EXT" not in text


def test_crm_route_set_name_false_skips_caller_name_lines():
    cr = CrmRouteSnapshot(subscription_id="sub-1", set_name=False, route=False)
    text = _from_trunk(compile_dialplan(_snapshot(crm_route=cr)))
    assert "INNOVA_CRMRT_NAME" not in text
    assert "Set(INNOVA_CRMRT=${CURL(" in text


def test_crm_route_enabled_adds_dial_lines_with_ring_seconds():
    cr = CrmRouteSnapshot(subscription_id="sub-9", ring_s=35, route=True, set_name=True)
    text = _from_trunk(compile_dialplan(_snapshot(crm_route=cr)))
    assert "Set(INNOVA_CRMRT_EXT=${CUT(INNOVA_CRMRT,|,1)})" in text
    assert "Set(__TRANSFER_CONTEXT=t1-from-internal)" in text
    assert "Dial(${INNOVA_DIAL:1},35," in text
    assert "r1_crmrt_skip" in text


def test_crm_route_lines_come_after_cid_prefix_and_before_goto_dest():
    cr = CrmRouteSnapshot(subscription_id="sub-1", route=True)
    text = _from_trunk(compile_dialplan(_snapshot(
        crm_route=cr,
        inbound_routes=[InboundRouteSnapshot(id="r1", did="712000000", callerid_pattern="",
                                             target_id="ext-101", cid_name_prefix="[Tashqi] ")],
    )))
    prefix_pos = text.index("Set(CALLERID(name)=")
    crmrt_pos = text.index("INNOVA_CRMRT")
    goto_pos = text.index("Goto(t1-dest-ext-101,s,1)")
    assert prefix_pos < crmrt_pos < goto_pos


def test_compile_dialplan_is_deterministic_with_crm_route():
    cr = CrmRouteSnapshot(subscription_id="sub-1", ring_s=15, route=True, set_name=True)
    one = compile_dialplan(_snapshot(crm_route=cr))
    two = compile_dialplan(_snapshot(crm_route=cr))
    assert one == two
