"""`app/services/live.py` sof funksiyalari — `GET /live`/`POST /live/spy`
(m2b-contract.md §2). AMI/DB'siz; `build_live_status` orkestratsiyasi
`test_integration_live.py`da (jonli stack bo'lsa)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.live import (
    agent_live_state,
    build_call_item,
    build_waiting_items,
    channel_extension_number,
    extension_live_state,
    group_channels_by_linkedid,
    pick_agent_channel,
)

_NOW = datetime(2026, 10, 28, 10, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------- kanal raqami
def test_channel_extension_number_extracts_from_pjsip_channel():
    assert channel_extension_number("PJSIP/t1-201-00000003") == "201"


def test_channel_extension_number_none_for_trunk_leg():
    assert channel_extension_number("PJSIP/t1-trunk-1-00000002") is None


def test_channel_extension_number_none_for_unmatched_channel():
    assert channel_extension_number("Local/700@parkedcalls-00000001;2") is None
    assert channel_extension_number("") is None


# --------------------------------------------------------------- guruhlash
def test_group_channels_by_linkedid_preserves_first_seen_order():
    channels = [
        {"Channel": "a", "Linkedid": "L1"},
        {"Channel": "b", "Linkedid": "L2"},
        {"Channel": "c", "Linkedid": "L1"},
    ]
    groups = group_channels_by_linkedid(channels)
    assert [c["Channel"] for c in groups[0]] == ["a", "c"]
    assert [c["Channel"] for c in groups[1]] == ["b"]


def test_group_channels_by_linkedid_falls_back_to_uniqueid_then_channel():
    channels = [{"Channel": "a", "Uniqueid": "U1"}, {"Channel": "b"}]
    groups = group_channels_by_linkedid(channels)
    assert len(groups) == 2


# --------------------------------------------------------------- call item
def test_build_call_item_up_state_for_bridged_pair():
    group = [
        {"Channel": "PJSIP/t1-201-00000001", "Linkedid": "L1", "Uniqueid": "L1", "BridgeId": "br1",
         "Application": "Dial", "ApplicationData": "PJSIP/t1-202", "ChannelStateDesc": "Up",
         "CallerIDNum": "201", "Exten": "202", "Duration": "00:00:10"},
        {"Channel": "PJSIP/t1-202-00000002", "Linkedid": "L1", "Uniqueid": "L1-2", "BridgeId": "br1",
         "Application": "Dial", "ApplicationData": "", "ChannelStateDesc": "Up",
         "CallerIDNum": "201", "Exten": "202", "Duration": "00:00:08"},
    ]
    item = build_call_item(group, now=_NOW, queue_ids_by_name={})
    assert item["id"] == "L1"
    assert item["direction"] == "internal"
    assert item["from"] == "201"
    assert item["to"] == "202"
    assert item["state"] == "up"
    assert item["extension"] == "202"
    assert item["started_at"] == _NOW - timedelta(seconds=10)
    assert item["answered_at"] == _NOW - timedelta(seconds=8)
    assert item["channels"] == ["PJSIP/t1-201-00000001", "PJSIP/t1-202-00000002"]


def test_build_call_item_queued_state_when_queue_app_not_bridged():
    group = [{"Channel": "PJSIP/t1-trunk-1-00000001", "Linkedid": "L2", "Application": "Queue",
              "ApplicationData": "t1-q-abc,t", "ChannelStateDesc": "Up", "CallerIDNum": "998901234567",
              "Exten": "600", "Duration": "00:00:03"}]
    item = build_call_item(group, now=_NOW, queue_ids_by_name={"t1-q-abc": "qid-1"})
    assert item["state"] == "queued"
    assert item["queue_id"] == "qid-1"
    assert item["direction"] == "inbound"
    assert item["answered_at"] is None


def test_build_call_item_ringing_state_from_channel_state_desc():
    group = [{"Channel": "PJSIP/t1-201-00000001", "Linkedid": "L3", "Application": "Dial",
              "ChannelStateDesc": "Ringing", "CallerIDNum": "201", "Exten": "202", "Duration": "00:00:01"}]
    item = build_call_item(group, now=_NOW, queue_ids_by_name={})
    assert item["state"] == "ringing"


def test_build_call_item_parked_overrides_other_states():
    group = [{"Channel": "Local/700@parkedcalls-00000001;2", "Linkedid": "L4", "Application": "ParkedCall",
              "ChannelStateDesc": "Up", "CallerIDNum": "201", "Exten": "700", "Duration": "00:00:05",
              "BridgeId": "br9"}]
    item = build_call_item(group, now=_NOW, queue_ids_by_name={})
    assert item["state"] == "parked"


def test_build_call_item_multi_channel_group_without_bridgeid_is_still_up():
    """`bridged = len(ordered) > 1 or bool(BridgeId)` — ikki oyoqli guruh
    `BridgeId'siz` ham "up" bo'lishi kerak (mutatsiya: `or` -> `and`)."""
    group = [
        {"Channel": "PJSIP/t1-201-00000001", "Linkedid": "L5", "Application": "Dial",
         "ChannelStateDesc": "Up", "CallerIDNum": "201", "Exten": "202", "Duration": "00:00:10"},
        {"Channel": "PJSIP/t1-202-00000002", "Linkedid": "L5", "Application": "Dial",
         "ChannelStateDesc": "Up", "CallerIDNum": "201", "Exten": "202", "Duration": "00:00:08"},
    ]
    item = build_call_item(group, now=_NOW, queue_ids_by_name={})
    assert item["state"] == "up"


