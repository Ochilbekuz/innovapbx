"""M5a apply — sof qismlar: reja eskirishi/yakuniy qaror, CSV hisobot, sinov ilgagi,
ffmpeg bayroqlari, xato xabarini tozalash, yozuvchi yordamchilari (DB'siz)."""
from __future__ import annotations

import asyncio
import csv
import io
from datetime import time
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.schemas import UpdateTrunkPayload
from app.services.apply import ApplyResult
from app.services.fpbx import apply_job, bundle
from app.services.fpbx import plan as plan_mod
from app.services.fpbx.apply_plan import (
    REPORT_COLUMNS,
    PlanStaleError,
    build_report_csv,
    csv_cell,
    decide,
    item_result,
    resolve_final_actions,
)
from app.services.fpbx.mappers import Entry
from app.services.fpbx.mappers.trunk import map_trunk
from app.services.fpbx.writers import TestFailError, maybe_test_fail
from app.services.fpbx.writers.endpoints import _sip_secret, trunk_host
from app.services.fpbx.writers.context import WriteCtx, clamp, dashed, entry_key, matches, pick
from app.services.fpbx.writers.schedule import split_range
from tests.test_fpbx_plan import FIXTURE, SECRET_NEEDLES, _NoConflictSession


def _entry(action: str = "create", reason: str | None = None, **kw) -> Entry:
    base = {"kind": "extension", "source_ref": "users:101", "name": "Ali", "number": "101"}
    return Entry(**{**base, **kw}, action=action, reason=reason)


def _stored(entry: Entry, action: str, reason: str | None = None) -> dict:
    return {**entry.public_dict(), "action": action, "reason": reason}


# ------------------------------------------------------------------ decide / eskirish
@pytest.mark.parametrize(("fresh", "fresh_reason", "stored", "write", "note"), [
    ("create", None, "create", True, None),
    ("skip", "default_moh", "skip", False, None),
    ("create", None, "skip", False, None),
    ("conflict", "number_taken", "skip", False, None),
    ("conflict", "number_taken", "replace", False, "replace_unsupported"),
    ("skip", "default_moh", "create", True, None),
    ("skip", "already_imported", "create", False, "already_imported"),
    ("unsupported", "x", "unsupported", False, None),
])
def test_decide_allowed(fresh, fresh_reason, stored, write, note) -> None:
    entry = _entry(fresh, fresh_reason)
    decision = decide(entry, _stored(entry, stored, fresh_reason if stored == fresh else None))
    assert (decision.action, decision.write, decision.note) == (stored, write, note)
    assert decision.entry is entry


@pytest.mark.parametrize(("fresh", "stored"), [
    ("create", "conflict"), ("skip", "conflict"), ("conflict", "create"), ("create", "replace"),
    ("unsupported", "create"),
])
def test_decide_stale_action(fresh, stored) -> None:
    entry = _entry(fresh)
    with pytest.raises(PlanStaleError, match=f"{fresh} -> {stored}"):
        decide(entry, _stored(entry, stored))


def test_decide_stale_reason_and_fields() -> None:
    entry = _entry("skip", "already_imported")
    with pytest.raises(PlanStaleError, match="sabab"):
        decide(entry, _stored(entry, "skip", "default_moh"))
    with pytest.raises(PlanStaleError, match="maydon"):
        decide(entry, {**_stored(entry, "skip", "already_imported"), "name": "Boshqa"})
    assert PlanStaleError.code == "plan_stale"


def test_resolve_final_actions_set_mismatch() -> None:
    a, b = _entry(), _entry(source_ref="users:102", number="102")
    assert [d.entry for d in resolve_final_actions([_stored(b, "create"), _stored(a, "create")], [a, b])] == [a, b]
    with pytest.raises(PlanStaleError, match="to'plami"):
        resolve_final_actions([_stored(a, "create")], [a, b])
    with pytest.raises(PlanStaleError):
        resolve_final_actions([_stored(a, "create"), _stored(b, "create")], [a])


