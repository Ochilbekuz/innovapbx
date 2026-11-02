"""`outbound_routes` + `_patterns` + `_trunks(seq)` + `_sequence` -> `outbound_routes`
+ `outbound_route_patterns` + `outbound_route_trunks(position=seq)`
(m5a-contract.md §1.2). `outbound_route_sequence.seq` = marshrut ustuvorligi
(`priority`); `outbound_route_trunks.seq` = o'sha marshrut ICHIDAGI trunk
failover tartibi (`position`) — ikkisi ALOHIDA tushuncha."""
from __future__ import annotations

from app.services.fpbx import tsv as tsv_mod
from app.services.fpbx.mappers import Ctx, Entry, ref, warning, weak_secret


def _ordered_trunk_refs(trunks_by_route: dict[str, list[dict]], trunk_ids: set[str],
                         route_id: str, entry_warnings: list[dict[str, str]]) -> list[dict]:
    """`outbound_route_trunks.seq` bo'yicha tartiblangan failover ro'yxati —
    o'chirilgan/topilmagan trunk tashlanadi (ogohlantirib)."""
    ordered_trunks = sorted(trunks_by_route.get(route_id, []), key=lambda r: int(r["seq"]))
    trunk_refs = []
    for trunk_row in ordered_trunks:
        trunk_id = trunk_row["trunk_id"]
        if trunk_id not in trunk_ids:
            entry_warnings.append(warning("trunk_missing", f"Trunk topilmadi: {trunk_id}"))
            continue
        trunk_refs.append(ref("trunk", trunk_id))
    return trunk_refs


def _warn_unsupported_route_options(row: dict, entry_warnings: list[dict[str, str]]) -> None:
    """Innova'da yo'q 2 FreePBX sozlamasi (`emergency_route`/`time_group_id`) —
    standart (OFF/0) bo'lmasa, qisman xaritalanish haqida ogohlantiramiz."""
    if (row.get("emergency_route") or "OFF") != "OFF":
        entry_warnings.append(warning("partial_mapping", "emergency_route Innova'da qo'llab-quvvatlanmaydi"))
    if (row.get("time_group_id") or "0") != "0":
        entry_warnings.append(warning("partial_mapping", "time_group_id (marshrut jadvali) Innova'da qo'llab-quvvatlanmaydi"))


def _route_patterns(patterns_by_route: dict[str, list[dict]], route_id: str) -> list[dict]:
    return [{
        "strip_prefix": p.get("match_pattern_prefix") or None,
        "pattern": p.get("match_pattern_pass") or None,
        "add_prefix": p.get("prepend_digits") or None,
        "callerid_match": p.get("match_cid") or None,
    } for p in patterns_by_route.get(route_id, [])]


def map_outbound_route(ctx: Ctx) -> list[Entry]:
    patterns_by_route = tsv_mod.group_by(ctx.table("outbound_route_patterns"), "route_id")
    trunks_by_route = tsv_mod.group_by(ctx.table("outbound_route_trunks"), "route_id")
    priority_by_route = {row["route_id"]: row["seq"] for row in ctx.table("outbound_route_sequence")}
    trunk_ids = {row["trunkid"] for row in ctx.table("trunks")}

    entries: list[Entry] = []
    for row in ctx.table("outbound_routes"):
        route_id = row["route_id"]
        source_ref = f"outbound_routes:{route_id}"
        name = row.get("name") or route_id
        entry_warnings: list[dict[str, str]] = []

        trunk_refs = _ordered_trunk_refs(trunks_by_route, trunk_ids, route_id, entry_warnings)
        if not trunk_refs:
            entries.append(Entry(
                kind="outbound_route", source_ref=source_ref, name=name, number=None,
                action="skip", reason="no_trunk_left", warnings=entry_warnings,
            ))
            continue

        _warn_unsupported_route_options(row, entry_warnings)

        password = row.get("password")
        patterns = _route_patterns(patterns_by_route, route_id)

        entries.append(Entry(
            kind="outbound_route", source_ref=source_ref, name=name, number=None,
            action="create", warnings=entry_warnings,
            has_secret=bool(password), weak_secret=weak_secret(password, equals_number=None),
            payload={
                "name": name, "priority": int(priority_by_route.get(route_id, "0") or "0"),
                "callerid": row.get("outcid") or None,
                "override_extension_callerid": (row.get("outcid_mode") or "").upper() == "ALLOW",
                "pin_plain": password,
                "international": False,
                "enabled": True,
                "patterns": patterns,
                "trunks": trunk_refs,
            },
        ))
    return entries
