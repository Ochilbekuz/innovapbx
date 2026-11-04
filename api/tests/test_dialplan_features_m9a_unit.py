"""M9 Bo'lak A — sof funksiyalar (`app/services/dialplan_features.py`):
e'lon/boshqa manzil Goto (compiler.py), park sozlamalari, paging/intercom,
qo'ng'iroq kutish. DB/AMI'siz — faqat matn chiqishini tekshiradi."""
from __future__ import annotations

from app.services import compiler as cmp
from app.services.dialplan_features import (
    PREDIAL_HDR_CONTEXT,
    ParkingSettingsData,
    _call_waiting_check_lines,
    _cw_set,
    _intercom,
    is_park_number,
    park_lines,
    park_numbers,
    parking_conf_text,
    page_group_lines,
    predial_hdr_context_lines,
)


# ------------------------------------------------------------ A4: predial-hdr
def test_predial_hdr_context_sets_alert_info_and_autoanswer_headers():
    lines = predial_hdr_context_lines()
    assert lines[0] == f"[{PREDIAL_HDR_CONTEXT}]"
    text = "\n".join(lines)
    assert "PJSIP_HEADER(add,Alert-Info)=${INNOVA_ALERT_INFO}" in text
    assert "PJSIP_HEADER(add,Call-Info)=<sip:innova-autoanswer>;answer-after=0" in text
    assert "PJSIP_HEADER(add,Alert-Info)=info=alert-autoanswer" in text
    assert lines[-1] == " same => n,Return()"


# ------------------------------------------------------------ A4: paging
def test_page_group_lines_default_options_i_and_d_s_q():
    lines = page_group_lines("601", ("201", "202"), duplex=True, skip_busy=True, beep=False)
    text = "\n".join(lines)
    assert "exten => 601,1,NoOp(Innova: paging 601)" in text
    assert " same => n,Set(__INNOVA_AUTOANSWER=1)" in text
    assert " same => n,Page(${INNOVA_DIAL:1},idsq)" in text
    assert " same => n,Hangup()" in text


def test_page_group_lines_minimal_options_no_duplex_no_skip_with_beep():
    lines = page_group_lines("602", ("201",), duplex=False, skip_busy=False, beep=True)
    assert " same => n,Page(${INNOVA_DIAL:1},i)" in lines


def test_intercom_sets_autoanswer_and_dials_rest_of_extension():
    lines = _intercom("t1", "*80")
    text = "\n".join(lines)
    assert "exten => _*80X.,1,NoOp(Innova: intercom ${EXTEN:3})" in text
    assert " same => n,Set(INNOVA_NUM=${EXTEN:3})" in text
    assert " same => n,Set(__INNOVA_AUTOANSWER=1)" in text
    assert " same => n,Set(__TRANSFER_CONTEXT=t1-from-internal)" in text
    assert "Dial(${INNOVA_DIAL:1},20," in text


# ------------------------------------------------------------ A5: call waiting
def test_call_waiting_check_jumps_to_busycheck_when_disabled_and_busy():
    lines = _call_waiting_check_lines("t1")
    text = "\n".join(lines)
    assert '?cwcheck:dial)' in text
    assert " same => n(cwcheck),GotoIf(" in text
    assert 'DEVICE_STATE(PJSIP/${EXTEN})}"="INUSE"]?busycheck)' in text
    assert 'DEVICE_STATE(PJSIP/${EXTEN})}"="BUSY"]?busycheck)' in text
    assert 'DEVICE_STATE(PJSIP/${EXTEN})}"="RINGINUSE"]?busycheck)' in text
    assert lines[-1] == " same => n,Goto(dial)"


def test_cw_on_writes_t_and_cw_off_writes_f_then_reads_back():
    on_lines = "\n".join(_cw_set("t")("t1", "*56"))
    off_lines = "\n".join(_cw_set("f")("t1", "*57"))
    assert "exten => *56,1,NoOp(Innova: kutish qo'ng'irog'i yoqish)" in on_lines
    assert "Set(REALTIME(ext_state,endpoint,${INNOVA_EP},call_waiting)=t)" in on_lines
    assert "Playback(activated)" in on_lines
    assert "exten => *57,1,NoOp(Innova: kutish qo'ng'irog'i o'chirish)" in off_lines
    assert "Set(REALTIME(ext_state,endpoint,${INNOVA_EP},call_waiting)=f)" in off_lines
    assert "Playback(de-activated)" in off_lines
    assert " same => n(err),Playback(invalid)" in off_lines


# ------------------------------------------------------------ A3: park sozlamalari
def test_parking_settings_data_defaults_match_old_hardcoded_constants():
    s = ParkingSettingsData()
    assert (s.lot_number, s.first_slot, s.slot_count, s.last_slot) == ("700", 701, 20, 720)
    assert s.timeout_s == 60 and s.on_timeout == "origin"


def test_park_numbers_and_is_park_number_use_custom_range():
    s = ParkingSettingsData(lot_number="800", first_slot=801, slot_count=5, timeout_s=90)
    nums = park_numbers(s)
    assert nums == frozenset({"800", "801", "802", "803", "804", "805"})
    assert is_park_number("803", s) is True
    assert is_park_number("701", s) is False  # eski sukut oraliqda, lekin bu lotda emas


def test_park_lines_use_lot_priority_1_and_slot_range():
    s = ParkingSettingsData(lot_number="800", first_slot=801, slot_count=2)
    lines = park_lines("t1", s)
    assert lines[0] == "exten => 800,1,Park(t1-park)"
    assert "exten => 801,1,ParkedCall(t1-park,801)" in lines
    assert "exten => 802,1,ParkedCall(t1-park,802)" in lines


def test_parking_conf_text_reflects_on_timeout_and_moh_class():
    origin = ParkingSettingsData(on_timeout="origin")
    assert "comebacktoorigin => yes" in parking_conf_text("t1", origin)
    target = ParkingSettingsData(on_timeout="target", moh_class_name="default")
    text = parking_conf_text("t1", target)
    assert "comebacktoorigin => no" in text and "parkedmusicclass => default" in text


def test_parkedcalls_context_falls_back_to_hangup_when_no_target():
    lines = cmp._parkedcalls_context_lines("t1", ParkingSettingsData(on_timeout="origin"))
    assert lines == ["[t1-parkedcalls]", "exten => _X.,1,Hangup()"]


def test_parkedcalls_context_goes_to_target_dest_when_configured():
    s = ParkingSettingsData(on_timeout="target", timeout_target_id="tgt-1")
    lines = cmp._parkedcalls_context_lines("t1", s)
    assert lines == [
        "[t1-parkedcalls]",
        "exten => s,1,Goto(t1-dest-tgt-1,s,1)",
        "exten => _X.,1,Goto(t1-dest-tgt-1,s,1)",
    ]