# ------------------------------------------------------------------ CSV
@pytest.mark.parametrize(("value", "out"), [
    (None, ""), ("Ali", "Ali"), ("=1+2", "'=1+2"), ("@x", "'@x"), ("+998901112233", "+998901112233"),
    ("-5", "-5"), ("-cmd", "'-cmd"), ("\tx", "'\tx"), (101, "101"),
])
def test_csv_cell(value, out) -> None:
    assert csv_cell(value) == out


def test_item_result_variants() -> None:
    item = {"kind": "extension", "source_ref": "users:101", "action": "create", "reason": None}
    created = {"extension:users:101": "id1"}
    assert item_result(item, created=created, result=None, applied=True) == ("created", None)
    rotated = {"rotated": ["users:101"]}
    assert item_result(item, created=created, result=rotated, applied=True) == ("created;rotated", None)
    assert item_result(item, created={}, result=None, applied=False) == ("not_applied", None)
    skipped = {"not_created": {"extension:users:101": "holiday_exists"}}
    assert item_result(item, created={}, result=skipped, applied=True) == ("skipped", "holiday_exists")
    unsup = {**item, "action": "unsupported", "reason": "custom"}
    assert item_result(unsup, created={}, result=None, applied=True) == ("unsupported", "custom")
    assert item_result({**item, "action": "skip", "reason": "builtin"}, created={}, result={},
                       applied=True) == ("skipped", "builtin")


def test_build_report_csv() -> None:
    items = [{"kind": "extension", "source_ref": "users:101", "name": "=Ali", "number": "101",
              "action": "create", "reason": None},
             {"kind": "blacklist", "source_ref": "blacklist:1", "name": "b", "number": None,
              "action": "skip", "reason": "exists"}]
    body = build_report_csv(items, created={"extension:users:101": "uuid-1"}, result={"rotated": []}, applied=True)
    rows = list(csv.reader(io.StringIO(body)))
    assert tuple(rows[0]) == REPORT_COLUMNS
    assert rows[1] == ["extension", "users:101", "'=Ali", "101", "create", "", "created", "uuid-1"]
    assert rows[2] == ["blacklist", "blacklist:1", "b", "", "skip", "exists", "skipped", ""]


# ------------------------------------------------------------------ apply_job yordamchilari
def test_maybe_test_fail(monkeypatch) -> None:
    monkeypatch.setenv("INNOVA_TEST_FAIL_AT", "routes")
    maybe_test_fail("audio")
    with pytest.raises(TestFailError, match="routes") as info:
        maybe_test_fail("routes")
    assert info.value.code == "test_fail"
    monkeypatch.setenv("INNOVA_TEST_FAIL_AT", " audio ")
    with pytest.raises(TestFailError):
        maybe_test_fail("audio")
    monkeypatch.delenv("INNOVA_TEST_FAIL_AT")
    maybe_test_fail("routes")


@pytest.mark.parametrize(("name", "args"), [
    ("a.ulaw", ("-f", "mulaw", "-ar", "8000", "-ac", "1")), ("a.ALAW", ("-f", "alaw", "-ar", "8000", "-ac", "1")),
    ("a.sln16", ("-f", "s16le", "-ar", "16000", "-ac", "1")), ("a.sln48", ("-f", "s16le", "-ar", "48000", "-ac", "1")),
    ("a.raw", ("-f", "s16le", "-ar", "8000", "-ac", "1")), ("a.gsm", ("-f", "gsm")), ("a.g722", ("-f", "g722")),
    ("a.wav", ()), ("a.mp3", ()),
])
def test_ffmpeg_input_args(name, args) -> None:
    assert apply_job.ffmpeg_input_args(Path(name)) == args


def test_error_of_sanitizes() -> None:
    class _Orig(Exception):
        pass

    db_exc = IntegrityError("INSERT ... secret", {"p": "SinovSecret101!"},
                            _Orig("duplicate key value\nDETAIL: Key (x)=(SinovSecret101!)"))
    assert apply_job.error_of(db_exc) == {"code": "apply_failed", "message": "duplicate key value"}
    assert apply_job.error_of(TestFailError("t")) == {"code": "test_fail", "message": "t"}
    assert apply_job.error_of(apply_job.ApplyError("backup_failed", "b"))["code"] == "backup_failed"
    assert apply_job.error_of(KeyError())["message"] == "KeyError"
    assert len(apply_job.error_of(ValueError("x" * 900))["message"]) == 500


