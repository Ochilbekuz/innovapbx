"""`conf/voicemail.conf` `[default]` mailboxlari -> `voicemail_boxes` (+ target)
(m5a-contract.md §1.2). Faqat `users`da mavjud va `voicemail != 'novm'` bo'lgan
mailbox ishlov olinadi; qolganlari (namunaviy `1234` kabi) `ignored` ro'yxatiga
`plan.py` tomonidan qo'shiladi (bu mapper ularni butunlay bilmaydi deb hisoblaymiz —
`map_voicemail` faqat extension bilan bog'lanadigan qatorlarni Entry qiladi;
cross-reference uchun `unmatched_mailboxes()` yordamchisi ham eksport qilinadi)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, weak_secret
from app.services.fpbx.vmconf import parse_voicemail_conf_file

_GREETING_EXT = (".wav", ".sln48", ".sln16", ".sln", ".ulaw", ".alaw", ".gsm", ".g722", ".mp3")


def _has_extension(ctx: Ctx, mailbox: str) -> bool:
    return any(row["extension"] == mailbox and (row.get("voicemail") or "novm") != "novm"
               for row in ctx.table("users"))


def _greeting_relpath(ctx: Ctx, mailbox: str) -> str | None:
    folder = ctx.root / "files" / "voicemail" / "default" / mailbox
    if not folder.is_dir():
        return None
    for ext in _GREETING_EXT:
        candidate = folder / f"unavail{ext}"
        if candidate.exists():
            return str(candidate.relative_to(ctx.root))
    return None


def all_boxes(ctx: Ctx) -> dict[str, dict]:
    """`conf/voicemail.conf`dagi `[default]` bo'lim mailboxlari (xom)."""
    path = ctx.root / "conf" / "voicemail.conf"
    return parse_voicemail_conf_file(path) if path.exists() else {}


def unmatched_mailboxes(ctx: Ctx) -> list[str]:
    """`users`ga bog'lanmagan mailboxlar — `plan.py` shularni `ignored`ga qo'shadi
    (`table="voicemail.conf"`, `key=f"default/{mailbox}"`, `reason="vm_without_extension"`)."""
    return [mb for mb in all_boxes(ctx) if not _has_extension(ctx, mb)]


def map_voicemail(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for mailbox, box in all_boxes(ctx).items():
        if not _has_extension(ctx, mailbox):
            continue
        source_ref = f"voicemail.conf:default/{mailbox}"
        pin = box.get("pin")
        options = box.get("options") or {}
        attach = options.get("attach", "yes") == "yes"
        greeting = _greeting_relpath(ctx, mailbox)
        entries.append(Entry(
            kind="voicemail", source_ref=source_ref, name=box.get("name") or mailbox, number=mailbox,
            action="create", depends_on=[f"users:{mailbox}"],
            has_secret=bool(pin), weak_secret=weak_secret(pin, equals_number=mailbox),
            payload={
                "mailbox": mailbox, "pin_plain": pin, "email": box.get("email"),
                "email_notify": bool(box.get("email")), "attach_audio": attach,
                "greeting_source_relpath": greeting,
            },
        ))
    return entries
