"""`app/services/system_update.py` — m11-update-contract.md bo'lim 1/4 (sof
funksiyalar: status parse, changelog filtri, ANSI tozalash, log offset)."""
from __future__ import annotations

from pathlib import Path

from app.services import system_update as su


def test_strip_ansi_removes_color_codes():
    assert su.strip_ansi("\x1b[31mxato\x1b[0m") == "xato"


def test_parse_status_ignores_unknown_lines():
    text = "state=idle\nnot_a_pair\nlatest=1.0.13\n"
    result = su.parse_status(text)
    assert result == {"state": "idle", "latest": "1.0.13"}


def test_pending_word_valid_and_invalid():
    assert su.pending_word("check\n") == "check"
    assert su.pending_word("update") == "update"
    assert su.pending_word("garbage") is None
    assert su.pending_word(None) is None


def test_version_tuple_handles_corrupt_segments():
    assert su.version_tuple("1.0.13") == (1, 0, 13)
    assert su.version_tuple("1.x.13") == (1, 0, 13)


def test_build_update_out_sanitizes_unknown_values_never_raises():
    out = su.build_update_out(
        agent=True, raw_status={"state": "garbage", "error": "nonsense", "available": "1"},
        request_text=None, configured_version="1.0.12", changelog=[],
    )
    assert out.state == "idle"
    assert out.error is None
    assert out.available is True


def test_build_update_out_current_falls_back_to_configured_version():
    out = su.build_update_out(
        agent=True, raw_status={}, request_text=None, configured_version="1.0.12", changelog=[],
    )
    assert out.current == "1.0.12"


def test_build_update_out_bad_timestamp_becomes_none_not_500():
    out = su.build_update_out(
        agent=True, raw_status={"checked_at": "not-a-date"}, request_text=None,
        configured_version=None, changelog=[],
    )
    assert out.checked_at is None


def test_parse_changelog_filters_and_sorts_newest_first():
    md = (
        "## 1.0.11 — 2026-10-01\nEski\n\n"
        "## 1.0.13 — 2026-11-04\nYangi\n\n"
        "## 1.0.12 — 2026-10-20\nO'rta\n"
    )
    entries = su.parse_changelog(md, "1.0.12")
    assert [e.version for e in entries] == ["1.0.13"]
    assert entries[0].body == "Yangi"


def test_parse_changelog_excludes_version_equal_to_current():
    md = "## 1.0.12 — 2026-10-20\nJoriy\n\n## 1.0.13 — 2026-11-04\nYangi\n"
    entries = su.parse_changelog(md, "1.0.12")
    assert [e.version for e in entries] == ["1.0.13"]


def test_parse_changelog_no_current_returns_everything():
    md = "## 1.0.1\nA\n\n## 1.0.2\nB\n"
    entries = su.parse_changelog(md, None)
    assert [e.version for e in entries] == ["1.0.2", "1.0.1"]


def test_agent_available_false_when_dir_missing(tmp_path):
    assert su.agent_available(tmp_path / "no-such-dir") is False


def test_agent_available_true_when_writable(tmp_path):
    assert su.agent_available(tmp_path) is True


def test_write_request_then_duplicate_raises_file_exists(tmp_path):
    su.write_request(tmp_path, "check")
    assert (tmp_path / "request").read_text() == "check\n"
    try:
        su.write_request(tmp_path, "update")
        raised = False
    except FileExistsError:
        raised = True
    assert raised


def test_read_log_chunk_missing_file_returns_zeros(tmp_path):
    offset, size, text = su.read_log_chunk(tmp_path / "update.log", 0)
    assert (offset, size, text) == (0, 0, "")


def test_read_log_chunk_offset_beyond_size_resets_to_zero(tmp_path):
    log = tmp_path / "update.log"
    log.write_text("salom")
    offset, size, text = su.read_log_chunk(log, 999)
    assert offset == 5
    assert size == 5
    assert text == "salom"


def test_read_log_chunk_strips_ansi(tmp_path):
    log = tmp_path / "update.log"
    log.write_text("\x1b[32myashil\x1b[0m\n")
    _offset, _size, text = su.read_log_chunk(log, 0)
    assert text == "yashil\n"


def test_read_log_chunk_respects_max_bytes(tmp_path):
    log = tmp_path / "update.log"
    log.write_text("a" * 100)
    offset, size, text = su.read_log_chunk(log, 0, max_bytes=10)
    assert size == 100
    assert offset == 10
    assert text == "a" * 10