def test_unlink(tmp_path) -> None:
    files = [tmp_path / "a.wav", tmp_path / "missing.wav"]
    files[0].write_bytes(b"x")
    apply_job._unlink(files)
    assert not files[0].exists()


# ------------------------------------------------------------------ yozuvchi yordamchilari
@pytest.mark.parametrize(("start", "end", "parts"), [
    (time(9), time(18), [(time(9), time(18))]),
    (time(22), time(6), [(time(22), time(23, 59, 59)), (time(0), time(6))]),
    (time(22), time(0), [(time(22), time(23, 59, 59))]),
    (time(23, 59, 59), time(6), [(time(0), time(6))]),
])
def test_split_range(start, end, parts) -> None:
    assert split_range(start, end) == parts


def test_small_helpers() -> None:
    assert clamp(None, 1, 10, 3) == 3
    assert clamp(True, 1, 10, 3) == 3
    assert clamp(50, 1, 10, 3) == 10
    assert clamp(0, 1, 10, 3) == 1
    assert clamp(10, 1, 10, 3) == 10
    assert clamp(500, 0, None, 3) == 500
    assert pick("hunt", {"hunt"}, "ringall") == "hunt"
    assert pick("x", {"hunt"}, "ringall") == "ringall"
    assert matches(r"[0-9]{2}", "12") and not matches(r"[0-9]{2}", "123") and not matches(r"x", None)
    assert dashed("a" * 40, 2) == "a" * 32
    assert dashed("moh", 2) == "moh-2"
    assert entry_key(_entry()) == "extension:users:101"
    ctx = WriteCtx(session=None, tenant_id="t", tenant_code="t1", job_id="j", bundle_dir=Path("."),
                   sounds_dir=Path("."))
    ctx.warn("users:1", "c", "m")
    assert ctx.warnings == [{"code": "c", "message": "m", "source_ref": "users:1"}]


# ------------------------------------------------------------------ to'plam (navbat a'zolari)
@pytest.fixture(scope="module")
def analysis(tmp_path_factory):
    dest = tmp_path_factory.mktemp("fpbx-apply-unit")
    bundle.extract_bundle(FIXTURE, dest, max_total_bytes=20 * 1024 * 1024 * 1024)
    return asyncio.run(plan_mod.analyze(bundle.find_bundle_root(dest), _NoConflictSession(), "t1"))


def test_queue_members_parsed_from_local_channel(analysis) -> None:
    queue = next(e for e in analysis.items if e.kind == "queue")
    members = sorted((m["extension_number"], bool(m.get("dynamic"))) for m in queue.payload["members"])
    assert members == [("101", False), ("102", False), ("103", True)]


def test_plan_matches_itself_and_public_has_no_secrets(analysis) -> None:
    stored = [e.public_dict() for e in analysis.items]
    decisions = resolve_final_actions(stored, analysis.items)
    assert sum(d.write for d in decisions) == sum(e.action == "create" for e in analysis.items)
    text = repr(stored)
    assert not any(needle in text for needle in SECRET_NEEDLES)


@pytest.mark.parametrize(("rotate", "weak", "rotated"), [(True, True, True), (True, False, False), (False, True, False)])
def test_sip_secret_rotation(rotate, weak, rotated) -> None:
    ctx = WriteCtx(session=None, tenant_id="t", tenant_code="t1", job_id="j", bundle_dir=Path("."),
                   sounds_dir=Path("."), rotate_weak=rotate)
    entry = _entry(payload={"secret_plain": "101"})
    entry.weak_secret = weak
    secret = _sip_secret(ctx, entry)
    assert (secret != "101") is rotated
    assert ctx.rotated == (["users:101"] if rotated else [])
    assert len(_sip_secret(ctx, _entry(payload={}))) >= 12


