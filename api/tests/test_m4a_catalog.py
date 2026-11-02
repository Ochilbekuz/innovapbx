"""M4a §2 — MAC normallashtirish, User-Agent tahlili, so'rov fayl nomi, modellar katalogi, sozlamalar validatsiyasi,
IP xato limiti (sof funksiyalar)."""
from __future__ import annotations

import pytest

from app.services import prov_catalog as c
from app.services import prov_settings as s
from app.services.prov_guard import FailureGuard


# ------------------------------------------------------------------ MAC
@pytest.mark.parametrize("raw", ["80:5E:C0:AA:BB:CC", "80-5e-c0-aa-bb-cc", "805e.c0aa.bbcc", "805EC0AABBCC",
                                 " 80 5e c0 aa bb cc "])
def test_normalize_mac(raw: str) -> None:
    assert c.normalize_mac(raw) == "805ec0aabbcc"


@pytest.mark.parametrize("raw", ["", "805ec0aabb", "805ec0aabbccdd", "805ec0aabbcg", "00:00:00:00:00:00", None])
def test_normalize_mac_rejects(raw) -> None:
    with pytest.raises(c.InvalidMac):
        c.normalize_mac(raw)
    assert c.try_mac(raw) is None


# ------------------------------------------------------------------ User-Agent
@pytest.mark.parametrize(("ua", "expected"), [
    ("Yealink SIP-T46U 108.86.0.20 805ec0aabbcc", c.UaInfo("yealink", "T46U", "108.86.0.20", "805ec0aabbcc")),
    ("Yealink SIP-T54W 96.86.0.100", c.UaInfo("yealink", "T54W", "96.86.0.100", None)),
    ("yealink T31P 124.86.0.40 80:5E:C0:11:22:33", c.UaInfo("yealink", "T31P", "124.86.0.40", "805ec0112233")),
    ("Grandstream Model HW GXP2170 SW 1.0.11.3 DevId c074ad112233",
     c.UaInfo("grandstream", "GXP2170", "1.0.11.3", "c074ad112233")),
    ("Grandstream Model HW GRP2614 SW 1.0.5.15", c.UaInfo("grandstream", "GRP2614", "1.0.5.15", None)),
    ("Fanvil X4U 2.12.1 0c383e112233", c.UaInfo("fanvil", "X4U", "2.12.1", "0c383e112233")),
    ("Fanvil x3s 2.4.5", c.UaInfo("fanvil", "X3S", "2.4.5", None)),
    ("curl/8.5.0", c.UaInfo()),
    ("", c.UaInfo()),
    (None, c.UaInfo()),
])
def test_parse_user_agent(ua, expected) -> None:
    assert c.parse_user_agent(ua) == expected


def test_ua_bad_mac_is_none() -> None:
    assert c.parse_user_agent("Yealink SIP-T46U 108.86.0.20 000000000000").mac is None


# ------------------------------------------------------------------ fayl nomi
@pytest.mark.parametrize(("name", "expected"), [
    ("y000000000000.cfg", c.ProvFile("common")),
    ("y000000000028.cfg", c.ProvFile("common")),
    ("Y00000000002A.CFG", c.ProvFile("common")),
    ("805ec0aabbcc.cfg", c.ProvFile("device_cfg", "805ec0aabbcc")),
    ("805EC0AABBCC.cfg", c.ProvFile("device_cfg", "805ec0aabbcc")),
    ("cfgc074ad112233.xml", c.ProvFile("device_xml", "c074ad112233")),
    ("cfgc074ad112233", c.ProvFile("legacy_binary", "c074ad112233")),
    ("000000000000.cfg", c.ProvFile("unknown")),
    ("y000000000000.boot", c.ProvFile("unknown")),
    ("../etc/passwd", c.ProvFile("unknown")),
    ("", c.ProvFile("unknown")),
])
def test_parse_filename(name: str, expected: c.ProvFile) -> None:
    assert c.parse_filename(name) == expected


def test_guess_vendor() -> None:
    yealink = c.UaInfo("yealink", "T46U")
    fanvil = c.UaInfo("fanvil", "X4U")
    assert c.guess_vendor("device_cfg", yealink) == "yealink"
    assert c.guess_vendor("device_cfg", fanvil) == "fanvil"
    assert c.guess_vendor("device_cfg", c.UaInfo()) is None
    assert c.guess_vendor("device_xml", yealink) == "grandstream"
    assert c.guess_vendor("unknown", yealink) is None


# ------------------------------------------------------------------ katalog
def test_models_catalog() -> None:
    assert c.find_model("yealink", " t46u ") == c.PhoneModel("yealink", "T46U", 27, "T4x")
    assert c.find_model("grandstream", "GXP2170").family == "GXP21xx"
    assert c.find_model("fanvil", "X4U").keys == 12
    assert c.find_model("yealink", "GXP2170") is None and c.find_model(None, "T46U") is None
    assert c.find_model("yealink", None) is None
    assert {m.vendor for m in c.MODELS} == set(c.VENDORS)
    assert all(0 <= m.keys <= c.MAX_KEYS for m in c.MODELS)
    assert len({(m.vendor, m.model) for m in c.MODELS}) == len(c.MODELS)


