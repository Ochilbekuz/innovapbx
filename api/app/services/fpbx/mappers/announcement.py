"""`announcement` -> `announcements` (m5a-contract.md §1.2)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, ref, target_payload, target_warnings, warning


def map_announcement(ctx: Ctx) -> list[Entry]:
    recordings_ids = {row["id"] for row in ctx.table("recordings")}
    entries: list[Entry] = []
    for row in ctx.table("announcement"):
        ann_id = row["announcement_id"]
        source_ref = f"announcement:{ann_id}"
        name = row.get("description") or ann_id
        recording_id = row.get("recording_id")
        entry_warnings: list[dict[str, str]] = []

        if not recording_id or recording_id not in recordings_ids:
            audio_ref, action, reason = None, "skip", "audio_missing"
            entry_warnings.append(warning("audio_missing", f"E'lon audiosi topilmadi: {recording_id}"))
        else:
            audio_ref, action, reason = ref("audio", recording_id), "create", None

        target = ctx.resolve(row.get("post_dest"))
        entry_warnings += target_warnings(target)
        for flag, label in (("allow_skip", "allow_skip"), ("repeat_msg", "repeat_msg"), ("return_ivr", "return_ivr")):
            if (row.get(flag) or "0") != "0":
                entry_warnings.append(warning("partial_mapping", f"E'lon '{label}' Innova'da qo'llab-quvvatlanmaydi"))

        entries.append(Entry(
            kind="announcement", source_ref=source_ref, name=name, number=None,
            action=action, reason=reason, warnings=entry_warnings,
            payload={"name": name, "audio_file_id": audio_ref, "next_target_id": target_payload(target)},
        ))
    return entries