# ------------------------------------------------------------------ apply_job: tashqi qadamlar (soxta)
class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.parametrize(("outcome", "expected"), [
    (ApplyResult("applied", 7, None), "7"),
    (ApplyResult("unchanged", 3, None), "3"),
    (ApplyResult("unchanged", None, None), None),
])
def test_apply_dialplan_ok(monkeypatch, outcome, expected) -> None:
    async def fake(session, **kw):
        assert kw == {"tenant_id": "t", "user_id": "u", "ami": "ami"}
        return outcome

    monkeypatch.setattr(apply_job, "apply_config", fake)
    assert asyncio.run(apply_job._apply_dialplan(None, "t", "u", "ami")) == expected


@pytest.mark.parametrize(("outcome", "code", "message"), [
    (ApplyResult("rolled_back", 2, "reload xato"), "apply_failed", "reload xato"),
    (ApplyResult("rolled_back", 2, None), "apply_failed", "Dialplan qo'llanmadi"),
    (ApiError(422, "compile_error", "kompilyatsiya"), "compile_error", "kompilyatsiya"),
])
def test_apply_dialplan_failures(monkeypatch, outcome, code, message) -> None:
    async def fake(session, **kw):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(apply_job, "apply_config", fake)
    with pytest.raises(apply_job.ApplyError) as info:
        asyncio.run(apply_job._apply_dialplan(None, "t", None, None))
    assert (info.value.code, info.value.message) == (code, message)


def _post_ctx(**created: int) -> WriteCtx:
    ctx = WriteCtx(session=None, tenant_id="t", tenant_code="t1", job_id="j", bundle_dir=Path("."),
                   sounds_dir=Path("."))
    ctx.created.update(created)
    return ctx


def test_post_apply_problems(monkeypatch) -> None:
    calls: list[str] = []

    def fn(kind: str, fail: bool):
        async def run(session, *, tenant_id, tenant_code, ami):
            calls.append(f"{kind}:{tenant_id}:{tenant_code}:{ami}")
            if fail:
                raise RuntimeError("SirliMatn")
        return run

    monkeypatch.setattr(apply_job, "_POST_APPLY", (("moh", fn("moh", True)), ("voicemail", fn("voicemail", False)),
                                                   ("conference", fn("conference", True))))
    reloads: list[bool] = []

    async def reload(ami):
        reloads.append(ami)
        return False

    monkeypatch.setattr(apply_job, "_safe_reload", reload)
    session = _FakeSession()
    problems = asyncio.run(apply_job._post_apply_problems(session, _post_ctx(moh=1, voicemail=2, trunk=1), "a"))
    assert calls == ["moh:t:t1:a", "voicemail:t:t1:a"]
    assert problems == [{"code": "moh_apply_failed", "message": "RuntimeError", "source_ref": None},
                        {"code": "pjsip_reload_failed", "message": "pjsip reload", "source_ref": None}]
    assert asyncio.run(apply_job._post_apply_problems(session, _post_ctx(conference=0), "a")) == []
    assert reloads == ["a"]


def test_with_problems_appends_warnings() -> None:
    result = {"warnings": 2, "warning_items": [{"code": "a"}], "created": {"moh": 1}}
    assert apply_job.with_problems(result, []) == result
    merged = apply_job.with_problems(result, [{"code": "x"}])
    assert merged == {"warnings": 3, "warning_items": [{"code": "a"}, {"code": "x"}], "created": {"moh": 1}}
    assert result["warnings"] == 2 and len(result["warning_items"]) == 1  # asl o'zgarmaydi


@pytest.mark.parametrize(("reload", "ok"), [(lambda: True, True), (lambda: None, False), (lambda: 1 / 0, False)])
def test_safe_reload(monkeypatch, reload, ok) -> None:
    async def fake(ami):
        return reload()

    monkeypatch.setattr(apply_job, "reload_pjsip", fake)
    assert asyncio.run(apply_job._safe_reload(None)) is ok


class _Backup:
    def __init__(self, status: str) -> None:
        self.id, self.status = "b1", status


