"""M3b §1 — yozuv dialplan'i: bitta yordamchi barcha dial nuqtalarida, bitta subroutine."""
from __future__ import annotations

import re

from app.services import dialplan_recording as rec


def test_recorded_dial_lines_prep_then_dial_with_u():
    lines = rec.recorded_dial_lines("PJSIP/t1-${EXTEN}", "${INNOVA_RING}", "tT")
    assert lines == [
        " same => n,Gosub(innova-rec-prep,s,1)",
        " same => n,Dial(PJSIP/t1-${EXTEN},${INNOVA_RING},tTU(innova-rec))",
    ]


def test_recorded_dial_lines_without_options():
    assert rec.recorded_dial_lines("PJSIP/x@t", "30")[-1] == " same => n,Dial(PJSIP/x@t,30,U(innova-rec))"


def test_recorded_queue_lines_gosub_is_seventh_arg():
    lines = rec.recorded_queue_lines("t1-q-abc", 60, queue_id="abc")
    assert lines == [
        " same => n,Set(__INNOVA_QUEUE=abc)",
        " same => n,Gosub(innova-rec-prep,s,1)",
        " same => n,Queue(t1-q-abc,,,,60,,innova-rec)",
    ]
    args = lines[-1].split("Queue(")[1].rstrip(")").split(",")
    assert args[6] == "innova-rec"


def _context(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"[{name}]")
    out = []
    for line in lines[start + 1:]:
        if line.startswith("["):
            break
        out.append(line)
    return out


def test_shared_contexts_present_and_return():
    text = "\n".join(rec.recording_context_lines())
    for name in ("innova-rec-prep", "innova-rec", "innova-rec-start", "innova-rec-toggle"):
        body = _context(text, name)
        assert body and body[0].startswith("exten => s,1,")
        assert any("Return()" in line for line in body), name


def test_prep_sets_inherited_a_and_on_demand_feature():
    body = "\n".join(_context("\n".join(rec.recording_context_lines()), "innova-rec-prep"))
    assert "Set(__INNOVA_REC_A=${CHANNEL(endpoint)})" in body
    assert "Set(DYNAMIC_FEATURES=innova-rec)" in body
    assert '"${CHANNEL(channeltype)}"!="PJSIP"' in body
    # M3c §1: A o'z chiquvchi qo'ng'irog'ini boshlayapti — `recording_out` (emas `recording`).
    assert "REALTIME_FIELD(ext_state,endpoint,${INNOVA_REC_A},recording_out)" in body


def test_rec_policy_uses_recording_out_for_a_and_recording_for_b():
    body = "\n".join(_context("\n".join(rec.recording_context_lines()), "innova-rec"))
    # B (javob bergan, CHANNEL(endpoint)) — KIRUVCHI (`recording`, nomi o'zgarmaydi).
    assert "REALTIME_FIELD(ext_state,endpoint,${CHANNEL(endpoint)},recording)" in body
    assert "REALTIME_FIELD(ext_state,endpoint,${CHANNEL(endpoint)},recording_out)" not in body
    # A / manba (SRC yoki A) — CHIQUVCHI (`recording_out`).
    assert "REALTIME_FIELD(ext_state,endpoint,${INNOVA_REC_A},recording_out)" in body
    assert "REALTIME_FIELD(ext_state,endpoint,${INNOVA_REC_P},recording_out)" in body


def test_rec_start_file_path_and_cdr():
    body = "\n".join(_context("\n".join(rec.recording_context_lines()), "innova-rec-start"))
    assert "innova/${STRFTIME(${EPOCH},UTC,%Y/%m/%d)}/${CHANNEL(linkedid)}-${UNIQUEID}.wav" in body
    assert "MixMonitor(${INNOVA_REC_FILE},ai(INNOVA_REC_ID))" in body
    assert "Set(CDR(recordingfile)=${INNOVA_REC_FILE})" in body


def test_rec_policy_branches():
    body = "\n".join(_context("\n".join(rec.recording_context_lines()), "innova-rec"))
    # trunk B → manba ichki raqam siyosati; ichki → external_only; never ustun
    assert "INNOVA_REC_SRC" in body and "rec_external_only" in body
    assert '"${INNOVA_REC_RA}"="never"|"${INNOVA_REC_RB}"="never"' in body
    labels = set(re.findall(r"n\((\w+)\)", body))
    targets = set(re.findall(r"\?(\w+)(?::(\w+))?\)", body))
    for a, b in targets:
        assert a in labels and (not b or b in labels)


def test_toggle_stops_or_starts():
    body = "\n".join(_context("\n".join(rec.recording_context_lines()), "innova-rec-toggle"))
    assert "StopMixMonitor(${INNOVA_REC_ID})" in body
    assert "Gosub(innova-rec-start,s,1)" in body


def test_originate_context_blocks_feature_codes():
    lines = rec.originate_context_lines("t1")
    text = "\n".join(lines)
    assert lines[0] == "[t1-originate]"
    assert "exten => _X!,1," in text
    assert "Set(CALLERID(num)=${INNOVA_ORIG_EXT})" in text
    assert "Goto(t1-from-internal,${EXTEN},1)" in text
    assert "exten => _[*#]!,1," in text


def test_recording_ids_constant_matches_feature():
    assert rec.FEATURE_NAME == "innova-rec" and rec.SUBROUTINE == "innova-rec"


def test_family_matches_features():
    from app.services.dialplan_features import EXT_STATE_FAMILY
    assert rec.EXT_STATE_FAMILY == EXT_STATE_FAMILY
