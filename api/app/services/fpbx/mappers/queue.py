"""`queues_config` + `queues_details` (EAV, `member` ko'p qiymatli) + astdb
`QPENALTY/<N>/agents/*` (dinamik a'zolar) -> `queues` + `queue_members`
(m5a-contract.md §1.2, proof §4: 2 statik + 1 dinamik a'zo)."""
from __future__ import annotations

from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx import tsv as tsv_mod
from app.services.fpbx.mappers import Ctx, Entry, target_payload, target_warnings


def _static_members(details_rows: list[dict]) -> list[dict]:
    members = []
    for row in details_rows:
        if row.get("keyword") != "member":
            continue
        raw = row.get("data") or ""
        ext_part, _, penalty_part = raw.partition(",")
        extension = ext_part.split("@")[0].split("/")[-1]  # Local/101@from-queue/n -> 101
        members.append({
            "extension_number": extension, "penalty": int(penalty_part) if penalty_part.isdigit() else 0,
            "dynamic": False,
        })
    return members


def map_queue(ctx: Ctx) -> list[Entry]:
    details_by_id = tsv_mod.group_by(ctx.table("queues_details"), "id")
    entries: list[Entry] = []
    for row in ctx.table("queues_config"):
        number = row["extension"]
        source_ref = f"queues_config:{number}"
        name = row.get("descr") or number
        pivoted = tsv_mod.pivot_first(details_by_id.get(number, []))
        entry_warnings: list[dict[str, str]] = []

        members = _static_members(details_by_id.get(number, []))
        for ext, penalty in astdb_mod.family(ctx.astdb, f"QPENALTY/{number}/agents").items():
            members.append({
                "extension_number": ext, "penalty": int(penalty) if penalty.isdigit() else 0,
                "dynamic": True,
            })

        timeout_target = ctx.resolve(row.get("dest"))
        entry_warnings += target_warnings(timeout_target)

        entries.append(Entry(
            kind="queue", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            payload={
                "name": name, "strategy": pivoted.get("strategy") or "ringall",
                "moh_class_name": pivoted.get("music") or None,
                "agent_ring_seconds": int(pivoted["timeout"]) if (pivoted.get("timeout") or "").isdigit() else 15,
                "retry_seconds": int(pivoted["retry"]) if (pivoted.get("retry") or "").isdigit() else 5,
                "wrapup_seconds": int(pivoted["wrapuptime"]) if (pivoted.get("wrapuptime") or "").isdigit() else 0,
                "max_wait_seconds": int(row["maxwait"]) if (row.get("maxwait") or "").isdigit() else 0,
                "max_callers": int(pivoted["maxlen"]) if (pivoted.get("maxlen") or "").isdigit() else 0,
                "announce_position": (pivoted.get("announce-position") or "no") == "yes",
                "announce_frequency_seconds": int(pivoted["announce-frequency"]) if (pivoted.get("announce-frequency") or "").isdigit() else 0,
                "sla_seconds": int(pivoted["servicelevel"]) if (pivoted.get("servicelevel") or "").isdigit() else 60,
                "join_empty": (pivoted.get("joinempty") or "no") == "yes",
                "record": (pivoted.get("recording") or "dontcare") in ("force", "yes"),
                "timeout_target_id": target_payload(timeout_target),
                "members": members,
            },
        ))
    return entries