@pytest.mark.parametrize("status", ["ok", "failed"])
def test_pre_import_backup(monkeypatch, status) -> None:
    seen: dict = {}

    backup = _Backup("pending")

    async def record(session, **kw):
        seen.update(kw)
        return backup

    async def run(session, backup_id, tenant_id):
        seen["run"] = (backup_id, tenant_id)
        backup.status = status

    monkeypatch.setattr(apply_job.backup_job, "create_backup_record", record)
    monkeypatch.setattr(apply_job.backup_job, "_run_backup_job", run)
    session = _FakeSession()
    if status == "ok":
        assert asyncio.run(apply_job._pre_import_backup(session, "t")) == "b1"
    else:
        with pytest.raises(apply_job.ApplyError, match="pre_import") as info:
            asyncio.run(apply_job._pre_import_backup(session, "t"))
        assert info.value.code == "backup_failed"
    assert (seen["tenant_id"], seen["kind"], seen["created_by"], seen["run"]) == ("t", "pre_import", None, ("b1", "t"))
    assert seen["components"] and session.commits == 1


def test_pre_import_backup_needs_passphrase(monkeypatch) -> None:
    async def record(session, **kw):
        raise apply_job.backup_job.PassphraseRequiredError()

    monkeypatch.setattr(apply_job.backup_job, "create_backup_record", record)
    session = _FakeSession()
    with pytest.raises(apply_job.ApplyError) as info:
        asyncio.run(apply_job._pre_import_backup(session, "t"))
    assert (info.value.code, session.commits) == ("passphrase_required", 0)


@pytest.mark.parametrize(("payload", "host"), [
    ({"auth_mode": "ip", "host": None, "match_ips": ["203.0.113.10/32"]}, "203.0.113.10"),
    ({"auth_mode": "ip", "host": " ", "match_ips": [" ", "198.51.100.7"]}, "198.51.100.7"),
    ({"auth_mode": "ip", "host": "sip.example.uz", "match_ips": ["203.0.113.10/32"]}, "sip.example.uz"),
    ({"auth_mode": "ip", "match_ips": []}, ""),
    ({"auth_mode": "register", "host": None, "match_ips": ["203.0.113.10"]}, ""),
])
def test_trunk_host_fallback(payload, host) -> None:
    assert trunk_host(payload) == host


def test_unchanged_feature_codes_are_builtin(analysis) -> None:
    """proof §6: qayta tahlilda skip sabablari faqat already_imported/default_moh/builtin."""
    reasons = {e.reason for e in analysis.items if e.action == "skip"}
    assert reasons <= {"default_moh", "builtin"}, reasons


@pytest.mark.parametrize("key", ["match", "match_ips"])
def test_update_trunk_payload_accepts_db_column_name(key) -> None:
    """proof §5 `match_ips` bilan PATCH qiladi — jim e'tiborsiz qolmasin (API nomi `match`)."""
    payload = UpdateTrunkPayload.model_validate({"updated_at": "2026-10-30T10:00:00Z", key: ["172.21.0.95/32"]})
    assert payload.match == ["172.21.0.95/32"]
    assert UpdateTrunkPayload.model_validate({"updated_at": "2026-10-30T10:00:00Z"}).match is None


class _TrunkCtx:
    def __init__(self, match: str) -> None:
        self._match = match

    def table(self, name: str) -> list[dict]:
        return [{"trunkid": "9", "tech": "pjsip", "name": "x", "disabled": "off"}] if name == "trunks" else []

    def eav(self, name: str) -> dict:
        return {"9": {"match": self._match, "identify_by": "ip"}} if name == "pjsip" else {}


def test_trunk_match_split_by_comma(analysis) -> None:
    ip_trunk = next(e for e in analysis.items if e.kind == "trunk" and e.payload["auth_mode"] == "ip")
    assert ip_trunk.payload["match_ips"] == ["203.0.113.10/32"]
    entries = map_trunk(_TrunkCtx("203.0.113.10/32, 198.51.100.0/24 ,"))
    assert entries[0].payload["match_ips"] == ["203.0.113.10/32", "198.51.100.0/24"]
    assert trunk_host(entries[0].payload) == "203.0.113.10"