# --------------------------------------------------------------- navbat kutish
def test_build_waiting_items_filters_by_queue_and_sorts_by_position():
    entries = [
        {"Event": "QueueEntry", "Queue": "t1-q-a", "CallerIDNum": "100", "Wait": "20", "Position": "2"},
        {"Event": "QueueParams", "Queue": "t1-q-a"},
        {"Event": "QueueEntry", "Queue": "t1-q-b", "CallerIDNum": "999", "Wait": "1", "Position": "1"},
        {"Event": "QueueEntry", "Queue": "t1-q-a", "CallerIDNum": "101", "Wait": "5", "Position": "1"},
    ]
    items = build_waiting_items(entries, "t1-q-a", _NOW)
    assert [i["from"] for i in items] == ["101", "100"]
    assert items[0]["since"] == _NOW - timedelta(seconds=5)
    assert items[0]["position"] == 1


def test_build_waiting_items_missing_wait_defaults_to_zero():
    """`e.get("Wait") or 0` — `Wait` kaliti umuman yo'q bo'lsa ham 0 (mutatsiya: 0 -> 1)."""
    entries = [{"Event": "QueueEntry", "Queue": "t1-q-a", "CallerIDNum": "100", "Position": "1"}]
    items = build_waiting_items(entries, "t1-q-a", _NOW)
    assert items[0]["since"] == _NOW


def test_build_waiting_items_missing_position_defaults_to_zero():
    """`e.get("Position") or 0` — `Position` kaliti yo'q bo'lsa ham 0 (mutatsiya: 0 -> 1)."""
    entries = [{"Event": "QueueEntry", "Queue": "t1-q-a", "CallerIDNum": "100", "Wait": "5"}]
    items = build_waiting_items(entries, "t1-q-a", _NOW)
    assert items[0]["position"] == 0


# --------------------------------------------------------------------- holat
def test_extension_live_state_dnd_wins_over_everything():
    assert extension_live_state(dnd=True, online=True, busy=True, ringing=True) == "dnd"


def test_extension_live_state_offline_when_not_online():
    assert extension_live_state(dnd=False, online=False, busy=False, ringing=False) == "unavailable"


