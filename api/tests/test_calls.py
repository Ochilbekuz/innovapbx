"""`/calls` CDR guruhlash — sof funksiyalar, bazasiz (ub-mode: TDD, mutator nishoni).

Asosiy holat: bitta `uniqueid`ga ega bir nechta `cdr` qatori (masalan `Queue()` har
a'zo-urinishi uchun alohida qator yaratadi) — biror oyoq ANSWERED bo'lsa, butun
qo'ng'iroq "javob berildi" deb ko'rsatilishi, `billsec`/`duration` esa O'SHA
javob berilgan oyoqnikidan olinishi SHART (IVR boshlang'ich oyoqning emas)."""
from __future__ import annotations

from datetime import datetime

from app.db.models import Cdr
from app.services.cdr_grouping import (
    answered_leg as _answered_leg,
    call_out_from_group as _call_out_from_group,
    group_by_uniqueid as _group_by_uniqueid,
    primary_leg as _primary_leg,
)


def _cdr(**kw) -> Cdr:
    defaults = dict(
        calldate=datetime(2026, 10, 27, 12, 0, 0), clid=None, src="trunkcaller", dst="s",
        dcontext="t1-dest-x", channel="PJSIP/t1-trunk-1-00000000", dstchannel=None,
        lastapp="Dial", lastdata=None, duration=0, billsec=0, disposition="NO ANSWER",
        amaflags=None, accountcode="t1", uniqueid="1.0", linkedid="1.0", userfield="712099301",
        peeraccount=None, sequence=0, recordingfile=None,
    )
    defaults.update(kw)
    return Cdr(**defaults)


def test_group_by_uniqueid_keeps_first_seen_order():
    rows = [_cdr(uniqueid="a", sequence=0), _cdr(uniqueid="b", sequence=0), _cdr(uniqueid="a", sequence=1)]
    groups = _group_by_uniqueid(rows)
    assert [g[0].uniqueid for g in groups] == ["a", "b"]
    assert len(groups[0]) == 2


def test_answered_leg_finds_answered_row_case_insensitively():
    group = [_cdr(disposition="NO ANSWER"), _cdr(disposition="Answered", billsec=12)]
    winner = _answered_leg(group)
    assert winner is not None and winner.billsec == 12


def test_answered_leg_returns_none_when_nobody_answered():
    group = [_cdr(disposition="NO ANSWER"), _cdr(disposition="NO ANSWER")]
    assert _answered_leg(group) is None


def test_primary_leg_is_lowest_sequence():
    group = [_cdr(sequence=3), _cdr(sequence=0), _cdr(sequence=1)]
    assert _primary_leg(group).sequence == 0


def test_call_out_from_group_uses_answered_leg_disposition_and_billsec():
    """Ssenariy 1 naqshi: IVR -> Queue() 2 a'zo, biri ANSWERED. Guruh natijasi
    "answered" bo'lishi va billsec ANSWERED oyoqnikidan kelishi SHART."""
    group = [
        _cdr(uniqueid="u1", sequence=0, dstchannel="PJSIP/t1-102-1", disposition="NO ANSWER", billsec=1),
        _cdr(uniqueid="u1", sequence=1, dstchannel="PJSIP/t1-101-1", disposition="ANSWERED", billsec=16,
             duration=16),
    ]
    out = _call_out_from_group(group)
    assert out.disposition == "answered"
    assert out.billsec == 16
    assert out.duration == 16
    assert out.did == "712099301"


def test_call_out_from_group_falls_back_to_primary_when_nobody_answered():
    group = [_cdr(uniqueid="u2", sequence=0, disposition="NO ANSWER", billsec=0, duration=5)]
    out = _call_out_from_group(group)
    assert out.disposition == "no_answer"
    assert out.duration == 5


def test_call_out_from_group_internal_direction_has_no_did():
    group = [_cdr(channel="PJSIP/t1-101-1", userfield="712099301")]
    out = _call_out_from_group(group)
    assert out.direction == "internal"
    assert out.did is None


def test_call_out_from_group_outbound_direction_reports_trunk_and_no_did():
    """compiler.py `_route_trunk_dial_lines`: trunk Dial'dan OLDIN
    `Set(CDR(userfield)=<trunk nomi>)` — shu sabab manba (`channel`) ICHKI,
    manzil (`dstchannel`) TRUNK bo'lsa direction="out", `trunk` — userfield."""
    group = [_cdr(
        channel="PJSIP/t1-101-00000001", dstchannel="PJSIP/t1-trunk-abc-00000002",
        userfield="Trunk A", dst="998901234567", disposition="ANSWERED", billsec=10, duration=10,
    )]
    out = _call_out_from_group(group)
    assert out.direction == "out"
    assert out.trunk == "Trunk A"
    assert out.did is None
    assert out.dst == "998901234567"


def test_call_out_from_group_inbound_trunk_name_from_channel_id():
    group = [_cdr(channel="PJSIP/t1-trunk-1-00000000", dstchannel="PJSIP/t1-101-1", userfield="712099301")]
    assert _call_out_from_group(group).trunk is None  # nomlar xaritasi berilmagan
    out = _call_out_from_group(group, {"1": "Uztelecom", "2": "Beeline"})
    assert out.direction == "in"
    assert out.trunk == "Uztelecom"
    assert out.did == "712099301"
    internal = [_cdr(channel="PJSIP/t1-101-1", dstchannel="PJSIP/t1-102-1")]
    assert _call_out_from_group(internal, {"1": "Uztelecom"}).trunk is None


def test_trunk_id_of_parses_endpoint_uuid():
    from app.services.cdr_grouping import trunk_id_of
    uid = "5b3c9f2e-1d4a-4b6e-9a7c-0f1e2d3c4b5a"
    assert trunk_id_of(f"PJSIP/acme-trunk-{uid}-0000001a") == uid
    assert trunk_id_of("PJSIP/acme-101-0000001a") is None
    assert trunk_id_of("PJSIP/acme-trunk-") is None
    assert trunk_id_of(None) is None
