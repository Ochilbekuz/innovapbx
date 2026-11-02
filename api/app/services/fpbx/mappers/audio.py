"""`recordings` + `files/sounds/...` -> `audio_files` (m5a-contract.md §1.2).

Haqiqiy audio konvertatsiyasi (`sox`) — `apply` bosqichi (fayl yozish/mutatsiya,
`analyze()` sof bo'lishi SHART); bu yerda faqat qaysi manba fayl ishlatilishini
(ustuvorlik bo'yicha) aniqlaymiz va mavjudligini tekshiramiz (o'qish, mutatsiyasiz)."""
from __future__ import annotations

from pathlib import Path

from app.services.fpbx.mappers import Ctx, Entry, warning

_EXT_PRIORITY = (".wav", ".sln48", ".sln16", ".sln", ".ulaw", ".alaw", ".gsm", ".g722", ".mp3")
_LANGS = {"uz", "ru", "en"}


def _first_segment(filename: str) -> str:
    """`filename` `&` bilan bir nechtasini birlashtirgan bo'lishi mumkin —
    birinchisi olinadi (qolgani ogohlantirish bilan e'tiborsiz qoldiriladi)."""
    return filename.split("&")[0].strip()


def _find_source(root: Path, filename: str) -> tuple[Path | None, str]:
    """`filename` odatda `custom/<nom>` (tilsiz) yoki `<til>/custom/<nom>` bo'ladi.
    Ustuvorlik bo'yicha birinchi mavjud kengaytmani qaytaradi (`language, path`)."""
    rel = filename.strip("/")
    parts = rel.split("/", 1)
    language = parts[0] if len(parts) == 2 and parts[0] in _LANGS else "uz"
    sounds_dir = root / "files" / "sounds"
    base = sounds_dir / rel
    for ext in _EXT_PRIORITY:
        candidate = base.with_suffix(ext)
        if candidate.exists():
            return candidate, language
    return None, language


def map_audio(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for row in ctx.table("recordings"):
        source_ref = f"recordings:{row['id']}"
        filename_raw = row.get("filename") or ""
        display_name = row.get("displayname") or filename_raw or source_ref
        entry_warnings: list[dict[str, str]] = []
        if "&" in filename_raw:
            entry_warnings.append(warning("multiple_sources", f"Bir nechta fayl: {filename_raw}"))
        filename = _first_segment(filename_raw)
        found, language = _find_source(ctx.root, filename) if filename else (None, "uz")
        if found is None:
            entries.append(Entry(
                kind="audio", source_ref=source_ref, name=display_name, number=None,
                action="skip", reason="audio_missing",
                warnings=[*entry_warnings, warning("audio_missing", f"Audio fayl topilmadi: {filename}")],
            ))
            continue
        entries.append(Entry(
            kind="audio", source_ref=source_ref, name=display_name, number=None,
            action="create", warnings=entry_warnings,
            payload={
                "name": display_name, "language": language, "source": "upload",
                "source_relpath": str(found.relative_to(ctx.root)),
            },
        ))
    return entries
