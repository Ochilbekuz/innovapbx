"""`app/services/voicemail.py` — sof qismlar (conf qurish, spool o'qish,
xabar havolasi tekshiruvi) va disk qismlar (tmp_path bilan)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services import voicemail as vm
from app.services.voicemail import (
    VoicemailConfBox,
    box_password,
    build_voicemail_conf,
    count_messages,
    list_messages,
    message_paths,
    parse_message_ref,
    parse_message_txt,
)

_TXT = """;
; Message Information file
;
[message]
origmailbox=201
context=t1-dest-x
macrocontext=
exten=s
rdnis=unknown
priority=4
callerchan=PJSIP/172.21.0.30-00000001
callerid="Proof" <998901112233>
origdate=Wed Oct 28 10:00:00 AM UTC 2026
origtime=1793181600
category=
msg_id=1793181600-00000000
flag=
duration=7
"""


def _write_msg(box: Path, folder: str, n: int, *, origtime: int = 1793181600, msg_id: str | None = None,
               duration: int = 7) -> None:
    d = box / folder
    d.mkdir(parents=True, exist_ok=True)
    text = _TXT.replace("origtime=1793181600", f"origtime={origtime}").replace("duration=7", f"duration={duration}")
    text = text.replace("msg_id=1793181600-00000000", f"msg_id={msg_id or f'{origtime}-{n:08d}'}")
    (d / f"msg{n:04d}.txt").write_text(text)
    (d / f"msg{n:04d}.wav").write_bytes(b"RIFF....WAVE")


# ------------------------------------------------------------ conf
def test_conf_has_tenant_context_and_box_lines_without_pin():
    text = build_voicemail_conf("t1", [VoicemailConfBox(mailbox="201", fullname="Aziz", password="xA1")])
    assert "[t1]" in text
    assert "201 => xA1,Aziz,,," in text


def test_conf_without_boxes_still_valid_and_has_no_context():
    text = build_voicemail_conf("t1", [])
    assert "[t1]" not in text
    assert text.endswith("\n")


def test_conf_sanitizes_fullname_separators():
    text = build_voicemail_conf("t1", [VoicemailConfBox(mailbox="300", fullname="A,b|c\n[d];e", password="p")])
    line = next(l for l in text.splitlines() if l.startswith("300 =>"))
    assert line == "300 => p,A b c  d  e,,,"


def test_conf_boxes_are_sorted_by_mailbox():
    text = build_voicemail_conf("t1", [VoicemailConfBox("300", "B", "p"), VoicemailConfBox("201", "A", "p")])
    assert text.index("201 =>") < text.index("300 =>")


def test_box_password_is_not_dtmf_enterable_and_deterministic():
    p1 = box_password("secret", "box-1")
    assert p1 == box_password("secret", "box-1")
    assert p1 != box_password("secret", "box-2")
    assert p1 != box_password("other", "box-1")
    assert not p1.isdigit()
    assert p1.startswith("x")
    assert len(p1) == 17


# ------------------------------------------------------------ xabar havolasi
@pytest.mark.parametrize("ref,expected", [
    ("INBOX/msg0000", ("INBOX", "msg0000")),
    ("Old/msg0123", ("Old", "msg0123")),
])
def test_message_ref_valid(ref, expected):
    assert parse_message_ref(ref) == expected


@pytest.mark.parametrize("ref", [
    "../t1/201/INBOX/msg0000", "/etc/passwd", "INBOX/../msg0000", "INBOX/msg000", "INBOX/msg00000",
    "inbox/msg0000", "Work/msg0000", "INBOX/msg0000.txt", "INBOX/msg0000/", "", "INBOX\\msg0000",
    "INBOX/msg0000\n",
])
def test_message_ref_invalid(ref):
    assert parse_message_ref(ref) is None


# ------------------------------------------------------------ metadata
def test_parse_message_txt_reads_fields():
    meta = parse_message_txt(_TXT)
    assert meta == {"callerid": '"Proof" <998901112233>', "origtime": 1793181600,
                    "duration": 7, "msg_id": "1793181600-00000000"}


def test_parse_message_txt_tolerates_missing_and_bad_values():
    meta = parse_message_txt("[message]\norigtime=abc\nduration=\n")
    assert meta == {"callerid": "", "origtime": 0, "duration": 0, "msg_id": ""}


def test_parse_message_txt_ignores_other_sections_and_value_with_equals():
    meta = parse_message_txt("[other]\nduration=99\n[message]\ncallerid=a=b\nduration=3\n")
    assert meta["duration"] == 3
    assert meta["callerid"] == "a=b"


# ------------------------------------------------------------ spool
def test_list_and_count_messages(tmp_path):
    _write_msg(tmp_path, "INBOX", 0, origtime=1793181600)
    _write_msg(tmp_path, "INBOX", 1, origtime=1793181700, duration=3)
    _write_msg(tmp_path, "Old", 0, origtime=1793181500)
    (tmp_path / "INBOX" / "msg0005.wav").write_bytes(b"x")  # txt yo'q — e'tiborsiz
    (tmp_path / "INBOX" / "README.txt").write_text("x")
    assert count_messages(tmp_path) == {"new": 2, "old": 1}

    items = list_messages(tmp_path)
    assert [i["id"] for i in items] == ["INBOX/msg0001", "INBOX/msg0000", "Old/msg0000"]
    first = items[0]
    assert first == {"id": "INBOX/msg0001", "folder": "inbox", "callerid": '"Proof" <998901112233>',
                     "duration_s": 3, "received_at": "2026-10-28T10:01:40Z", "heard": False,
                     "msg_id": "1793181700-00000001"}
    assert items[2]["folder"] == "old"
    assert items[2]["heard"] is True


def test_list_and_count_missing_box_dir(tmp_path):
    assert count_messages(tmp_path / "nope") == {"new": 0, "old": 0}
    assert list_messages(tmp_path / "nope") == []


def test_message_paths_only_for_valid_existing(tmp_path):
    _write_msg(tmp_path, "INBOX", 0)
    paths = message_paths(tmp_path, "INBOX/msg0000")
    assert paths is not None
    assert paths.wav == tmp_path / "INBOX" / "msg0000.wav"
    assert paths.folder == "INBOX"
    assert paths.msg_id == "1793181600-00000000"
    assert message_paths(tmp_path, "INBOX/msg0001") is None
    assert message_paths(tmp_path, "../x/msg0000") is None


# ------------------------------------------------------------ salomlashuv (greeting)
@pytest.fixture
def spool(tmp_path, monkeypatch):
    monkeypatch.setattr(vm.settings, "voicemail_spool_dir", str(tmp_path / "spool"))
    monkeypatch.setattr(vm.settings, "sounds_dir", str(tmp_path / "sounds"))
    chowned: list[str] = []
    monkeypatch.setattr(vm, "_chown_to_asterisk", lambda p: chowned.append(str(p)))
    return tmp_path, chowned


def test_sync_greeting_links_unavail_and_busy(spool):
    tmp_path, chowned = spool
    vm.sync_greeting("t1", "201", "aud-1")
    box = tmp_path / "spool" / "t1" / "201"
    for name in ("unavail.wav", "busy.wav"):
        assert os.readlink(box / name) == str(tmp_path / "sounds" / "t1" / "aud-1.wav")
    # Asterisk (uid 1000) yoza olishi uchun API yaratgan har narsa chown qilinadi.
    assert str(tmp_path / "spool" / "t1") in chowned
    assert str(box) in chowned
    assert str(box / "unavail.wav") in chowned


def test_sync_greeting_replaces_and_removes(spool):
    tmp_path, _ = spool
    vm.sync_greeting("t1", "201", "aud-1")
    vm.sync_greeting("t1", "201", "aud-2")
    box = tmp_path / "spool" / "t1" / "201"
    assert os.readlink(box / "busy.wav").endswith("aud-2.wav")
    vm.sync_greeting("t1", "201", None)
    assert not (box / "busy.wav").is_symlink()
    assert not (box / "unavail.wav").is_symlink()


def test_sync_greeting_none_keeps_recorded_real_file(spool):
    """Foydalanuvchi telefon orqali (VoiceMailMain) yozgan haqiqiy fayl —
    simvolik havola emas — o'chirilmaydi."""
    tmp_path, _ = spool
    box = tmp_path / "spool" / "t1" / "201"
    box.mkdir(parents=True)
    (box / "unavail.wav").write_bytes(b"real")
    vm.sync_greeting("t1", "201", None)
    assert (box / "unavail.wav").read_bytes() == b"real"


