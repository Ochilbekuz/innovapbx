"""M12 Bo'lak A (asterisk-engineer): Kun/Tun rejimi (*28N, BLF) + DISA
(PIN 3 urinish, outbound-rg'ga Goto) — sof kompilyator funksiyalari, va
L3 audit tuzatishi (`feature_code_lines` render vaqtida `CODE_RE` qayta
tekshiradi). DB/AMI'siz — faqat matn chiqishini tekshiradi."""
from __future__ import annotations

import logging

from app.services import compiler as cmp
from app.services.dialplan_features import feature_code_lines


def _snap(**kwargs) -> cmp.DialplanSnapshot:
    base = dict(tenant_code="t1", internal_api_base_url="http://api:8000", internal_api_token="tok")
    base.update(kwargs)
    return cmp.DialplanSnapshot(**base)


# ------------------------------------------------------------ A1: kun/tun dest
def test_day_night_dest_lines_reads_live_state_and_routes_day_or_night():
    dn = cmp.DayNightSnapshot(
        id="dn1", target_id="tgt-dn1", name="Asosiy", code="0",
        day_target_id="tgt-day", night_target_id="tgt-night", has_pin=False,
    )
    snap = _snap(day_night=[dn])
    lines = cmp._day_night_dest_lines("t1", dn, snap)
    text = "\n".join(lines)
    assert "/internal/day-night/dn1/state?token=tok" in text
    assert "Goto(t1-dest-tgt-day,s,1)" in text
    assert "Goto(t1-dest-tgt-night,s,1)" in text
    assert 'GotoIf($["${INNOVA_DN_MODE}"="night"]?night)' in text


def test_day_night_toggle_lines_bare_digit_exten_and_blf_hint():
    dn = cmp.DayNightSnapshot(
        id="dn1", target_id="tgt-dn1", name="Asosiy", code="5",
        day_target_id="tgt-day", night_target_id="tgt-night", has_pin=True,
    )
    lines = cmp._day_night_toggle_lines("t1", dn, "http://api:8000", "tok")
    text = "\n".join(lines)
    assert "exten => *285,hint,Custom:DAYNIGHT5" in text
    assert "exten => *285,1,NoOp" in text
    assert " same => n,Read(INNOVA_PIN,,8)" in text
    assert "/internal/day-night/dn1/toggle?token=tok&pin=${INNOVA_PIN}" in text
    assert "Set(DEVICE_STATE(Custom:DAYNIGHT5)=" in text


def test_day_night_toggle_lines_no_pin_skips_read():
    dn = cmp.DayNightSnapshot(
        id="dn2", target_id="tgt-dn2", name="PIN'siz", code="1",
        day_target_id="tgt-day", night_target_id="tgt-night", has_pin=False,
    )
    lines = cmp._day_night_toggle_lines("t1", dn, "http://api:8000", "tok")
    text = "\n".join(lines)
    assert " same => n,Read(INNOVA_PIN,,8)" not in text
    assert "exten => *281," in text


def test_build_edges_includes_day_night_day_and_night_targets():
    dn = cmp.DayNightSnapshot(
        id="dn1", target_id="tgt-dn1", name="Asosiy", code="0",
        day_target_id="tgt-day", night_target_id="tgt-night", has_pin=False,
    )
    snap = _snap(day_night=[dn])
    edges = cmp._build_edges(snap)
    assert set(edges["tgt-dn1"]) == {"tgt-day", "tgt-night"}


def test_all_dest_ids_includes_day_night_targets():
    dn = cmp.DayNightSnapshot(
        id="dn1", target_id="tgt-dn1", name="Asosiy", code="0",
        day_target_id="tgt-day", night_target_id="tgt-night", has_pin=False,
    )
    snap = _snap(day_night=[dn])
    ids = cmp._all_dest_ids(snap)
    assert "tgt-day" in ids
    assert "tgt-night" in ids


def test_satellite_builders_registered_for_day_night_and_disa():
    assert "day_night" in cmp._SATELLITE_BUILDERS
    assert "disa" in cmp._SATELLITE_BUILDERS


# ------------------------------------------------------------ A2: DISA dest
def test_disa_dest_lines_no_pin_goes_straight_to_outbound_rg():
    disa = cmp.DisaSnapshot(id="d1", target_id="tgt-d1", name="Tashqi", has_pin=False)
    snap = _snap(disa=[disa])
    lines = cmp._disa_dest_lines("t1", disa, snap)
    text = "\n".join(lines)
    assert "Set(TIMEOUT(digit)=5)" in text
    assert "Set(TIMEOUT(response)=10)" in text
    assert "Read(INNOVA_DISA_NUM,,20)" in text
    assert "Goto(t1-outbound-rg,${INNOVA_DISA_NUM},1)" in text
    # PIN yo'q -- CURL pin-check qatori umuman bo'lmasligi kerak.
    assert "pin-check" not in text


def test_disa_dest_lines_with_pin_retries_up_to_max_attempts_then_hangup():
    disa = cmp.DisaSnapshot(id="d1", target_id="tgt-d1", name="Tashqi", has_pin=True, max_attempts=3)
    snap = _snap(disa=[disa])
    lines = cmp._disa_dest_lines("t1", disa, snap)
    text = "\n".join(lines)
    assert "/internal/disa/d1/pin-check?token=tok&pin=${INNOVA_PIN}" in text
    assert "GotoIf($[${INNOVA_DISA_TRY} < 3]?pin)" in text
    assert " same => n,Hangup()" in text
    assert "Goto(t1-outbound-rg,${INNOVA_DISA_NUM},1)" in text
    # ichki xizmat kodlariga (-from-internal) hech qanday Goto bo'lmasligi SHART.
    assert "from-internal" not in text


def test_disa_dest_lines_cid_override_uses_dp_num():
    disa = cmp.DisaSnapshot(id="d1", target_id="tgt-d1", name="Tashqi", has_pin=False, cid_override="998901234567")
    snap = _snap(disa=[disa])
    lines = cmp._disa_dest_lines("t1", disa, snap)
    assert " same => n,Set(CALLERID(num)=998901234567)" in lines


def test_disa_dest_lines_rejects_unsafe_cid_override():
    disa = cmp.DisaSnapshot(id="d1", target_id="tgt-d1", name="Tashqi", has_pin=False, cid_override="x; rm -rf")
    snap = _snap(disa=[disa])
    try:
        cmp._disa_dest_lines("t1", disa, snap)
        raised = False
    except cmp.CompileError:
        raised = True
    assert raised


# ------------------------------------------------------------ L3: render-time CODE_RE re-check
def test_feature_code_lines_skips_invalid_code_and_logs(caplog):
    with caplog.at_level(logging.WARNING):
        lines = feature_code_lines("t1", {"dnd_toggle": "*DROP TABLE"})
    assert lines == []
    assert any("noto'g'ri kod o'tkazib yuborildi" in r.message for r in caplog.records)


def test_feature_code_lines_renders_valid_code_normally():
    lines = feature_code_lines("t1", {"dnd_toggle": "*78"})
    text = "\n".join(lines)
    assert "*78" in text
