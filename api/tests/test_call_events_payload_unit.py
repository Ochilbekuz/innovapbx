"""M3b §2 — AMI hodisalaridan va CDR qatorlaridan payload qurish (sof funksiyalar)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.integrations import events as ev

T0 = datetime(2026, 10, 29, 10, 0, 0, tzinfo=timezone.utc)
TRUNK = "PJSIP/t1-trunk-0b9c1d2e-1111-2222-3333-444455556666-0000000a"
QID = "5f0e7a7e-1d0b-4f1e-9a55-3a2b1c0d9e8f"


def cdr(seq, *, channel, dstchannel="", src="", dst="", disposition="ANSWERED", duration=10, billsec=0,
        at=T0, lastapp="Dial", lastdata="", userfield=""):
    return SimpleNamespace(sequence=seq, channel=channel, dstchannel=dstchannel, src=src, dst=dst,
                           disposition=disposition, duration=duration, billsec=billsec, calldate=at,
                           lastapp=lastapp, lastdata=lastdata, userfield=userfield)


# ------------------------------------------------------------ kanal nomlari
def test_channel_helpers():
    # Eski (tenant-prefiksli) kanal nomi — tarixiy hodisalarda hamon uchraydi.
    assert ev.channel_extension("PJSIP/t1-101-0000001f") == "101"
    assert ev.channel_extension(TRUNK) is None
    assert ev.channel_extension("Local/101@t1-ext-00000001;2") is None
    assert ev.channel_extension(None) is None
    assert ev.channel_code(TRUNK) == "t1"
    assert ev.channel_code("Local/1@x") is None
    assert ev.is_trunk(TRUNK) and not ev.is_trunk("PJSIP/t1-101-00000001") and not ev.is_trunk(None)
    assert ev.queue_id_of(f"t1-q-{QID},,,,60") == QID
    assert ev.queue_id_of("PJSIP/t1-101") is None


def test_channel_extension_new_format():
    # Yangi (prefiksiz, m-sip-login-plain-number) kanal nomi.
    assert ev.channel_extension("PJSIP/101-0000001f") == "101"
    assert ev.channel_code("PJSIP/101-0000001f") is None  # endi kod prefiksi yo'q


def test_var_update_tracks_only_innova_vars():
    evt = {"Event": "VarSet", "Linkedid": "1700.1", "Variable": "__INNOVA_DID", "Value": "712000000"}
    assert ev.var_update(evt) == ("1700.1", "INNOVA_DID", "712000000")
    assert ev.var_update({**evt, "Variable": "INNOVA_QUEUE", "Value": None}) == ("1700.1", "INNOVA_QUEUE", "")
    assert ev.var_update({**evt, "Variable": "INNOVA_BL_NUM"}) is None
    assert ev.var_update({**evt, "Event": "Newexten"}) is None
    assert ev.var_update({**evt, "Linkedid": ""}) is None


# ------------------------------------------------------------ AMI
def test_inbound_ringing_and_answered():
    base = {"Channel": TRUNK, "DestChannel": "PJSIP/t1-101-0000000b", "Linkedid": "1700.1",
            "CallerIDNum": "+998 90 123-45-67"}
    variables = {"INNOVA_DID": "712000000", "INNOVA_QUEUE": QID}
    ring = ev.live_event({"Event": "DialBegin", **base}, variables)
    assert (ring.type, ring.code, ring.linkedid, ring.dedupe_key) == ("call.ringing", "t1", "1700.1", "ringing:1700.1:101")
    assert (ring.direction, ring.from_, ring.to, ring.extension) == ("inbound", "998901234567", "101", "101")
    assert (ring.did, ring.queue_id, ring.internal) == ("712000000", QID, False)
    ans = ev.live_event({"Event": "DialEnd", "DialStatus": "ANSWER", **base})
    assert (ans.type, ans.dedupe_key, ans.did, ans.queue_id) == ("call.answered", "answered:1700.1", None, None)
    assert ev.live_event({"Event": "DialEnd", "DialStatus": "NOANSWER", **base}) is None


def test_internal_and_outbound_live_events():
    internal = ev.live_event({"Event": "DialBegin", "Channel": "PJSIP/t1-101-00000001",
                              "DestChannel": "PJSIP/t1-102-00000002", "Linkedid": "9.1"})
    assert (internal.direction, internal.from_, internal.to, internal.internal) == ("internal", "101", "102", True)
    assert internal.did is None
    out = ev.live_event({"Event": "DialBegin", "Channel": "PJSIP/t1-101-00000001", "DestChannel": TRUNK,
                         "DialString": "998901234567@t1-trunk-x", "Linkedid": "9.2"})
    assert (out.direction, out.from_, out.to, out.extension) == ("outbound", "101", "998901234567", "101")


def test_internal_live_event_new_format_needs_default_code():
    """Yangi (prefiksiz) ICHKI qo'ng'iroqda hech bir oyoqda tenant kodi yo'q —
    `default_code` berilmasa aniqlanmaydi, berilsa (yagona-tenant taxmin) ishlaydi."""
    evt = {"Event": "DialBegin", "Channel": "PJSIP/101-00000001", "DestChannel": "PJSIP/102-00000002",
           "Linkedid": "9.3"}
    assert ev.live_event(evt) is None
    internal = ev.live_event(evt, default_code="t1")
    assert (internal.code, internal.direction, internal.from_, internal.to) == ("t1", "internal", "101", "102")


def test_live_event_ignores_unrelated():
    assert ev.live_event({"Event": "Hangup"}) is None
    assert ev.live_event({"Event": "DialBegin", "Channel": "Local/1@x;2", "DestChannel": TRUNK, "Linkedid": "1"}) is None
    assert ev.live_event({"Event": "DialBegin", "DestChannel": "PJSIP/t1-101-00000001", "Linkedid": "1"}) is None
    assert ev.live_event({"Event": "DialBegin", "Channel": TRUNK, "DestChannel": "PJSIP/t1-101-00000001"}) is None
    assert ev.live_event({"Event": "DialBegin", "Channel": "Local/a", "DestChannel": "Local/b", "Linkedid": "1"}) is None


# ------------------------------------------------------------ CDR → call.ended
def test_inbound_queue_answered_by_member():
    rows = [
        cdr(1, channel=TRUNK, src="998901234567", dst="s", lastapp="Queue", lastdata=f"t1-q-{QID},,,,60",
            disposition="ANSWERED", duration=20, billsec=20, userfield="712000000"),
        cdr(2, channel=TRUNK, dstchannel="PJSIP/t1-101-00000002", disposition="NO ANSWER", duration=5,
            lastapp="Queue", lastdata=f"t1-q-{QID},,,,60"),
        cdr(3, channel=TRUNK, dstchannel="PJSIP/t1-103-00000003", disposition="ANSWERED", duration=18, billsec=12,
            at=T0 + timedelta(seconds=2), lastapp="Queue", lastdata=f"t1-q-{QID},,,,60"),
    ]
    f = ev.ended_facts(list(reversed(rows)))
    assert (f.direction, f.status, f.from_, f.to, f.extension, f.answered_by) == (
        "inbound", "answered", "998901234567", "103", "103", "103")
    assert (f.did, f.queue_id, f.billsec) == ("712000000", QID, 12)
    assert f.started_at == T0 and f.answered_at == T0 + timedelta(seconds=8)
    assert f.ended_at == T0 + timedelta(seconds=20) and f.duration_s == 20


def test_inbound_missed_and_busy_and_failed():
    missed = [cdr(1, channel=TRUNK, src="9989", dst="s", userfield="7120"),
              cdr(2, channel=TRUNK, dstchannel="PJSIP/t1-101-00000002", disposition="NO ANSWER")]
    f = ev.ended_facts(missed)
    assert (f.status, f.to, f.extension, f.answered_by, f.answered_at, f.billsec) == ("missed", "101", "101", None, None, 0)
    busy = [cdr(1, channel=TRUNK, dstchannel="PJSIP/t1-101-00000002", disposition="BUSY")]
    assert ev.ended_facts(busy).status == "busy"
    failed = [cdr(1, channel=TRUNK, src="1", userfield="7120", disposition="FAILED")]
    f = ev.ended_facts(failed)
    assert (f.status, f.to) == ("failed", "7120")


def test_outbound_call():
    rows = [cdr(1, channel="PJSIP/t1-101-00000001", dstchannel=TRUNK, src="712000000", dst="998901234567",
                duration=30, billsec=25, userfield="Beeline")]
    f = ev.ended_facts(rows)
    assert (f.direction, f.status, f.from_, f.to, f.extension, f.answered_by, f.did) == (
        "outbound", "answered", "101", "998901234567", "101", "101", None)
    unanswered = [cdr(1, channel="PJSIP/t1-101-00000001", dstchannel=TRUNK, dst="99890", disposition="NO ANSWER")]
    f = ev.ended_facts(unanswered)
    assert (f.status, f.to, f.answered_by) == ("missed", "99890", None)


def test_internal_call():
    rows = [cdr(1, channel="PJSIP/t1-101-00000001", dstchannel="PJSIP/t1-102-00000002", src="101", dst="102",
                billsec=4)]
    f = ev.ended_facts(rows)
    assert (f.direction, f.from_, f.to, f.extension, f.answered_by) == ("internal", "101", "102", "102", "102")
    no_dst = [cdr(1, channel="PJSIP/t1-101-00000001", src="101", dst="*97", disposition="ANSWERED")]
    f = ev.ended_facts(no_dst)
    assert (f.status, f.to, f.extension) == ("missed", "97", None)


def test_ended_call_payload():
    rows = [cdr(1, channel=TRUNK, src="998901234567", dstchannel="PJSIP/t1-101-00000002", billsec=6, duration=8)]
    facts = ev.ended_facts(rows)
    call = ev.ended_call("1700.1", facts, queue={"id": QID, "name": "Sotuv"}, origin=None,
                         recordings=[{"id": "r1", "duration_s": 6, "url": None}], did_hint="712000000")
    assert call == {
        "id": "1700.1", "direction": "inbound", "from": "998901234567", "to": "101", "did": "712000000",
        "extension": "101", "queue": {"id": QID, "name": "Sotuv"}, "status": "answered",
        "started_at": "2026-10-29T10:00:00Z", "answered_at": "2026-10-29T10:00:02Z", "ended_at": "2026-10-29T10:00:08Z",
        "duration_s": 8, "billsec": 6, "answered_by": "101", "recordings": [{"id": "r1", "duration_s": 6, "url": None}],
    }
    with_origin = ev.ended_call("x", facts, queue=None, origin={"source": "api", "external_id": None}, recordings=[])
    assert with_origin["origin"] == {"source": "api", "external_id": None}


def test_base_call_omits_origin_when_absent():
    call = ev.base_call(linkedid="1", direction="internal", from_="101", to="102", did=None, extension="102",
                        queue=None, origin=None)
    assert "origin" not in call and call["did"] is None
