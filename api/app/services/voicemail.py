"""Ovozli pochta (m1c-contract.md §2) — Asterisk `app_voicemail` tomoniga
yetkazish va spool'ni o'qish. MOH (`moh.py`) bilan BIR XIL qolip:
DB so'rovi (`load_*`) -> sof qurish (`build_voicemail_conf`) -> atomik yozish
(`dialplan` umumiy hajm, `voicemail.conf` `#include` qiladi) -> AMI
`voicemail reload` + `voicemail show users for <code>` bilan tasdiq.

Spool (`voicemail` umumiy hajm, `<spool>/<code>/<box>/{INBOX,Old}/msgNNNN.{txt,wav}`)
ni API faqat O'QIYDI. Ko'chirish/o'chirish — AMI `VoicemailMove`/`VoicemailRemove`
(`msg_id` bo'yicha): raqamlarni qayta tartiblash, qulf va MWI'ni Asterisk
o'zi bajaradi. API yaratadigan yagona narsa — salomlashuv havolalari
(`unavail.wav`/`busy.wav` -> `sounds` hajmidagi audio): API root, Asterisk
uid 1000 — shu sabab yaratilgan papka/havola `ASTERISK_UID` ga chown qilinadi
(aks holda Asterisk INBOX yarata olmaydi)."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import VoicemailBox
from app.services.apply import AmiLike
from app.services.atomic_write import atomic_write

ASTERISK_UID = 1000
ASTERISK_GID = 1000
FOLDERS = {"INBOX": "inbox", "Old": "old"}
GREETING_FILES = ("unavail.wav", "busy.wav")

_REF_RE = re.compile(r"(INBOX|Old)/(msg[0-9]{4})")
_SAFE_PART_RE = re.compile(r"[A-Za-z0-9_-]+")
_FULLNAME_BAD = str.maketrans({c: " " for c in ",|\n\r[];="})


@dataclass(frozen=True)
class VoicemailConfBox:
    mailbox: str
    fullname: str
    password: str


@dataclass(frozen=True)
class MessagePaths:
    folder: str
    txt: Path
    wav: Path
    msg_id: str


# ------------------------------------------------------------ sof qismlar
def box_password(secret_key: str, box_id: str) -> str:
    """Faylga yoziladigan parol: deterministik (fayl har apply'da o'zgarmasin),
    `x` bilan boshlanadi — telefon klaviaturasidan TERIB BO'LMAYDI. Haqiqiy
    PIN faqat bazada (bcrypt), tekshiruv — ichki `CURL()` endpoint."""
    digest = hmac.new(secret_key.encode(), f"vm:{box_id}".encode(), hashlib.sha256).hexdigest()
    return "x" + digest[:16]


def build_voicemail_conf(tenant_code: str, boxes: list[VoicemailConfBox]) -> str:
    lines = [
        "; Innova PBX — API avtomatik generatsiya qiladi (qo'lda tahrirlanmasin).",
        f"; tenant={tenant_code}",
    ]
    if boxes:
        lines += ["", f"[{tenant_code}]"]
        for box in sorted(boxes, key=lambda b: b.mailbox):
            lines.append(f"{box.mailbox} => {box.password},{box.fullname.translate(_FULLNAME_BAD)},,,")
    return "\n".join(lines) + "\n"


def parse_message_ref(ref: str) -> tuple[str, str] | None:
    """`INBOX/msg0000` -> (`INBOX`, `msg0000`). Boshqa har qanday shakl
    (`..`, absolyut yo'l, kengaytma, boshqa papka) -> None (router 404)."""
    m = _REF_RE.fullmatch(ref)
    return (m.group(1), m.group(2)) if m else None


def _int_or_zero(value: str) -> int:
    return int(value) if value.isdigit() else 0


def parse_message_txt(text: str) -> dict:
    raw: dict[str, str] = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "message" and "=" in line:
            key, value = line.split("=", 1)
            raw[key.strip()] = value.strip()
    return {
        "callerid": raw.get("callerid", ""),
        "origtime": _int_or_zero(raw.get("origtime", "")),
        "duration": _int_or_zero(raw.get("duration", "")),
        "msg_id": raw.get("msg_id", ""),
    }


def _iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _message_txts(box: Path, folder: str) -> list[Path]:
    d = box / folder
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if parse_message_ref(f"{folder}/{p.stem}") and p.suffix == ".txt")


def count_messages(box: Path) -> dict[str, int]:
    return {"new": len(_message_txts(box, "INBOX")), "old": len(_message_txts(box, "Old"))}


def list_messages(box: Path) -> list[dict]:
    """Yangilari (INBOX) avval, har papka ichida eng yangisi birinchi."""
    items: list[dict] = []
    for folder, label in FOLDERS.items():
        folder_items = []
        for txt in _message_txts(box, folder):
            meta = parse_message_txt(txt.read_text(encoding="utf-8", errors="replace"))
            folder_items.append({
                "id": f"{folder}/{txt.stem}", "folder": label, "callerid": meta["callerid"],
                "duration_s": meta["duration"], "received_at": _iso_utc(meta["origtime"]),
                "heard": folder == "Old", "msg_id": meta["msg_id"],
            })
        items += sorted(folder_items, key=lambda i: (i["received_at"], i["id"]), reverse=True)
    return items


