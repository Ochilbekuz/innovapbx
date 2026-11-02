"""`incoming` -> `inbound_routes` (m5a-contract.md §1.2)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, target_payload, target_warnings, warning

_DEFAULTS = {"privacyman": "0", "alertinfo": "", "delay_answer": "0", "fanswer": ""}


def map_inbound_route(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for index, row in enumerate(ctx.table("incoming"), start=1):
        did = row.get("extension") or None
        key = did or f"catchall-{index}"
        source_ref = f"incoming:{key}"
        name = row.get("description") or key
        entry_warnings: list[dict[str, str]] = []

        target = ctx.resolve(row.get("destination"))
        entry_warnings += target_warnings(target)
        for field in _DEFAULTS:
            if (row.get(field) or "") != _DEFAULTS[field]:
                entry_warnings.append(warning("partial_mapping", f"'{field}' standartdan farqli — Innova'da e'tiborsiz"))

        entries.append(Entry(
            kind="inbound_route", source_ref=source_ref, name=name, number=did,
            action="create", warnings=entry_warnings,
            payload={
                "name": name, "did": did, "callerid_pattern": row.get("cidnum") or None,
                "callerid_name_prefix": row.get("grppre") or None,
                "target_id": target_payload(target),
                "record_override": None, "enabled": True,
            },
        ))
    return entries
