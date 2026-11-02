"""`app/services/security_log_tail.py` — sof funksiyalar (DB/AMI'siz):
qator ajratish (`parse_security_line`) va fayl tail holati (`read_new_lines`)."""
from __future__ import annotations

import os

import pytest

from app.services.security_log_tail import TailState, parse_security_line, read_new_lines

LIVE_LINE = (
    '[Oct 28 21:27:18] SECURITY[118] res_security_log.c: SecurityEvent="ChallengeResponseFailed",'
    'EventTV="2026-10-28T21:27:18.055+0000",Severity="Error",Service="PJSIP",EventVersion="1",'
    'AccountID="t1-202",SessionID="register-only-t1-202",LocalAddress="IPV4/UDP/172.21.0.4/5060",'
    'RemoteAddress="IPV4/UDP/172.21.0.5/5090",Challenge="...",Response="...",ExpectedResponse=""'
)


def test_parse_live_format_extracts_kind_and_ip():
    ev = parse_security_line(LIVE_LINE)
    assert ev is not None
    assert (ev.kind, ev.ip) == ("ChallengeResponseFailed", "172.21.0.5")


def test_parse_ignores_non_countable_kind():
    line = LIVE_LINE.replace("ChallengeResponseFailed", "SuccessfulAuth")
    assert parse_security_line(line) is None


def test_parse_ignores_line_without_remote_address():
    line = 'SecurityEvent="ChallengeResponseFailed",Severity="Error"'
    assert parse_security_line(line) is None


def test_parse_ignores_blank_and_banner_lines():
    assert parse_security_line("") is None
    assert parse_security_line("Asterisk Ready.") is None


@pytest.mark.parametrize("kind", ["InvalidAccountID", "InvalidPassword"])
def test_parse_forward_compat_kinds_still_countable(kind):
    line = LIVE_LINE.replace("ChallengeResponseFailed", kind)
    ev = parse_security_line(line)
    assert ev is not None and ev.kind == kind


def test_read_new_lines_first_call_jumps_to_eof(tmp_path):
    path = tmp_path / "security.log"
    path.write_text("old line that must NOT be replayed\n")
    state = TailState()
    assert read_new_lines(str(path), state) == []
    assert state.started is True


def test_read_new_lines_returns_only_complete_new_lines(tmp_path):
    path = tmp_path / "security.log"
    path.write_text("")
    state = TailState()
    read_new_lines(str(path), state)  # EOF ga sakraydi (bo'sh fayl)

    with open(path, "a") as fh:
        fh.write("line1\nline2\n")
    assert read_new_lines(str(path), state) == ["line1", "line2"]
    assert read_new_lines(str(path), state) == []  # ikkinchi chaqiruv -- yangi narsa yo'q


def test_read_new_lines_ignores_incomplete_trailing_line(tmp_path):
    path = tmp_path / "security.log"
    path.write_text("")
    state = TailState()
    read_new_lines(str(path), state)

    with open(path, "a") as fh:
        fh.write("complete\nincomplete-no-newline")
    assert read_new_lines(str(path), state) == ["complete"]
    with open(path, "a") as fh:
        fh.write("-finished\n")
    assert read_new_lines(str(path), state) == ["incomplete-no-newline-finished"]


def test_read_new_lines_restarts_from_zero_on_truncate(tmp_path):
    path = tmp_path / "security.log"
    path.write_text("")
    state = TailState()
    read_new_lines(str(path), state)
    with open(path, "a") as fh:
        fh.write("a" * 50 + "\n")
    read_new_lines(str(path), state)
    assert state.offset > 0

    path.write_text("short\n")  # log aylanishi -- fayl qisqardi
    assert read_new_lines(str(path), state) == ["short"]


def test_read_new_lines_missing_file_returns_empty_and_keeps_state(tmp_path):
    missing = tmp_path / "does-not-exist.log"
    state = TailState()
    assert read_new_lines(str(missing), state) == []
    assert state.started is False


def test_read_new_lines_detects_inode_change(tmp_path):
    path = tmp_path / "security.log"
    path.write_text("")
    state = TailState()
    read_new_lines(str(path), state)

    os.remove(path)
    path.write_text("fresh-after-rotate\n")
    assert read_new_lines(str(path), state) == ["fresh-after-rotate"]


# ---------------------------------------------------------------- M3a §0: transport (WS/WSS ajratiladi)
@pytest.mark.parametrize("remote,transport", [
    ("IPV4/UDP/172.21.0.5/5090", "udp"), ("IPV4/TCP/172.21.0.5/5090", "tcp"), ("IPV4/TLS/172.21.0.5/5061", "tls"),
    ("IPV4/WS/172.21.0.9/41234", "ws"), ("IPV4/WSS/172.21.0.9/41234", "ws"),
])
def test_parse_extracts_transport_ws_and_wss_both_ws(remote, transport):
    ev = parse_security_line(LIVE_LINE.replace("IPV4/UDP/172.21.0.5/5090", remote))
    assert ev is not None and ev.transport == transport and ev.ip == remote.split("/")[2]


def test_parse_extracts_account_id():
    assert parse_security_line(LIVE_LINE).account == "t1-202"
    assert parse_security_line(LIVE_LINE.replace('AccountID="t1-202",', "")).account is None
