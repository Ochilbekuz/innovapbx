"""`ringgroups` -> `ring_groups` + `ring_group_members` (m5a-contract.md §1.2)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, target_payload, target_warnings, warning

_STRATEGY = {"ringall": "ringall", "hunt": "hunt", "memoryhunt": "memoryhunt"}


def _strategy(raw: str | None) -> tuple[str, bool]:
    for prefix, mapped in _STRATEGY.items():
        if (raw or "").startswith(prefix):
            return mapped, False
    return "ringall", True


def _members(ctx: Ctx, grplist: str | None) -> list[dict]:
    members = []
    for item in (grplist or "").split("-"):
        number = item.strip().rstrip("#")
        if not number:
            continue
        if number in ctx.catalog.extensions:
            members.append({"extension_number": number, "external_number": None})
        else:
            members.append({"extension_number": None, "external_number": number})
    return members


def map_ring_group(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for row in ctx.table("ringgroups"):
        number = row["grpnum"]
        source_ref = f"ringgroups:{number}"
        name = row.get("description") or number
        entry_warnings: list[dict[str, str]] = []

        strategy, bad_strategy = _strategy(row.get("strategy"))
        if bad_strategy:
            entry_warnings.append(warning(
                "strategy_unsupported", f"Noma'lum strategiya '{row.get('strategy')}' -> ringall"))

        grptime = int(row["grptime"]) if (row.get("grptime") or "").isdigit() else 20
        ring_seconds = max(5, min(300, grptime))

        target = ctx.resolve(row.get("postdest"))
        entry_warnings += target_warnings(target)

        entries.append(Entry(
            kind="ring_group", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            payload={
                "name": name, "strategy": strategy, "ring_seconds": ring_seconds,
                "no_answer_target_id": target_payload(target),
                "callerid_prefix": row.get("grppre") or None,
                "members": _members(ctx, row.get("grplist")),
            },
        ))
    return entries
