"""`mysql -B` (TSV) eksport fayllarini o'qish — `innova-fpbx-export.sh` shu formatda yozadi.

Maydonlar TAB, satrlar NEWLINE bilan ajratilgan; har maydon ichidagi TAB/NEWLINE/BACKSLASH
`\\t`/`\\n`/`\\\\` ko'rinishida escape qilingan. SQL NULL — ANIQ "NULL" so'zi (4 harf, escape
YO'Q) sifatida chiqadi — shu sabab HAQIQIY "NULL" matnli qiymatdan FARQLANMAYDI (bu FreePBX
eksport formatining o'zi shunday) va har bir chaqiruvchi buni bilishi SHART (masalan
`featurecodes.customcode`da "NULL" — override yo'q, bo'sh satr emas)."""
from __future__ import annotations

from pathlib import Path

_ESCAPES = {"t": "\t", "n": "\n", "\\": "\\", "0": "\0", "r": "\r"}


def _unescape(field: str) -> str:
    if "\\" not in field:
        return field
    out: list[str] = []
    i = 0
    while i < len(field):
        ch = field[i]
        if ch == "\\" and i + 1 < len(field):
            out.append(_ESCAPES.get(field[i + 1], field[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def parse_tsv(text: str) -> list[dict[str, str | None]]:
    """Birinchi qator — ustun nomlari. Har bir keyingi qator — dict (qiymat ANIQ
    "NULL" bo'lsa -> Python `None`, aks holda unescape qilingan satr)."""
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str | None]] = []
    for line in lines[1:]:
        if line == "":
            continue
        fields = [_unescape(f) for f in line.split("\t")]
        rows.append({name: (None if value == "NULL" else value)
                     for name, value in zip(header, fields)})
    return rows


def parse_tsv_file(path: str | Path) -> list[dict[str, str | None]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_tsv(text)


def group_by(rows: list[dict], field: str) -> dict[str, list[dict]]:
    """Qatorlarni berilgan ustun qiymati bo'yicha guruhlaydi (tartib saqlanadi) —
    EAV jadvallar (`sip`/`pjsip`/`queues_details`, `(id,keyword,data,flags)`) va
    bir-ko'p (`ivr_entries`, `outbound_route_patterns`, ...) uchun umumiy."""
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row[field], []).append(row)
    return out


def pivot_first(rows_for_id: list[dict], *, keyword_field: str = "keyword",
                 data_field: str = "data") -> dict[str, str | None]:
    """EAV qatorlar ro'yxatini (bitta `id` uchun) `{keyword: data}` ga yig'adi —
    takrorlangan kalit bo'lsa BIRINCHI qiymat saqlanadi (ko'p qatorli kalitlar —
    masalan `queues_details` `member` — chaqiruvchi tomonidan alohida, `group_by`
    bilan filtrlab olinadi, bu yerda emas)."""
    out: dict[str, str | None] = {}
    for row in rows_for_id:
        kw = row[keyword_field]
        if kw not in out:
            out[kw] = row.get(data_field)
    return out
