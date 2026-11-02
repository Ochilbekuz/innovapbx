"""`timeconditions` -> `time_conditions` (m5a-contract.md §1.2). `truegoto` ->
`open_target_id`, `falsegoto` -> `closed_target_id` — TO'G'RIDAN-TO'G'RI, TESKARI
EMAS (proof §4 maxsus shu yo'nalishni tekshiradi)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, ref, target_payload, target_warnings


def map_time_condition(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for row in ctx.table("timeconditions"):
        tc_id = row["timeconditions_id"]
        source_ref = f"timeconditions:{tc_id}"
        name = row.get("displayname") or tc_id
        entry_warnings: list[dict[str, str]] = []

        open_target = ctx.resolve(row.get("truegoto"))
        closed_target = ctx.resolve(row.get("falsegoto"))
        entry_warnings += target_warnings(open_target) + target_warnings(closed_target)

        time_group_id = row.get("time")
        entries.append(Entry(
            kind="time_condition", source_ref=source_ref, name=name, number=None,
            action="create", warnings=entry_warnings,
            depends_on=[f"timegroups_groups:{time_group_id}"] if time_group_id else [],
            payload={
                "name": name, "time_group_id": ref("time_group", time_group_id),
                "honor_holidays": True,
                "open_target_id": target_payload(open_target),
                "closed_target_id": target_payload(closed_target),
                "override": None, "toggle_code": None,
            },
        ))
    return entries
