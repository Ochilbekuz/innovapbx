"""Asterisk `astdb.txt` tekis fayl formatini o'qish (`AMPUSER/<N>/*`, `CF`/`CFB`/`CFU`/`DND`,
`CONFERENCE/<id>/*`, `QPENALTY/<id>/agents/<N>`, `followme/*`, `blacklist/<raqam>`, ...).

Qator shakli: `/<OILA>/<kalit...>                      : <qiymat>` (ustun kengligigacha
bo'shliq bilan to'ldirilgan, oxirgi "N results found." qatori — kalit `/` bilan
boshlanmaydi, jim tashlab yuboriladi)."""
from __future__ import annotations

import re
from pathlib import Path

_LINE_RE = re.compile(r"^(/\S+)\s*:\s(.*)$")


def parse_astdb(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("/"):
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        out[match.group(1)] = match.group(2).rstrip()
    return out


def parse_astdb_file(path: str | Path) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_astdb(text)


def family(flat: dict[str, str], prefix: str) -> dict[str, str]:
    """`/<prefix>/<qolgan qism>` kalitlarni topadi, `qolgan qism`ni kalit qilib
    qaytaradi — masalan `family(db, "AMPUSER/101")` -> `{"device": "101", ...}`."""
    full_prefix = f"/{prefix}/"
    return {key[len(full_prefix):]: value for key, value in flat.items()
             if key.startswith(full_prefix)}


def top_level(flat: dict[str, str], prefix: str) -> dict[str, str]:
    """`/<prefix>/<bir bosqich>` — faqat kalit ichida `/` qolmagan (masalan
    `CF`/`CFB`/`CFU`/`DND` — `/CF/102` -> `{"102": "106"}`); ichki `/` bo'lsa
    (masalan `blacklist/dest`) chiqarib tashlanadi — raqamlar emas."""
    full_prefix = f"/{prefix}/"
    out = {}
    for key, value in flat.items():
        if key.startswith(full_prefix):
            rest = key[len(full_prefix):]
            if "/" not in rest:
                out[rest] = value
    return out
