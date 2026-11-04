"""`app/netd/firewall.py` — m12-contract.md B3 (firewall GUI). Soxta
`Executor` (xotiradagi fayl tizimi) + soxta soat — HAQIQIY `nft` HECH QACHON
chaqirilmaydi (`run()` soxta natija qaytaradi, host o'zgarmaydi)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.netd.executor import CommandResult, FIREWALL_CONF_PATH
from app.netd.firewall import (
    MAX_ALLOW_ENTRIES,
    MAX_BLOCKED_ENTRIES,
    MAX_TIMEOUT_S,
    MIN_TIMEOUT_S,
    SERVICE_NAMES,
    STATE_PATH,
    FirewallService,
    _ip_in_any_cidr,
    _PendingRecord,
    _Snapshot,
    check_self_lockout,
    config_to_dict,
    default_config,
    diff_summary,
    is_valid_cidr,
    render_nft,
    validate_firewall_config,
)
from app.netd.service import NetdError


class FakeExecutor:
    def __init__(self, files: dict[str, str] | None = None, nft_check_ok: bool = True, nft_apply_ok: bool = True):
        self.files = dict(files or {})
        self.nft_check_ok = nft_check_ok
        self.nft_apply_ok = nft_apply_ok
        self.commands: list[list[str]] = []

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def exists(self, path: str) -> bool:
        return path in self.files

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        self.commands.append(argv)
        if argv[:2] == ["nft", "-c"]:
            return CommandResult(0, "", "") if self.nft_check_ok else CommandResult(1, "", "sintaksis xato")
        if argv[:2] == ["nft", "-f"]:
            return CommandResult(0, "", "") if self.nft_apply_ok else CommandResult(1, "", "qo'llash xato")
        return CommandResult(0, "", "")


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _clock() -> Clock:
    return Clock(datetime(2026, 1, 1, tzinfo=timezone.utc))


def _service(name, mode="all", allow=()):
    return SimpleNamespace(name=name, mode=mode, allow=list(allow))


def _config(services=None, blocked_cidrs=(), timeout_s=120):
    return SimpleNamespace(
        services=services if services is not None else [_service(n) for n in SERVICE_NAMES],
        blocked_cidrs=list(blocked_cidrs), timeout_s=timeout_s,
    )


def _allowlist_config(ssh_allow=("10.0.0.5/32",), web_allow=("10.0.0.5/32",)):
    return _config(services=[
        _service("ssh", "allowlist", ssh_allow), _service("web", "allowlist", web_allow),
        _service("sip", "all"), _service("rtp", "all"),
    ])


def _service_pending(executor, *, timeout_s=120):
    return FirewallService(executor, readonly=False, pending_path="/pending.json", now_fn=_clock())


# ------------------------------------------------------------------ validatsiya

def test_is_valid_cidr_rejects_non_ipv4_and_garbage():
    assert is_valid_cidr("10.0.0.0/24") is True
    assert is_valid_cidr("not-a-cidr") is False
    assert is_valid_cidr("::1/128") is False  # faqat IPv4


def test_is_valid_cidr_rejects_non_string_value():
    assert is_valid_cidr(123) is False
    assert is_valid_cidr(None) is False


def test_ip_in_any_cidr_false_for_unparsable_ip():
    assert _ip_in_any_cidr("not-an-ip", ["10.0.0.0/24"]) is False


def test_pending_record_is_expired_at_exact_boundary_and_before():
    record = _PendingRecord(id="x", applied_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                             expires_at=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
                             summary=[], snapshot=_Snapshot(None, None))
    assert record.is_expired(datetime(2026, 1, 1, 0, 1, 59, tzinfo=timezone.utc)) is False
    assert record.is_expired(datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)) is True  # aynan chegarada
    assert record.is_expired(datetime(2026, 1, 1, 0, 2, 1, tzinfo=timezone.utc)) is True


def test_validate_firewall_config_requires_all_four_services():
    result = validate_firewall_config(_config(services=[_service("ssh")]))
    assert not result.ok
    missing_fields = {e.field for e in result.errors}
    assert "services" in missing_fields


def test_validate_firewall_config_rejects_unknown_service_name():
    result = validate_firewall_config(_config(services=[_service("telnet")]))
    assert not result.ok


def test_validate_firewall_config_rejects_duplicate_service_name():
    result = validate_firewall_config(_config(services=[_service("ssh"), _service("ssh")]))
    assert not result.ok


def test_validate_firewall_config_allowlist_requires_at_least_one_cidr():
    result = validate_firewall_config(_config(services=[_service("ssh", "allowlist", [])]))
    assert not result.ok
    assert result.errors[0].field == "services[0].allow"


def test_validate_firewall_config_allowlist_with_none_allow_is_treated_as_empty():
    svc = SimpleNamespace(name="ssh", mode="allowlist", allow=None)
    result = validate_firewall_config(_config(services=[svc]))
    assert result.errors[0].field == "services[0].allow"


def test_validate_firewall_config_rejects_invalid_cidr_in_allowlist():
    result = validate_firewall_config(_config(services=[_service("ssh", "allowlist", ["not-a-cidr"])]))
    assert not result.ok


def test_validate_firewall_config_reports_only_the_invalid_cidr_among_valid_ones():
    result = validate_firewall_config(
        _config(services=[_service("ssh", "allowlist", ["10.0.0.5/32", "not-a-cidr", "10.0.0.6/32"])]))
    allow_errors = [e for e in result.errors if e.field.startswith("services[0].allow[")]
    assert [e.field for e in allow_errors] == ["services[0].allow[1]"]


def test_validate_firewall_config_allow_list_boundary_at_max_entries():
    exactly_max = [f"10.0.{i // 256}.{i % 256}/32" for i in range(MAX_ALLOW_ENTRIES)]
    result = validate_firewall_config(_config(services=[_service("ssh", "allowlist", exactly_max)]))
    assert not any(e.field == "services[0].allow" for e in result.errors)

    too_many = exactly_max + ["10.255.255.254/32"]
    result = validate_firewall_config(_config(services=[_service("ssh", "allowlist", too_many)]))
    assert any(e.field == "services[0].allow" for e in result.errors)


def test_validate_firewall_config_blocked_cidrs_boundary_at_max_entries():
    exactly_max = [f"10.{i // 256}.{i % 256}.0/24" for i in range(MAX_BLOCKED_ENTRIES)]
    result = validate_firewall_config(_config(blocked_cidrs=exactly_max))
    assert not any(e.field == "blocked_cidrs" for e in result.errors)

    too_many = exactly_max + ["11.0.0.0/24"]
    result = validate_firewall_config(_config(blocked_cidrs=too_many))
    assert any(e.field == "blocked_cidrs" for e in result.errors)


def test_validate_firewall_config_timeout_boundaries_are_inclusive():
    assert not any(e.field == "timeout_s" for e in validate_firewall_config(_config(timeout_s=MIN_TIMEOUT_S)).errors)
    assert not any(e.field == "timeout_s" for e in validate_firewall_config(_config(timeout_s=MAX_TIMEOUT_S)).errors)
    assert any(e.field == "timeout_s" for e in validate_firewall_config(_config(timeout_s=MIN_TIMEOUT_S - 1)).errors)
    assert any(e.field == "timeout_s" for e in validate_firewall_config(_config(timeout_s=MAX_TIMEOUT_S + 1)).errors)


def test_validate_firewall_config_rejects_blocking_everything():
    result = validate_firewall_config(_config(blocked_cidrs=["0.0.0.0/0"]))
    assert not result.ok
    assert result.errors[0].field == "blocked_cidrs[0]"


def test_validate_firewall_config_rejects_timeout_out_of_range():
    result = validate_firewall_config(_config(timeout_s=10))
    assert not result.ok
    assert result.errors[0].field == "timeout_s"


def test_validate_firewall_config_ok_for_default():
    assert validate_firewall_config(_config()).ok


# ------------------------------------------------------------------ config_to_dict / diff_summary

def test_config_to_dict_treats_none_allow_and_blocked_cidrs_as_empty_list():
    cfg = _config(services=[_service("ssh", "all", []), *[_service(n) for n in SERVICE_NAMES if n != "ssh"]])
    cfg.services[0].allow = None
    cfg.blocked_cidrs = None
    as_dict = config_to_dict(cfg)
    assert as_dict["services"][0]["allow"] == []
    assert as_dict["blocked_cidrs"] == []


def test_diff_summary_reports_mode_change_to_all_and_to_allowlist_with_exact_cidr_count():
    old = config_to_dict(_allowlist_config(ssh_allow=["10.0.0.5/32"]))
    lines = diff_summary(old, _config(services=[
        _service("ssh", "all"), _service("web", "allowlist", ["10.0.0.9/32", "10.0.0.10/32"]),
        _service("sip", "all"), _service("rtp", "all"),
    ]))
    assert "ssh: hammaga ochiq bo'ladi" in lines
    assert "web: faqat 2 ta CIDR uchun ochiq bo'ladi" in lines  # aynan sanoq (mutator: `svc.allow or []`)


def test_diff_summary_empty_when_nothing_changed():
    cfg = _config()
    old = config_to_dict(cfg)
    assert diff_summary(old, cfg) == []


def test_diff_summary_empty_when_allowlist_unchanged_with_non_empty_allow():
    # prev va yangi allow ikkisi ham BO'SH EMAS va TENG — `or` -> `and` mutatsiyasi
    # (ikki tomondagi ro'yxatni ham noto'g'ri bo'shatib qo'yardi) ushbu holatda aniqlanadi.
    cfg = _allowlist_config(ssh_allow=["10.0.0.5/32"], web_allow=["10.0.0.5/32"])
    old = config_to_dict(cfg)
    assert diff_summary(old, cfg) == []


def test_diff_summary_reports_blocked_cidrs_change_with_exact_count():
    old = config_to_dict(_config())
    lines = diff_summary(old, _config(blocked_cidrs=["1.2.3.4/32", "5.6.7.8/32"]))
    assert "bloklangan CIDR ro'yxati o'zgaradi (2 ta)" in lines  # aynan sanoq


def test_diff_summary_empty_when_blocked_cidrs_unchanged_and_non_empty():
    cfg = _config(blocked_cidrs=["1.2.3.4/32"])
    old = config_to_dict(cfg)
    assert diff_summary(old, cfg) == []


# ------------------------------------------------------------------ o'zini qulflashdan himoya

def test_check_self_lockout_flags_admin_ip_missing_from_ssh_allowlist():
    errors = []
    check_self_lockout(_allowlist_config(ssh_allow=["10.0.0.9/32"]), "10.0.0.5", errors)
    assert any(e.field == "services.ssh.allow" for e in errors)


def test_check_self_lockout_passes_when_admin_ip_in_allowlist():
    errors = []
    check_self_lockout(_allowlist_config(ssh_allow=["10.0.0.5/32"], web_allow=["10.0.0.5/32"]), "10.0.0.5", errors)
    assert errors == []


def test_check_self_lockout_flags_admin_ip_in_blocked_cidrs():
    errors = []
    check_self_lockout(_config(blocked_cidrs=["10.0.0.0/24"]), "10.0.0.5", errors)
    assert any(e.field == "blocked_cidrs" for e in errors)


def test_check_self_lockout_skipped_when_request_host_unknown_or_ipv6():
    errors = []
    check_self_lockout(_allowlist_config(ssh_allow=["10.0.0.9/32"]), None, errors)
    check_self_lockout(_allowlist_config(ssh_allow=["10.0.0.9/32"]), "::1", errors)
    assert errors == []


def test_check_self_lockout_ignores_services_not_in_allowlist_mode():
    errors = []
    check_self_lockout(_config(), "10.0.0.5", errors)  # bariga "all"
    assert errors == []


# ------------------------------------------------------------------ render

def test_render_nft_uses_independent_table_name():
    rendered = render_nft(default_config())
    assert rendered.startswith("table inet innova_fw {")
    assert "table inet innova {" not in rendered


def test_render_nft_drops_blocked_cidrs_first():
    rendered = render_nft(_config(blocked_cidrs=["1.2.3.4/32"]))
    assert "ip saddr { 1.2.3.4/32 } drop" in rendered


def test_render_nft_allowlist_mode_drops_everything_outside_allow():
    rendered = render_nft(_allowlist_config(ssh_allow=["10.0.0.5/32"]))
    assert "ip saddr != { 10.0.0.5/32 } tcp dport { 22 } drop" in rendered


def test_render_nft_all_mode_service_has_no_drop_rule():
    rendered = render_nft(default_config())
    assert "dport { 22 } drop" not in rendered  # hammasi "all" rejimida


# ------------------------------------------------------------------ FirewallService

@pytest.mark.asyncio
async def test_state_reports_default_config_when_nothing_applied_yet():
    service = _service_pending(FakeExecutor())
    state = await service.state()
    assert {s["name"] for s in state["services"]} == set(SERVICE_NAMES)
    assert state["pending"] is None
    assert state["readonly_reason"] is None


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_load_state_dict_returns_default_when_raw_missing_empty_or_blank(raw):
    executor = FakeExecutor({STATE_PATH: raw} if raw is not None else {})
    service = _service_pending(executor)
    assert service._load_state_dict() == config_to_dict(default_config())


def test_load_state_dict_returns_parsed_json_when_present():
    saved = config_to_dict(_allowlist_config())
    executor = FakeExecutor({STATE_PATH: json.dumps(saved)})
    service = _service_pending(executor)
    assert service._load_state_dict() == saved


@pytest.mark.asyncio
async def test_state_readonly_reason_set_when_readonly():
    service = FirewallService(FakeExecutor(), readonly=True, pending_path="/pending.json", now_fn=_clock())
    state = await service.state()
    assert state["readonly_reason"]


@pytest.mark.asyncio
async def test_validate_ok_for_default_config():
    service = _service_pending(FakeExecutor())
    result = await service.validate(_config())
    assert result == {"ok": True, "errors": [], "warnings": [], "diff": []}


@pytest.mark.asyncio
async def test_validate_reports_errors_and_self_lockout_without_writing():
    executor = FakeExecutor()
    service = _service_pending(executor)
    cfg = _allowlist_config(ssh_allow=["10.0.0.9/32"])
    result = await service.validate(cfg, request_host="10.0.0.5")
    assert result["ok"] is False
    assert any(e["field"] == "services.ssh.allow" for e in result["errors"])
    assert executor.commands == []


@pytest.mark.asyncio
async def test_apply_readonly_raises_without_writing():
    executor = FakeExecutor()
    service = FirewallService(executor, readonly=True, pending_path="/pending.json", now_fn=_clock())
    with pytest.raises(NetdError) as exc:
        await service.apply(_config())
    assert exc.value.code == "readonly"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_apply_invalid_config_raises_without_touching_nft():
    executor = FakeExecutor()
    service = _service_pending(executor)
    with pytest.raises(NetdError) as exc:
        await service.apply(_config(services=[_service("ssh")]))
    assert exc.value.code == "invalid_config"
    assert executor.commands == []


@pytest.mark.asyncio
async def test_apply_self_lockout_raises_422_equivalent_invalid_config():
    executor = FakeExecutor()
    service = _service_pending(executor)
    cfg = _allowlist_config(ssh_allow=["10.0.0.9/32"])
    with pytest.raises(NetdError) as exc:
        await service.apply(cfg, request_host="10.0.0.5")
    assert exc.value.code == "invalid_config"
    assert any(f["field"] == "services.ssh.allow" for f in exc.value.fields)


@pytest.mark.asyncio
async def test_apply_writes_nft_conf_runs_check_then_apply_and_opens_pending():
    executor = FakeExecutor()
    service = _service_pending(executor)
    result = await service.apply(_config(blocked_cidrs=["1.2.3.4/32"]))
    assert executor.commands == [
        ["nft", "-c", "-f", FIREWALL_CONF_PATH],
        ["nft", "-f", FIREWALL_CONF_PATH],
    ]
    assert "1.2.3.4/32" in executor.files[FIREWALL_CONF_PATH]
    assert result["pending"] is not None


@pytest.mark.asyncio
async def test_apply_twice_without_confirm_raises_pending_exists_409():
    executor = FakeExecutor()
    service = _service_pending(executor)
    await service.apply(_config())
    with pytest.raises(NetdError) as exc:
        await service.apply(_config(blocked_cidrs=["1.2.3.4/32"]))
    assert exc.value.code == "pending_exists"


@pytest.mark.asyncio
async def test_apply_rolls_back_conf_file_when_nft_check_fails():
    executor = FakeExecutor(files={FIREWALL_CONF_PATH: "OLD\n"}, nft_check_ok=False)
    service = _service_pending(executor)
    with pytest.raises(NetdError) as exc:
        await service.apply(_config())
    assert exc.value.code == "invalid_config"
    assert executor.files[FIREWALL_CONF_PATH] == "OLD\n"  # eski holatga qaytarilgan


@pytest.mark.asyncio
async def test_apply_reapplies_old_conf_when_nft_apply_fails():
    executor = FakeExecutor(files={FIREWALL_CONF_PATH: "OLD\n"}, nft_apply_ok=False)
    service = _service_pending(executor)
    with pytest.raises(NetdError) as exc:
        await service.apply(_config())
    assert exc.value.code == "apply_failed"
    assert executor.files[FIREWALL_CONF_PATH] == "OLD\n"
    assert executor.commands[-1] == ["nft", "-f", FIREWALL_CONF_PATH]  # eski conf bilan qayta qo'llangan


@pytest.mark.asyncio
async def test_confirm_clears_pending_and_keeps_new_conf():
    executor = FakeExecutor()
    service = _service_pending(executor)
    applied = await service.apply(_config(blocked_cidrs=["1.2.3.4/32"]))
    pending_id = applied["pending"]["id"]
    result = await service.confirm(pending_id)
    assert result["pending"] is None
    assert result["last_result"]["kind"] == "confirmed"
    assert "1.2.3.4/32" in executor.files[FIREWALL_CONF_PATH]


@pytest.mark.asyncio
async def test_confirm_unknown_pending_id_raises_not_found():
    service = _service_pending(FakeExecutor())
    with pytest.raises(NetdError) as exc:
        await service.confirm("ghost")
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_rollback_restores_old_conf_and_state():
    executor = FakeExecutor(files={FIREWALL_CONF_PATH: "OLD\n"})
    service = _service_pending(executor)
    applied = await service.apply(_config(blocked_cidrs=["1.2.3.4/32"]))
    pending_id = applied["pending"]["id"]
    result = await service.rollback(pending_id)
    assert result["pending"] is None
    assert result["last_result"]["kind"] == "rolled_back"
    assert executor.files[FIREWALL_CONF_PATH] == "OLD\n"


@pytest.mark.asyncio
async def test_pending_auto_expires_and_rolls_back_on_next_state_call():
    clock = _clock()
    executor = FakeExecutor(files={FIREWALL_CONF_PATH: "OLD\n"})
    service = FirewallService(executor, readonly=False, pending_path="/pending.json", now_fn=clock)
    await service.apply(_config(blocked_cidrs=["1.2.3.4/32"], timeout_s=60))
    clock.advance(61)
    state = await service.state()
    assert state["pending"] is None
    assert state["last_result"]["message"] == "Vaqt tugadi — firewall avtomatik qaytarildi"
    assert executor.files[FIREWALL_CONF_PATH] == "OLD\n"


@pytest.mark.asyncio
async def test_startup_recover_rolls_back_pending_loaded_from_disk():
    import json

    pending_json = json.dumps({
        "id": "p9", "applied_at": "2026-01-01T00:00:00+00:00", "expires_at": "2026-01-01T01:00:00+00:00",
        "summary": [], "snapshot": {"conf_text": "OLD\n", "state_json": None},
    })
    executor = FakeExecutor(files={"/pending.json": pending_json, FIREWALL_CONF_PATH: "NEW\n"})
    service = FirewallService(executor, readonly=False, pending_path="/pending.json", now_fn=_clock())
    assert service.pending is not None
    await service.startup_recover()
    assert service.pending is None
    assert executor.files[FIREWALL_CONF_PATH] == "OLD\n"
