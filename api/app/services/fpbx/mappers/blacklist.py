"""astdb `blacklist/<raqam>` -> `blacklist` (m5a-contract.md §1.2). `dest`/
`blockunknown` kabi raqam bo'lmagan metakalitlar haqiqiy qora ro'yxat yozuvi
EMAS — faqat butunlay raqamli kalitlar olinadi."""
from __future__ import annotations

from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx.mappers import Ctx, Entry


def map_blacklist(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for number, reason in astdb_mod.top_level(ctx.astdb, "blacklist").items():
        if not number.isdigit():
            continue
        source_ref = f"blacklist:{number}"
        entries.append(Entry(
            kind="blacklist", source_ref=source_ref, name=number, number=number,
            action="create",
            payload={"number": number, "reason": reason or None},
        ))
    return entries
