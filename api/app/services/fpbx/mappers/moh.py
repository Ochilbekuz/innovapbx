"""`music` + `files/moh/<category>/*` -> `moh_classes` + `moh_class_files`
(m5a-contract.md §1.2). `default` — FreePBX'da jadval qatori YO'Q (ildiz darajadagi
fayllar), Innova'da allaqachon o'rnatilgan `default` sinfi bor — shu sabab bitta
sintetik (TSV qatoriga bog'lanmagan) `skip` elementi qo'shiladi."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, warning

_AUDIO_EXT = (".wav", ".sln48", ".sln16", ".sln", ".ulaw", ".alaw", ".gsm", ".g722", ".mp3")


def _category_files(ctx: Ctx, category: str) -> list[str]:
    folder = ctx.root / "files" / "moh" / category
    if not folder.is_dir():
        return []
    return sorted(str(p.relative_to(ctx.root)) for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in _AUDIO_EXT)


def map_moh(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = [Entry(
        kind="moh", source_ref="music:default", name="default", number=None,
        action="skip", reason="default_moh",
    )]
    for row in ctx.table("music"):
        source_ref = f"music:{row['id']}"
        category = row.get("category") or row["id"]
        if (row.get("type") or "custom") != "custom":
            entries.append(Entry(
                kind="moh", source_ref=source_ref, name=category, number=None,
                action="unsupported", reason="moh_streaming_unsupported",
                warnings=[warning("moh_streaming_unsupported", f"Streaming MOH qo'llab-quvvatlanmaydi: {category}")],
            ))
            continue
        files = _category_files(ctx, category)
        entry_warnings = [] if files else [warning("moh_files_missing", f"MOH fayllari topilmadi: {category}")]
        entries.append(Entry(
            kind="moh", source_ref=source_ref, name=category, number=None,
            action="create", warnings=entry_warnings,
            payload={"name": category, "shuffle": (row.get("random") or "0") == "1", "files": files},
        ))
    return entries