# ------------------------------------------------------------------ sozlamalar
def test_settings_defaults_and_roundtrip() -> None:
    cfg = s.ProvSettings.from_raw({"prov_token": "a" * 32})
    assert cfg.allowed_networks == s.DEFAULT_NETWORKS and cfg.language == "uz" and cfg.sip_transport == "udp"
    assert cfg.extra == {"yealink": "", "grandstream": "", "fanvil": ""} and cfg.has_valid_token()
    assert s.ProvSettings.from_raw(cfg.to_raw()) == cfg
    assert s.ProvSettings.from_raw({"allowed_networks": []}).allowed_networks == ()
    assert not s.ProvSettings.from_raw(None).has_valid_token()
    assert len(s.new_token()) == 32 and s.new_token() != s.new_token()


def test_validate_networks() -> None:
    assert s.validate_networks(["10.1.2.3/8", " 192.168.1.0/24", "10.0.0.0/8", "2001:db8::/32"]) == (
        "10.0.0.0/8", "192.168.1.0/24", "2001:db8::/32")
    with pytest.raises(s.ProvSettingsError) as err:
        s.validate_networks(["10.0.0.0/33"])
    assert err.value.field == "allowed_networks"
    with pytest.raises(s.ProvSettingsError):
        s.validate_networks(["10.0.0.0/8"] * (s.MAX_NETWORKS + 1))
    assert s.validate_networks(["10.0.0.0/8"] * s.MAX_NETWORKS) == ("10.0.0.0/8",)


def test_validate_timezone_and_host() -> None:
    assert s.validate_timezone("Europe/Moscow") == "Europe/Moscow"
    for bad in ("Mars/Base", "../etc"):
        with pytest.raises(s.ProvSettingsError):
            s.validate_timezone(bad)
    assert s.validate_host("sip_server_host", " pbx.example.uz ") == "pbx.example.uz"
    assert s.validate_host("h", "10.0.0.5") == "10.0.0.5" and s.validate_host("h", "") is None
    assert s.validate_host("h", None) is None
    for bad in ("http://x", "pbx:5060", "a b", "-x.uz", "x\nstatic.y=1"):
        with pytest.raises(s.ProvSettingsError) as err:
            s.validate_host("sip_server_host", bad)
        assert err.value.field == "sip_server_host"


@pytest.mark.parametrize(("vendor", "good", "bad"), [
    ("yealink", "features.dnd.enable = 1\r\n# izoh\n\nlang.gui=Russian", "bad line without equals"),
    ("grandstream", "P8=1\nP1234 = a b", "Pabc=1"),
    ("fanvil", "<PHONE FEATURE MODULE>\nEnable DND :1", "key = value"),
])
def test_validate_extra(vendor: str, good: str, bad: str) -> None:
    assert "\r" not in s.validate_extra(vendor, good)
    assert "\n\n" not in s.validate_extra(vendor, good)
    with pytest.raises(s.ProvSettingsError) as err:
        s.validate_extra(vendor, good + "\n" + bad)
    assert err.value.field == f"extra.{vendor}"
    assert s.validate_extra(vendor, "") == ""


def test_validate_extra_line_limit() -> None:
    ok = "\n".join(f"a.b{i} = 1" for i in range(s.MAX_EXTRA_LINES))
    assert s.validate_extra("yealink", ok) == ok
    with pytest.raises(s.ProvSettingsError):
        s.validate_extra("yealink", ok + "\nx.y = 2")


def test_ip_allowed() -> None:
    nets = ("10.0.0.0/8", "172.16.0.0/12")
    assert s.ip_allowed("172.21.0.5", nets) and s.ip_allowed("10.255.0.1", nets)
    assert not s.ip_allowed("8.8.8.8", nets) and not s.ip_allowed(None, nets) and not s.ip_allowed("x", nets)
    assert s.ip_allowed("8.8.8.8", ())


# ------------------------------------------------------------------ IP xato limiti
class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_guard_blocks_on_limit_and_expires() -> None:
    clock = Clock()
    guard = FailureGuard(clock, limit=3, window_s=10, block_s=30)
    assert [guard.record_failure("a") for _ in range(3)] == [False, False, True]
    assert guard.is_blocked("a") and not guard.is_blocked("b")
    clock.now += 29.9
    assert guard.is_blocked("a")
    clock.now += 0.1
    assert not guard.is_blocked("a")
    assert not guard.record_failure("a")  # hisob blokdan keyin noldan


def test_guard_window_slides() -> None:
    clock = Clock()
    guard = FailureGuard(clock, limit=3, window_s=10, block_s=30)
    guard.record_failure("a")
    clock.now += 5
    guard.record_failure("a")
    clock.now += 5  # birinchisi aynan oynadan chiqdi
    assert not guard.record_failure("a")
    assert guard.record_failure("a")


def test_guard_memory_bounded_and_reset() -> None:
    guard = FailureGuard(Clock(), limit=5, max_ips=2)
    for ip in ("a", "b", "c"):
        guard.record_failure(ip)
    assert list(guard._failures) == ["b", "c"]
    guard.reset()
    assert guard._failures == {} and guard._blocked_until == {}


def test_guard_defaults() -> None:
    guard = FailureGuard(Clock())
    assert [guard.record_failure("x") for _ in range(20)][-2:] == [False, True]