def message_paths(box: Path, ref: str) -> MessagePaths | None:
    parsed = parse_message_ref(ref)
    if parsed is None:
        return None
    folder, name = parsed
    txt = box / folder / f"{name}.txt"
    if not txt.is_file():
        return None
    meta = parse_message_txt(txt.read_text(encoding="utf-8", errors="replace"))
    return MessagePaths(folder=folder, txt=txt, wav=txt.with_suffix(".wav"), msg_id=meta["msg_id"])


# ------------------------------------------------------------ disk
def box_dir(tenant_code: str, mailbox: str) -> Path:
    for part in (tenant_code, mailbox):
        if not _SAFE_PART_RE.fullmatch(part or ""):
            raise ValueError(f"Xavfsiz bo'lmagan spool yo'li qismi: {part!r}")
    return Path(settings.voicemail_spool_dir) / tenant_code / mailbox


def _chown_to_asterisk(path: Path) -> None:
    os.lchown(path, ASTERISK_UID, ASTERISK_GID)


def _ensure_box_dir(tenant_code: str, mailbox: str) -> Path:
    box = box_dir(tenant_code, mailbox)
    for d in (box.parent, box):
        if not d.is_dir():
            d.mkdir(mode=0o750, parents=True, exist_ok=True)
            _chown_to_asterisk(d)
    return box


def sync_greeting(tenant_code: str, mailbox: str, greeting_audio_id: str | None) -> None:
    """`unavail.wav`/`busy.wav` -> tanlangan audio (simvolik havola). `None`
    bo'lsa faqat BIZ qo'ygan havolalar olinadi — telefon orqali yozilgan
    haqiqiy fayl qoladi. IDEMPOTENT."""
    box = _ensure_box_dir(tenant_code, mailbox)
    wanted = Path(settings.sounds_dir) / tenant_code / f"{greeting_audio_id}.wav" if greeting_audio_id else None
    for name in GREETING_FILES:
        link = box / name
        if wanted is None:
            if link.is_symlink():
                link.unlink()
            continue
        if link.is_symlink() and os.readlink(link) == str(wanted):
            continue
        link.unlink(missing_ok=True)
        link.symlink_to(wanted)
        _chown_to_asterisk(link)


def remove_box_dir(tenant_code: str, mailbox: str) -> None:
    shutil.rmtree(box_dir(tenant_code, mailbox), ignore_errors=True)


def write_voicemail_file(text_content: str) -> None:
    atomic_write(settings.dialplan_dir, settings.voicemail_filename, text_content, tmp_prefix=".tmp-vm-")


# ------------------------------------------------------------ AMI
def _check_response(resp: dict, what: str) -> None:
    if str(resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"{what} rad etildi: {resp.get('Message', '')}")


async def _reload_and_verify_voicemail(ami: AmiLike, tenant_code: str, mailboxes: list[str]) -> None:
    await ami.ensure_connected()
    _check_response(await ami.action("Command", Command="voicemail reload"), "voicemail reload")
    if not mailboxes:
        return
    show = await ami.action("Command", Command=f"voicemail show users for {tenant_code}")
    shown = {tok for line in (show.get("Output", "") or "").splitlines() for tok in line.split()}
    missing = [m for m in mailboxes if m not in shown]
    if missing:
        raise RuntimeError(f"tekshiruv muvaffaqiyatsiz: quti(lar) ko'rinmadi: {missing}")


async def ami_mark_heard(ami: AmiLike, tenant_code: str, mailbox: str, folder: str, msg_id: str) -> None:
    await ami.ensure_connected()
    resp = await ami.action("VoicemailMove", Context=tenant_code, Mailbox=mailbox, Folder=folder,
                            ID=msg_id, ToFolder="Old")
    _check_response(resp, "VoicemailMove")


async def ami_remove(ami: AmiLike, tenant_code: str, mailbox: str, folder: str, msg_id: str) -> None:
    await ami.ensure_connected()
    resp = await ami.action("VoicemailRemove", Context=tenant_code, Mailbox=mailbox, Folder=folder, ID=msg_id)
    _check_response(resp, "VoicemailRemove")


# ------------------------------------------------------------ nosof yig'ish
def _fullname(box: VoicemailBox) -> str:
    return box.extension.name if box.extension else f"Quti {box.mailbox}"


async def load_tenant_boxes(session: AsyncSession, tenant_id: str) -> list[VoicemailBox]:
    return list((await session.execute(
        select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id).order_by(VoicemailBox.mailbox)
    )).scalars().all())


async def apply_voicemail(session: AsyncSession, *, tenant_id: str, tenant_code: str, ami: AmiLike) -> None:
    """Qutilar -> `voicemail_innova.conf` + salomlashuv havolalari -> reload."""
    boxes = await load_tenant_boxes(session, tenant_id)
    secret = settings.require_secret_key()
    for box in boxes:
        sync_greeting(tenant_code, box.mailbox, str(box.greeting_audio_id) if box.greeting_audio_id else None)
    conf_boxes = [VoicemailConfBox(mailbox=b.mailbox, fullname=_fullname(b), password=box_password(secret, str(b.id)))
                  for b in boxes]
    write_voicemail_file(build_voicemail_conf(tenant_code, conf_boxes))
    await _reload_and_verify_voicemail(ami, tenant_code, [b.mailbox for b in boxes])