def test_extension_live_state_ringing_busy_idle_priority():
    assert extension_live_state(dnd=False, online=True, busy=False, ringing=True) == "ringing"
    assert extension_live_state(dnd=False, online=True, busy=True, ringing=False) == "busy"
    assert extension_live_state(dnd=False, online=True, busy=False, ringing=False) == "idle"


def test_agent_live_state_offline_when_dynamic_and_logged_out_even_if_online():
    assert agent_live_state(dynamic=True, logged_in=False, paused=False, online=True, busy=False,
                             ringing=False) == "offline"


def test_agent_live_state_unavailable_when_not_online():
    assert agent_live_state(dynamic=False, logged_in=False, paused=False, online=False, busy=False,
                             ringing=False) == "unavailable"


def test_agent_live_state_paused_ringing_busy_idle_priority():
    assert agent_live_state(dynamic=False, logged_in=False, paused=True, online=True, busy=False,
                             ringing=False) == "paused"
    assert agent_live_state(dynamic=True, logged_in=True, paused=False, online=True, busy=False,
                             ringing=True) == "ringing"
    assert agent_live_state(dynamic=True, logged_in=True, paused=False, online=True, busy=True,
                             ringing=False) == "busy"
    assert agent_live_state(dynamic=True, logged_in=True, paused=False, online=True, busy=False,
                             ringing=False) == "idle"


# --------------------------------------------------------------------- spy
_CHANNELS = [
    {"Channel": "PJSIP/t1-trunk-1-00000001", "Linkedid": "L1", "Uniqueid": "L1"},
    {"Channel": "PJSIP/t1-201-00000002", "Linkedid": "L1", "Uniqueid": "L1-2"},
]


def test_pick_agent_channel_by_explicit_channel_if_present():
    assert pick_agent_channel(_CHANNELS, call_id=None, channel="PJSIP/t1-201-00000002") == "PJSIP/t1-201-00000002"


def test_pick_agent_channel_explicit_channel_absent_returns_none():
    assert pick_agent_channel(_CHANNELS, call_id=None, channel="PJSIP/t1-999-x") is None


def test_pick_agent_channel_by_call_id_prefers_extension_leg():
    assert pick_agent_channel(_CHANNELS, call_id="L1", channel=None) == "PJSIP/t1-201-00000002"


def test_pick_agent_channel_unknown_call_id_returns_none():
    assert pick_agent_channel(_CHANNELS, call_id="unknown", channel=None) is None


def test_pick_agent_channel_prefers_filtered_pool_over_full_group():
    """`pool = [...] or group` — filtrlangan ro'yxat BO'SH BO'LMAGANDA ham
    to'liq guruh emas, FAQAT u ishlatilishi kerak (mutatsiya: `or` -> `and`
    filtrlangan ro'yxat bo'sh bo'lmasa ham to'liq guruhni qaytarib yuboradi,
    bu yerda trunk oyog'i ext oyog'idan KEYINGI yaratilgan qilib qo'yilgan —
    xato bo'lsa trunk tanlanadi)."""
    channels = [
        {"Channel": "PJSIP/t1-201-00000001", "Linkedid": "L9", "Uniqueid": "L9"},
        {"Channel": "PJSIP/t1-trunk-1-00000005", "Linkedid": "L9", "Uniqueid": "L9-2"},
    ]
    assert pick_agent_channel(channels, call_id="L9", channel=None) == "PJSIP/t1-201-00000001"


def test_pick_agent_channel_returns_highest_sequence_from_pool():
    """Pool'da bir nechta ext kanal bo'lsa — ENG OXIRGI yaratilgani (eng katta
    ketma-ketlik) tanlanadi (mutatsiya: `[-1]` -> `[0]`)."""
    channels = [
        {"Channel": "PJSIP/t1-201-00000001", "Linkedid": "L10", "Uniqueid": "L10"},
        {"Channel": "PJSIP/t1-202-00000002", "Linkedid": "L10", "Uniqueid": "L10-2"},
    ]
    assert pick_agent_channel(channels, call_id="L10", channel=None) == "PJSIP/t1-202-00000002"
