"""`app/services/security_config.py` — sof `parse_*`/`check_*` (CTO yozgan,
hali sinovsiz edi — m2c-contract.md §1 chegaralari)."""
from __future__ import annotations

import pytest

from app.services.security_config import (
    ALERT_KINDS,
    ALWAYS_TRUSTED,
    AlertConfig,
    SipGuardConfig,
    TollFraudConfig,
    check_chat_ids,
    check_int,
    check_nets,
    is_trusted,
    parse_alerts,
    parse_sip_guard,
    parse_toll_fraud,
    to_json,
)


def test_parse_sip_guard_defaults_on_none():
    cfg = parse_sip_guard(None)
    assert cfg == SipGuardConfig()


def test_parse_sip_guard_merges_known_keys_only():
    cfg = parse_sip_guard({"max_failures": 10, "unknown_key": "x"})
    assert cfg.max_failures == 10
    assert cfg.enabled is True
    assert not hasattr(cfg, "unknown_key")


def test_parse_sip_guard_trusted_nets_becomes_tuple():
    cfg = parse_sip_guard({"trusted_nets": ["10.0.0.0/8", "192.168.1.0/24"]})
    assert cfg.trusted_nets == ("10.0.0.0/8", "192.168.1.0/24")


def test_parse_toll_fraud_defaults_on_none():
    assert parse_toll_fraud(None) == TollFraudConfig()


def test_parse_toll_fraud_partial_merge_keeps_other_defaults():
    cfg = parse_toll_fraud({"max_concurrent_outbound": 5})
    assert cfg.max_concurrent_outbound == 5
    assert cfg.ext_max_per_hour == 60
    assert cfg.ext_international_per_day == 20


def test_parse_alerts_defaults_all_events_true():
    cfg = parse_alerts(None)
    assert cfg == AlertConfig()
    assert all(cfg.events[k] for k in ALERT_KINDS)


def test_parse_alerts_unknown_event_key_ignored_known_overridden():
    cfg = parse_alerts({"events": {"ip_banned": False, "made_up": True}})
    assert cfg.events["ip_banned"] is False
    assert "made_up" not in cfg.events
    assert cfg.events["toll_blocked"] is True  # yetishmagan -> standart


def test_parse_alerts_chat_ids_tuple():
    cfg = parse_alerts({"chat_ids": ["123", "-456"]})
    assert cfg.chat_ids == ("123", "-456")


def test_to_json_converts_tuples_to_lists():
    j = to_json(SipGuardConfig(trusted_nets=("10.0.0.0/8",)))
    assert j["trusted_nets"] == ["10.0.0.0/8"]
    assert isinstance(j["trusted_nets"], list)


@pytest.mark.parametrize("path,value,expect_err", [
    ("sip_guard.max_failures", 5, False),
    ("sip_guard.max_failures", 2, True),       # < 3
    ("sip_guard.max_failures", 101, True),     # > 100
    ("sip_guard.ban_s", 0, False),              # 0 maxsus ruxsat
    ("toll_fraud.max_concurrent_outbound", 0, False),
    ("toll_fraud.max_concurrent_outbound", 501, True),
    ("toll_fraud.ext_max_per_hour", 1, False),
    ("telegram.dedup_s", 0, False),
    ("telegram.dedup_s", 86_401, True),
])
def test_check_int_boundaries(path, value, expect_err):
    err = check_int(path, value)
    assert (err is not None) == expect_err


def test_check_int_rejects_non_int_and_bool():
    assert check_int("sip_guard.max_failures", "5") is not None
    assert check_int("sip_guard.max_failures", True) is not None  # bool - int EMAS


def test_check_int_zero_not_ok_outside_zero_ok_set():
    # sip_guard.max_failures 0 RUXSAT EMAS (faqat ban_s/toll_fraud maydonlari)
    assert check_int("sip_guard.max_failures", 0) is not None


def test_check_nets_valid_and_invalid():
    assert check_nets(["10.0.0.0/8", "192.168.1.1"]) is None
    assert check_nets(["not-a-net"]) is not None


def test_check_nets_too_many():
    assert check_nets([f"10.0.{i}.0/24" for i in range(51)]) is not None


def test_check_chat_ids_valid_and_invalid():
    assert check_chat_ids(["123", "-456789"]) is None
    assert check_chat_ids(["abc"]) is not None


def test_check_chat_ids_too_many():
    assert check_chat_ids([str(i) for i in range(11)]) is not None


def test_is_trusted_always_trusted_loopback():
    assert is_trusted("127.0.0.1", ()) is True
    assert ALWAYS_TRUSTED == ("127.0.0.0/8",)


def test_is_trusted_custom_net():
    assert is_trusted("10.1.2.3", ("10.0.0.0/8",)) is True
    assert is_trusted("8.8.8.8", ("10.0.0.0/8",)) is False


def test_is_trusted_ignores_bad_net_in_list():
    assert is_trusted("8.8.8.8", ("not-a-net", "10.0.0.0/8")) is False


@pytest.mark.parametrize("ip,lan", [("192.168.1.5", True), ("10.1.2.3", True), ("172.16.0.1", True),
                                    ("172.32.0.1", False), ("fe80::1", True), ("fd00::5", True),
                                    ("8.8.8.8", False), ("2001:4860::8888", False)])
def test_is_lan(ip, lan):
    from app.services.security_config import is_lan
    assert is_lan(ip) is lan


def test_parse_sip_guard_trust_lan_default_and_override():
    from app.services.security_config import parse_sip_guard
    assert parse_sip_guard({}).trust_lan is True
    assert parse_sip_guard({"trust_lan": False}).trust_lan is False
