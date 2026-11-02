"""`conf/voicemail.conf` dagi `[default]` bo'lim pochta qutilari.

Qator shakli: `<mailbox>=<pin>,<Ism>,<email>,<pager>,<variantlar|pipe|bilan>`."""
from __future__ import annotations

from pathlib import Path


def _parse_options(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    out = {}
    for part in raw.split("|"):
        if "=" in part:
            key, _, value = part.partition("=")
            out[key.strip()] = value.strip()
    return out


def _parse_mailbox_line(line: str) -> tuple[str, dict] | None:
    if "=" not in line:
        return None
    mailbox, _, rest = line.partition("=")
    mailbox = mailbox.strip()
    if not mailbox:
        return None
    fields = rest.split(",")
    fields += [""] * (5 - len(fields))
    pin, name, email, pager, options = fields[:5]
    return mailbox, {
        "pin": pin or None, "name": name, "email": email or None,
        "pager": pager or None, "options": _parse_options(options),
    }


def parse_voicemail_conf(text: str) -> dict[str, dict]:
    """Faqat `[default]` bo'lim; keyingi `[...]` sarlavha (yoki fayl oxiri)gacha."""
    boxes: dict[str, dict] = {}
    in_default = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_default = line == "[default]"
            continue
        if not in_default:
            continue
        parsed = _parse_mailbox_line(line)
        if parsed is not None:
            mailbox, data = parsed
            boxes[mailbox] = data
    return boxes


def parse_voicemail_conf_file(path: str | Path) -> dict[str, dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_voicemail_conf(text)
