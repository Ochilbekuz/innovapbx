"""M3b §0/§3 — webhook imzosi, SSRF himoyasi, qayta urinish jadvali, tartib tanlovi (sof funksiyalar)."""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from app.services.integrations import outbox, ssrf, webhook
from app.services.integrations.providers import DeliveryResult

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------ imzo
def test_signature_header_matches_hmac_of_t_dot_body():
    body = b'{"a":1}'
    header = webhook.signature_header("s3cret", body, 1700000000)
    expected = hmac.new(b"s3cret", b"1700000000." + body, hashlib.sha256).hexdigest()
    assert header == f"t=1700000000,v1={expected}"


def test_signature_changes_with_body_and_time():
    a = webhook.signature_header("k", b"x", 1)
    assert a != webhook.signature_header("k", b"y", 1)
    assert a != webhook.signature_header("k", b"x", 2)
    assert a != webhook.signature_header("k2", b"x", 1)


def test_request_headers_contain_event_delivery_signature():
    headers = webhook.request_headers("k", b"{}", event_type="call.ended", delivery_id="d-1", now_unix=5)
    assert headers["X-Innova-Event"] == "call.ended"
    assert headers["X-Innova-Delivery"] == "d-1"
    assert headers["X-Innova-Signature"].startswith("t=5,v1=")
    assert headers["Content-Type"] == "application/json"


def test_classify_response():
    assert webhook.classify_response(200, {}, "ok").ok
    assert webhook.classify_response(204, {}, "").ok
    r = webhook.classify_response(500, {}, "x" * 5000)
    assert not r.ok and r.status_code == 500 and len(r.response_body) == 1024 and r.retry_after_s is None
    assert webhook.classify_response(429, {"retry-after": "7"}, "").retry_after_s == 7
    assert webhook.classify_response(429, {}, "").retry_after_s == 60
    assert webhook.classify_response(429, {"retry-after": "junk"}, "").retry_after_s == 60
    assert webhook.classify_response(301, {"location": "http://x"}, "").ok is False


def test_mask_secret_in_error():
    assert webhook.mask_secret("boom abc123 boom", "abc123") == "boom *** boom"
    assert webhook.mask_secret("boom", "") == "boom"
    assert len(webhook.mask_secret("e" * 900, "zz")) == 500


# ------------------------------------------------------------ SSRF
@pytest.mark.parametrize("ip", [
    "127.0.0.1", "127.8.8.8", "::1", "0.0.0.0", "::", "169.254.169.254", "169.254.1.1",
    "fe80::1", "fd00:ec2::254", "224.0.0.1", "255.255.255.255",
])
def test_forbidden_ips(ip):
    assert ssrf.is_forbidden_ip(ip, frozenset())


@pytest.mark.parametrize("ip", ["10.1.2.3", "172.16.5.5", "192.168.1.10", "8.8.8.8", "2a00:1450::1"])
def test_allowed_ips(ip):
    assert not ssrf.is_forbidden_ip(ip, frozenset())


def test_own_service_ip_forbidden():
    assert ssrf.is_forbidden_ip("172.21.0.3", frozenset({"172.21.0.3"}))
    assert not ssrf.is_forbidden_ip("172.21.0.210", frozenset({"172.21.0.3"}))


def _resolver(mapping):
    def resolve(host):
        if host not in mapping:
            raise OSError("nx")
        return mapping[host]
    return resolve


def test_check_url_ok_and_reasons():
    resolve = _resolver({"hook.lan": ["192.168.1.5"], "evil": ["127.0.0.1"], "two": ["8.8.8.8", "10.0.0.1"]})
    ssrf.check_url("http://hook.lan:8080/x", resolve=resolve, own_ips=frozenset(), blocked_hosts=frozenset())
    ssrf.check_url("https://two/x", resolve=resolve, own_ips=frozenset(), blocked_hosts=frozenset())
    cases = {
        "ftp://hook.lan/": "scheme",
        "http:///nohost": "host",
        "http://evil/": "address",
        "http://api:8000/x": "host",
        "http://API./x": "host",
        "http://unknown/": "resolve",
        "http://[::1]/": "address",
        "http://user:pw@hook.lan/": "credentials",
    }
    for url, reason in cases.items():
        with pytest.raises(ssrf.UrlForbidden) as exc:
            ssrf.check_url(url, resolve=resolve, own_ips=frozenset(), blocked_hosts=frozenset({"api"}))
        assert exc.value.reason == reason, url


def test_check_url_rejects_if_any_resolved_ip_is_forbidden():
    resolve = _resolver({"mixed": ["8.8.8.8", "169.254.169.254"]})
    with pytest.raises(ssrf.UrlForbidden):
        ssrf.check_url("http://mixed/", resolve=resolve, own_ips=frozenset(), blocked_hosts=frozenset())


