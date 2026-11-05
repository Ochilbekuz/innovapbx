"""`app/services/fpbx/mappers/ring_group.py` — 0038 (FreePBX Ring Groups parity):
to'liq strategiya to'plami, `annmsg_id`/`alertinfo`/`remotealert_id`/`needsconf`/
`ringing`/`recording` ko'chirilishi va "0"/bo'sh/yaroqsiz qiymatlar uchun
ogohlantirishlar."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.fpbx import dest as dest_mod
from app.services.fpbx.mappers import ring_group as rgm


def _ctx(ringgroups: list[dict], music: list[dict] | None = None, extensions: frozenset = frozenset({"101", "102"})):
    catalog = SimpleNamespace(extensions=extensions)
    return SimpleNamespace(
        table=lambda name: {"ringgroups": ringgroups, "music": music or []}[name],
        resolve=lambda raw: dest_mod.resolve_dest(raw, catalog),
        catalog=catalog,
    )


def _row(**overrides):
    base = dict(
        grpnum="600", strategy="ringall", grptime="20", grppre="", grplist="101-102",
        annmsg_id="0", postdest="hangup", description="Savdo", alertinfo="", remotealert_id="0",
        needsconf="0", toolate_id="0", ringing="0", cwignore="", cfignore="", cpickup="",
        recording="dontcare",
    )
    base.update(overrides)
    return base


def test_strategy_full_set_mapped_without_warning():
    for raw in ("ringall", "ringall-prim", "hunt", "hunt-prim", "memoryhunt", "memoryhunt-prim",
                "firstavailable", "firstnotonphone"):
        entry = rgm.map_ring_group(_ctx([_row(strategy=raw)]))[0]
        assert entry.payload["strategy"] == raw
        assert not any(w["code"] == "strategy_unsupported" for w in entry.warnings)


def test_unknown_strategy_falls_back_to_ringall_with_warning():
    entry = rgm.map_ring_group(_ctx([_row(strategy="random")]))[0]
    assert entry.payload["strategy"] == "ringall"
    assert entry.warnings[0]["code"] == "strategy_unsupported"


def test_annmsg_and_remotealert_zero_sentinel_means_none():
    entry = rgm.map_ring_group(_ctx([_row(annmsg_id="0", remotealert_id="0")]))[0]
    assert entry.payload["announcement_audio_id"] is None
    assert entry.payload["remote_announce_audio_id"] is None


def test_annmsg_and_remotealert_real_id_becomes_ref():
    entry = rgm.map_ring_group(_ctx([_row(annmsg_id="7", remotealert_id="9")]))[0]
    assert entry.payload["announcement_audio_id"] == {"$ref": "audio:recordings:7"}
    assert entry.payload["remote_announce_audio_id"] == {"$ref": "audio:recordings:9"}


def test_alert_info_valid_passthrough():
    entry = rgm.map_ring_group(_ctx([_row(alertinfo="Internal")]))[0]
    assert entry.payload["alert_info"] == "Internal"
    assert not any(w["code"] == "alert_info_invalid" for w in entry.warnings)


def test_alert_info_invalid_dropped_with_warning():
    entry = rgm.map_ring_group(_ctx([_row(alertinfo="bad info!")]))[0]
    assert entry.payload["alert_info"] is None
    assert entry.warnings[-1]["code"] == "alert_info_invalid"


def test_needsconf_true_values_map_to_confirm_calls():
    for raw in ("1", "yes", "true"):
        entry = rgm.map_ring_group(_ctx([_row(needsconf=raw)]))[0]
        assert entry.payload["confirm_calls"] is True
    entry = rgm.map_ring_group(_ctx([_row(needsconf="0")]))[0]
    assert entry.payload["confirm_calls"] is False


def test_ringing_zero_or_empty_means_plain_ring():
    for raw in ("0", "", None):
        entry = rgm.map_ring_group(_ctx([_row(ringing=raw)]))[0]
        assert entry.payload["ring_strategy_sound"] == "ring"
        assert entry.payload["moh_class_name"] is None


def test_ringing_with_known_music_id_maps_to_moh_class_name():
    music = [{"id": "1", "category": "sinov-moh"}]
    entry = rgm.map_ring_group(_ctx([_row(ringing="1")], music=music))[0]
    assert entry.payload["ring_strategy_sound"] == "moh"
    assert entry.payload["moh_class_name"] == "sinov-moh"
    assert not any(w["code"] == "moh_class_missing" for w in entry.warnings)


def test_ringing_with_unknown_music_id_falls_back_to_ring_with_warning():
    entry = rgm.map_ring_group(_ctx([_row(ringing="99")]))[0]
    assert entry.payload["ring_strategy_sound"] == "ring"
    assert entry.payload["moh_class_name"] is None
    assert entry.warnings[-1]["code"] == "moh_class_missing"


def test_recording_policy_mapping():
    assert rgm.map_ring_group(_ctx([_row(recording="force")]))[0].payload["recording_policy"] == "force"
    assert rgm.map_ring_group(_ctx([_row(recording="yes")]))[0].payload["recording_policy"] == "force"
    assert rgm.map_ring_group(_ctx([_row(recording="no")]))[0].payload["recording_policy"] == "no"
    assert rgm.map_ring_group(_ctx([_row(recording="dontcare")]))[0].payload["recording_policy"] == "dontcare"
