"""M3c §1 — FreePBX import: AMPUSER `recording/{in,out}/{internal,external}` (4 kalit,
yo'nalish x ichki/tashqi) ikkita MUSTAQIL yo'nalishga (`recording`=kiruvchi, `recording_out`=
chiquvchi) bo'linadi — har biri faqat o'z yo'nalishining ikki kalitini ko'radi."""
from __future__ import annotations

from app.services.fpbx.mappers import extension as ext_mapper


def test_recording_mode_for_in_ignores_out_keys():
    ampuser = {"recording/in/internal": "force", "recording/in/external": "no",
               "recording/out/internal": "never", "recording/out/external": "never"}
    assert ext_mapper._recording_mode_for(ampuser, "in") == "always"
    assert ext_mapper._recording_mode_for(ampuser, "out") == "never"


def test_recording_mode_for_both_never_is_never():
    ampuser = {"recording/in/internal": "never", "recording/in/external": "no"}
    assert ext_mapper._recording_mode_for(ampuser, "in") == "never"


def test_recording_mode_for_mixed_is_on_demand():
    ampuser = {"recording/out/internal": "no", "recording/out/external": "dontcare"}
    assert ext_mapper._recording_mode_for(ampuser, "out") == "on_demand"


def test_recording_mode_for_missing_keys_is_on_demand():
    assert ext_mapper._recording_mode_for({}, "in") == "on_demand"


def test_map_extension_sets_both_directions_independently(monkeypatch):
    """`map_extension` to'liq oqimi: AMPUSER'dagi 4 kalit -> `recording`(in)/`recording_out`(out)."""
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        table=lambda name: {
            "users": [{"extension": "101", "name": "Ali", "ringtimer": "0", "outboundcid": None}],
            "devices": [{"id": "101", "tech": "pjsip"}],
            "findmefollow": [],
        }[name],
        eav=lambda name: {},
        astdb={},
        catalog=SimpleNamespace(extensions=set()),
    )
    monkeypatch.setattr(ext_mapper.astdb_mod, "top_level", lambda astdb, fam: {})
    monkeypatch.setattr(ext_mapper.astdb_mod, "family", lambda astdb, fam: {
        "recording/in/internal": "force", "recording/in/external": "force",
        "recording/out/internal": "never", "recording/out/external": "never",
    })
    entries = ext_mapper.map_extension(ctx)
    assert (entries[0].payload["recording"], entries[0].payload["recording_out"]) == ("always", "never")