def test_own_ips_resolves_hosts_and_ignores_failures():
    resolve = _resolver({"api": ["172.21.0.3"], "postgres": ["172.21.0.2", "172.21.0.3"]})
    assert ssrf.own_ips(["api", "postgres", "nope"], resolve=resolve) == frozenset({"172.21.0.2", "172.21.0.3"})


# ------------------------------------------------------------ qayta urinish
def test_parse_schedule():
    assert outbox.parse_schedule("30,120, 600") == (30, 120, 600)
    assert outbox.parse_schedule("2,2,2") == (2, 2, 2)
    assert outbox.parse_schedule("") == outbox.DEFAULT_SCHEDULE
    assert outbox.parse_schedule("a,b") == outbox.DEFAULT_SCHEDULE
    assert outbox.parse_schedule("5,-1") == outbox.DEFAULT_SCHEDULE
    assert len(outbox.DEFAULT_SCHEDULE) == 8 and outbox.DEFAULT_SCHEDULE[0] == 30


def test_transition_success():
    t = outbox.transition(DeliveryResult(ok=True, status_code=200), attempts=0, schedule=(2, 2), now=NOW)
    assert (t.status, t.attempts, t.delivered_at) == ("delivered", 1, NOW)


def test_transition_retries_by_schedule_then_dead():
    schedule = (30, 120)
    fail = DeliveryResult(ok=False, status_code=500, error="HTTP 500")
    t1 = outbox.transition(fail, attempts=0, schedule=schedule, now=NOW)
    assert (t1.status, t1.attempts, t1.next_attempt_at) == ("pending", 1, NOW + timedelta(seconds=30))
    t2 = outbox.transition(fail, attempts=1, schedule=schedule, now=NOW)
    assert (t2.status, t2.attempts, t2.next_attempt_at) == ("pending", 2, NOW + timedelta(seconds=120))
    t3 = outbox.transition(fail, attempts=2, schedule=schedule, now=NOW)
    assert (t3.status, t3.attempts) == ("dead", 3)


def test_transition_rate_limit_does_not_consume_attempt():
    t = outbox.transition(DeliveryResult(ok=False, status_code=429, retry_after_s=7), attempts=1,
                          schedule=(2,), now=NOW)
    assert (t.status, t.attempts, t.next_attempt_at) == ("pending", 1, NOW + timedelta(seconds=7))


def test_transition_permanent_is_dead_immediately():
    t = outbox.transition(DeliveryResult(ok=False, error="bad", permanent=True), attempts=0, schedule=(2, 2), now=NOW)
    assert (t.status, t.attempts) == ("dead", 1)


def test_should_disable_after_continuous_failure():
    assert not outbox.should_disable(None, NOW, 86400)
    assert not outbox.should_disable(NOW - timedelta(hours=23), NOW, 86400)
    assert outbox.should_disable(NOW - timedelta(hours=24), NOW, 86400)


# ------------------------------------------------------------ tartib
def _cand(id_, sub, call, seq):
    return outbox.Candidate(id=id_, subscription_id=sub, call_id=call, seq=seq)


def test_pick_deliverable_respects_head_of_line_per_sub_and_call():
    cands = [_cand("b", "s1", "c1", 2), _cand("x", "s2", "c1", 3), _cand("t", "s1", None, 9)]
    heads = {("s1", "c1"): 1, ("s2", "c1"): 3}
    # s1/c1 boshida seq=1 (hali kutilmoqda/qulflangan) — b olinmaydi; s2/c1 boshi x.
    assert outbox.pick_deliverable(cands, heads).id == "x"


def test_pick_deliverable_null_call_never_blocks():
    cands = [_cand("t", "s1", None, 9)]
    assert outbox.pick_deliverable(cands, {}).id == "t"


def test_pick_deliverable_none_when_all_blocked():
    assert outbox.pick_deliverable([_cand("b", "s1", "c1", 2)], {("s1", "c1"): 1}) is None
    assert outbox.pick_deliverable([], {}) is None


def test_wants_event_rules():
    w = outbox.SubscriptionFilter(kind="webhook", events=("call.ended",), include_internal=False)
    assert outbox.wants_event(w, "call.ended", internal=False)
    assert not outbox.wants_event(w, "call.ringing", internal=False)
    assert not outbox.wants_event(w, "call.ended", internal=True)
    wi = outbox.SubscriptionFilter(kind="webhook", events=("call.ended",), include_internal=True)
    assert outbox.wants_event(wi, "call.ended", internal=True)
    crm = outbox.SubscriptionFilter(kind="bitrix24", events=("call.ended",), include_internal=True)
    assert not outbox.wants_event(crm, "call.ended", internal=True)
    assert outbox.wants_event(crm, "call.ended", internal=False)
    assert not outbox.wants_event(w, "test.ping", internal=False)