def test_remove_box_dir(spool):
    tmp_path, _ = spool
    vm.sync_greeting("t1", "201", "aud-1")
    vm.remove_box_dir("t1", "201")
    assert not (tmp_path / "spool" / "t1" / "201").exists()
    vm.remove_box_dir("t1", "201")  # idempotent


@pytest.mark.parametrize("code,mailbox", [("..", "201"), ("t1", ".."), ("t1", "2/1"), ("t1", "")])
def test_box_dir_rejects_unsafe_parts(spool, code, mailbox):
    with pytest.raises(ValueError):
        vm.box_dir(code, mailbox)


# ------------------------------------------------------------ AMI
class _FakeAmi:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def ensure_connected(self) -> None:
        return None

    async def action(self, name: str, **kw) -> dict:
        self.calls.append((name, kw))
        key = kw.get("Command", name)
        return self.responses.get(key, {"Response": "Success"})


async def test_reload_and_verify_ok():
    ami = _FakeAmi({"voicemail show users for t1": {"Response": "Success", "Output": "t1  201  Aziz  0\n"}})
    await vm._reload_and_verify_voicemail(ami, "t1", ["201"])
    assert ami.calls[0] == ("Command", {"Command": "voicemail reload"})


async def test_reload_and_verify_missing_box_raises():
    ami = _FakeAmi({"voicemail show users for t1": {"Response": "Success", "Output": "t1  2010 x 0\n"}})
    with pytest.raises(RuntimeError, match="201"):
        await vm._reload_and_verify_voicemail(ami, "t1", ["201"])


async def test_reload_rejected_raises():
    ami = _FakeAmi({"voicemail reload": {"Response": "Error", "Message": "no module"}})
    with pytest.raises(RuntimeError, match="no module"):
        await vm._reload_and_verify_voicemail(ami, "t1", [])


async def test_reload_without_boxes_skips_show():
    ami = _FakeAmi({})
    await vm._reload_and_verify_voicemail(ami, "t1", [])
    assert [c[1].get("Command") for c in ami.calls] == ["voicemail reload"]


async def test_move_to_old_uses_ami_voicemailmove():
    ami = _FakeAmi({})
    await vm.ami_mark_heard(ami, "t1", "201", "INBOX", "m-1")
    assert ami.calls == [("VoicemailMove", {"Context": "t1", "Mailbox": "201", "Folder": "INBOX",
                                             "ID": "m-1", "ToFolder": "Old"})]


async def test_remove_uses_ami_voicemailremove_and_raises_on_error():
    ami = _FakeAmi({"VoicemailRemove": {"Response": "Error", "Message": "Message not found"}})
    with pytest.raises(RuntimeError, match="Message not found"):
        await vm.ami_remove(ami, "t1", "201", "Old", "m-1")
    assert ami.calls == [("VoicemailRemove", {"Context": "t1", "Mailbox": "201", "Folder": "Old", "ID": "m-1"})]
