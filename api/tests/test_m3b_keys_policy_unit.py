"""M3b §1/§4 — API kalit, originate raqami, yozuv siyosati, imzoli havola (sof funksiyalar)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import api_keys, originate, recording_policy, recordings

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------ API kalit
def test_generate_key_format_and_hash():
    key = api_keys.generate_key()
    assert api_keys.KEY_RE.fullmatch(key.plaintext)
    assert key.plaintext.startswith(f"ipk_{key.prefix}_")
    assert key.key_hash == hashlib.sha256(key.plaintext.encode()).hexdigest()
    assert api_keys.generate_key().plaintext != key.plaintext


@pytest.mark.parametrize("raw", [
    "", "ipk_", "ipk_abcdefgh_short", "xpk_abcdefgh_" + "a" * 32, "ipk_ABCDEFGH_" + "a" * 32,
    "ipk_abcdefgh_" + "a" * 33, "ipk_abcdefgh_" + "a" * 31 + "!", "ipk_abcdefgh_" + "a" * 32 + "\n",
])
def test_parse_prefix_rejects_malformed(raw):
    assert api_keys.parse_prefix(raw) is None


def test_parse_prefix_ok_and_match():
    key = api_keys.generate_key()
    assert api_keys.parse_prefix(key.plaintext) == key.prefix
    assert api_keys.key_matches(key.plaintext, key.key_hash)
    assert not api_keys.key_matches(key.plaintext[:-1] + ("A" if key.plaintext[-1] != "A" else "B"), key.key_hash)


def test_validate_scopes():
    assert api_keys.validate_scopes(["calls:read", "calls:read", "extensions:read"]) == ["calls:read", "extensions:read"]
    with pytest.raises(ValueError):
        api_keys.validate_scopes(["calls:write"])
    with pytest.raises(ValueError):
        api_keys.validate_scopes([])


def test_key_usable():
    row = SimpleNamespace(revoked_at=None, expires_at=None)
    assert api_keys.key_usable(row, NOW)
    assert not api_keys.key_usable(SimpleNamespace(revoked_at=NOW, expires_at=None), NOW)
    assert not api_keys.key_usable(SimpleNamespace(revoked_at=None, expires_at=NOW), NOW)
    assert api_keys.key_usable(SimpleNamespace(revoked_at=None, expires_at=NOW + timedelta(seconds=1)), NOW)


def test_should_touch_last_used():
    assert api_keys.should_touch(None, NOW)
    assert not api_keys.should_touch(NOW - timedelta(seconds=59), NOW)
    assert api_keys.should_touch(NOW - timedelta(seconds=60), NOW)


def test_has_scope():
    assert api_keys.has_scope(["calls:read"], "calls:read")
    assert not api_keys.has_scope(["calls:read"], "calls:originate")


# ------------------------------------------------------------ originate
@pytest.mark.parametrize("raw,expected", [
    ("+998 90 123-45-67", "998901234567"), ("101", "101"), ("(71) 200-00-00", "712000000"),
    ("*97", "*97"), ("12#", "12#"), ("+1", "1"),
])
def test_validate_to_ok(raw, expected):
    assert originate.validate_to(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", "101\r\nAction: Command", "101\n", "abc", "1" * 33, "+", "1;2", "1,2", "1@x", "1/2", "١٢٣",
])
def test_validate_to_rejects(raw):
    with pytest.raises(originate.InvalidNumber):
        originate.validate_to(raw)


def test_validate_external_id():
    assert originate.validate_external_id(None) is None
    assert originate.validate_external_id("crm-42.a:b_c") == "crm-42.a:b_c"
    for bad in ("", "a b", "x,y", "a\r\n", "z" * 65, "ч"):
        with pytest.raises(originate.InvalidExternalId):
            originate.validate_external_id(bad)


def test_originate_fields():
    f = originate.originate_fields("t1", "101", "998901234567", request_id="req-1", external_id="e1")
    assert f["Channel"] == "PJSIP/101"
    assert f["Context"] == "t1-originate" and f["Exten"] == "998901234567" and f["Priority"] == "1"
    assert f["Async"] == "true" and f["ChannelId"] == "req-1"
    assert f["Variable"] == "INNOVA_ORIGIN=api,INNOVA_EXTID=e1,INNOVA_ORIG_EXT=101"
    assert f["CallerID"] == '"998901234567" <998901234567>'
    f2 = originate.originate_fields("t1", "101", "5", request_id="r", external_id=None)
    assert f2["Variable"] == "INNOVA_ORIGIN=api,INNOVA_EXTID=,INNOVA_ORIG_EXT=101"


# ------------------------------------------------------------ yozuv siyosati
P = recording_policy


def test_inbound_policy_is_answering_extension():
    assert P.decide(a=None, b="always", src=None, a_is_ext=False, b_is_ext=True, external_only=False).record
    d = P.decide(a=None, b="never", src=None, a_is_ext=False, b_is_ext=True, external_only=True)
    assert not d.record
    d = P.decide(a=None, b="on_demand", src=None, a_is_ext=False, b_is_ext=True, external_only=False)
    assert (d.record, d.on_demand_b, d.on_demand_a) == (False, True, False)


def test_outbound_policy_is_source_extension():
    assert P.decide(a="always", b=None, src=None, a_is_ext=True, b_is_ext=False, external_only=True).record
    assert not P.decide(a="never", b=None, src=None, a_is_ext=True, b_is_ext=False, external_only=False).record
    # Yo'naltirish: manba (forward qilgan) raqam siyosati.
    assert P.decide(a=None, b=None, src="always", a_is_ext=False, b_is_ext=False, external_only=False).record
    assert not P.decide(a="always", b=None, src="never", a_is_ext=True, b_is_ext=False, external_only=False).record
    d = P.decide(a="on_demand", b=None, src=None, a_is_ext=True, b_is_ext=False, external_only=False)
    assert (d.record, d.on_demand_a) == (False, True)


def test_internal_policy():
    kw = {"src": None, "a_is_ext": True, "b_is_ext": True}
    assert P.decide(a="always", b="on_demand", external_only=False, **kw).record
    assert P.decide(a="on_demand", b="always", external_only=False, **kw).record
    assert not P.decide(a="always", b="never", external_only=False, **kw).record
    assert not P.decide(a="never", b="always", external_only=False, **kw).record
    assert not P.decide(a="on_demand", b="on_demand", external_only=False, **kw).record
    d = P.decide(a="always", b="always", external_only=True, **kw)
    assert (d.record, d.on_demand_b) == (False, False)
    assert P.decide(a="on_demand", b="on_demand", external_only=False, **kw).on_demand_b


# ------------------------------------------------------------ imzoli havola
def test_signed_link_roundtrip_and_tamper():
    exp = int(NOW.timestamp()) + 60
    sig = recordings.link_signature("rec-1", exp, "sk")
    assert recordings.verify_link("rec-1", exp, sig, now_unix=int(NOW.timestamp()), secret_key="sk")
    assert not recordings.verify_link("rec-2", exp, sig, now_unix=int(NOW.timestamp()), secret_key="sk")
    assert not recordings.verify_link("rec-1", exp + 1, sig, now_unix=int(NOW.timestamp()), secret_key="sk")
    assert not recordings.verify_link("rec-1", exp, sig, now_unix=int(NOW.timestamp()), secret_key="other")
    assert not recordings.verify_link("rec-1", exp, sig, now_unix=exp, secret_key="sk")  # muddati o'tgan
    assert not recordings.verify_link("rec-1", exp, "zz", now_unix=int(NOW.timestamp()), secret_key="sk")


def test_link_key_is_domain_separated():
    import hmac

    raw = hmac.new(b"sk", b"rec-1.10", hashlib.sha256).hexdigest()
    assert recordings.link_signature("rec-1", 10, "sk") != raw


def test_signed_url():
    url = recordings.signed_url("https://pbx.example.uz/", "rec-1", ttl_s=100, now_unix=1000, secret_key="sk")
    sig = recordings.link_signature("rec-1", 1100, "sk")
    assert url == f"https://pbx.example.uz/api/public/v1/recordings/rec-1?exp=1100&sig={sig}"
    assert recordings.signed_url("", "rec-1", ttl_s=100, now_unix=1000, secret_key="sk") is None


def test_recording_paths():
    start = datetime(2026, 10, 29, 23, 59, tzinfo=timezone.utc)
    assert recordings.date_dirs(start, start + timedelta(minutes=5)) == ["innova/2026/10/29", "innova/2026/10/30"]
    assert recordings.date_dirs(start, start) == ["innova/2026/10/29"]
    assert recordings.uniqueid_from_name("1700.5-1700.7.wav", "1700.5") == "1700.7"
    assert recordings.uniqueid_from_name("a-b-c-d-e.wav", "a-b") == "c-d-e"
    assert recordings.uniqueid_from_name("x.wav", "1700.5") is None


def test_retention_cutoff():
    assert recordings.retention_cutoff(NOW, 30) == NOW - timedelta(days=30)
