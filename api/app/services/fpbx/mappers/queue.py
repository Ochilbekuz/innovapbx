"""`queues_config` + `queues_details` (EAV, `member` ko'p qiymatli) + astdb
`QPENALTY/<N>/agents/*` (dinamik a'zolar) -> `queues` + `queue_members`
(m5a-contract.md §1.2, proof §4: 2 statik + 1 dinamik a'zo)."""
from __future__ import annotations

from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx import tsv as tsv_mod
from app.services.fpbx.mappers import Ctx, Entry, int_or, target_payload, target_warnings


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


def _dynamic_members(astdb: dict[str, str], number: str) -> list[dict]:
    return [{
        "extension_number": ext, "penalty": int_or(penalty, 0), "dynamic": True,
    } for ext, penalty in astdb_mod.family(astdb, f"QPENALTY/{number}/agents").items()]


def _queue_payload(row: dict, name: str, pivoted: dict, timeout_target, members: list[dict]) -> dict:
    return {
        "name": name, "strategy": pivoted.get("strategy") or "ringall",
        "moh_class_name": pivoted.get("music") or None,
        "agent_ring_seconds": int_or(pivoted.get("timeout"), 15),
        "retry_seconds": int_or(pivoted.get("retry"), 5),
        "wrapup_seconds": int_or(pivoted.get("wrapuptime"), 0),
        "max_wait_seconds": int_or(row.get("maxwait"), 0),
        "max_callers": int_or(pivoted.get("maxlen"), 0),
        "announce_position": (pivoted.get("announce-position") or "no") == "yes",
        "announce_frequency_seconds": int_or(pivoted.get("announce-frequency"), 0),
        "sla_seconds": int_or(pivoted.get("servicelevel"), 60),
        "join_empty": (pivoted.get("joinempty") or "no") == "yes",
        "record": (pivoted.get("recording") or "dontcare") in ("force", "yes"),
        "timeout_target_id": target_payload(timeout_target),
        "members": members,
    }


def map_queue(ctx: Ctx) -> list[Entry]:
    details_by_id = tsv_mod.group_by(ctx.table("queues_details"), "id")
    entries: list[Entry] = []
    for row in ctx.table("queues_config"):
        number = row["extension"]
        source_ref = f"queues_config:{number}"
        name = row.get("descr") or number
        pivoted = tsv_mod.pivot_first(details_by_id.get(number, []))
        entry_warnings: list[dict[str, str]] = []

        members = _static_members(details_by_id.get(number, [])) + _dynamic_members(ctx.astdb, number)

        timeout_target = ctx.resolve(row.get("dest"))
        entry_warnings += target_warnings(timeout_target)

        entries.append(Entry(
            kind="queue", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            payload=_queue_payload(row, name, pivoted, timeout_target, members),
        ))
    return entries
