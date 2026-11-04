#!/usr/bin/env python3
"""Tarjima tuzilmasini tekshirish: python3 _tarjima_tekshir.py ru|en [fayl.md ...]

Har tarjima uz asliga nisbatan: id/group/order/path bir xil, title/summary bor (summary <=160, bitta qator),
ichki havolalar to'plami bir xil, sarlavhalar (##/###) va callout soni bir xil, HTML teg yo'q.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONT = re.compile(r"^---\n(.*?)\n---\n?", re.S)
LINK = re.compile(r"\]\(([^)\s]+)\)")


def parse(p: Path):
    src = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = FRONT.match(src)
    if not m:
        return None, src
    fields = {}
    for line in m.group(1).split("\n"):
        mm = re.match(r"^([a-z]+):\s*(.*)$", line.strip())
        if mm:
            fields[mm.group(1)] = mm.group(2).strip()
    return fields, src[m.end():]


def shape(body: str):
    no_code = re.sub(r"```.*?```", "", body, flags=re.S)
    return {
        "links": sorted(set(LINK.findall(no_code))),
        "h2": len(re.findall(r"^## ", no_code, re.M)),
        "h3": len(re.findall(r"^### ", no_code, re.M)),
        "callouts": sorted(re.findall(r"\[!(NOTE|TIP|WARNING|CAUTION)\]", no_code)),
        "code_blocks": body.count("```"),
        "html": bool(re.search(r"^\s*<[a-z!]", no_code, re.M | re.I)),
    }


def check(lang: str, name: str) -> list[str]:
    src_p, tr_p = ROOT / name, ROOT / lang / name
    if not src_p.exists():
        return [f"{name}: uz asli yo'q"]
    if not tr_p.exists():
        return [f"{name}: tarjima yo'q"]
    sf, sb = parse(src_p)
    tf, tb = parse(tr_p)
    if tf is None:
        return [f"{name}: sarlavha bloki (---) yo'q"]
    errs = [f"{name}: {k} '{tf.get(k)}' != '{sf.get(k)}'" for k in ("id", "group", "order", "path") if tf.get(k) != sf.get(k)]
    if not tf.get("title"):
        errs.append(f"{name}: title yo'q")
    if not tf.get("summary") or len(tf["summary"]) > 160:
        errs.append(f"{name}: summary bo'sh yoki 160 dan uzun ({len(tf.get('summary', ''))})")
    ss, ts = shape(sb), shape(tb)
    if ts["html"]:
        errs.append(f"{name}: HTML teg bor")
    for k in ("links", "h2", "h3", "callouts", "code_blocks"):
        if ss[k] != ts[k]:
            extra = ""
            if k == "links":
                extra = f" (yo'q: {sorted(set(ss[k]) - set(ts[k]))}, ortiqcha: {sorted(set(ts[k]) - set(ss[k]))})"
            errs.append(f"{name}: {k} farq qiladi{extra}" if extra else f"{name}: {k} {ts[k]} != {ss[k]}")
    return errs


def main() -> int:
    lang = sys.argv[1]
    names = sys.argv[2:] or sorted(p.name for p in ROOT.glob("*.md") if not p.name.startswith("_"))
    errs = [e for n in names for e in check(lang, n)]
    print("\n".join(errs) if errs else f"OK: {len(names)} fayl ({lang})")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
