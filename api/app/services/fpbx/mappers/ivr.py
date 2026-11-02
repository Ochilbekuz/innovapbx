"""`ivr_details` + `ivr_entries` -> `ivrs` + `ivr_options` (m5a-contract.md §1.2)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, ref, target_payload, target_warnings, warning

_DIGIT_OK = set("0123456789*#")


def _audio_ref(recording_id: str | None, recordings_ids: set[str]) -> dict | None:
    if not recording_id or recording_id in ("default", "") or recording_id not in recordings_ids:
        return None
    return ref("audio", recording_id)


def map_ivr(ctx: Ctx) -> list[Entry]:
    recordings_ids = {row["id"] for row in ctx.table("recordings")}
    entries_by_ivr: dict[str, list[dict]] = {}
    for row in ctx.table("ivr_entries"):
        entries_by_ivr.setdefault(row["ivr_id"], []).append(row)

    entries: list[Entry] = []
    for row in ctx.table("ivr_details"):
        ivr_id = row["id"]
        source_ref = f"ivr_details:{ivr_id}"
        name = row.get("name") or ivr_id
        entry_warnings: list[dict[str, str]] = []

        greeting = _audio_ref(row.get("announcement"), recordings_ids)
        invalid_audio = _audio_ref(row.get("invalid_recording"), recordings_ids)
        # Eslatma: Ivr modelida alohida "timeout audio" ustuni yo'q — FreePBX'ning
        # `timeout_recording`i Innova'da qo'llab-quvvatlanmaydi (ogohlantirmaymiz,
        # chunki fixture'da standart "default" qiymat, farq yo'q).

        invalid_loops = int(row["invalid_loops"]) if (row.get("invalid_loops") or "").isdigit() else 0
        timeout_loops = int(row["timeout_loops"]) if (row.get("timeout_loops") or "").isdigit() else 0
        repeats = max(invalid_loops, timeout_loops) or 1

        timeout_seconds = int(row["timeout_time"]) if (row.get("timeout_time") or "").isdigit() else 10
        direct_dial = bool(row.get("directdial"))

        invalid_target = ctx.resolve(row.get("invalid_destination"))
        timeout_target = ctx.resolve(row.get("timeout_destination"))
        entry_warnings += target_warnings(invalid_target) + target_warnings(timeout_target)

        options = []
        for entry_row in entries_by_ivr.get(ivr_id, []):
            digit = entry_row.get("selection") or ""
            if digit not in _DIGIT_OK:
                entry_warnings.append(warning("ivr_digit_unsupported", f"IVR tanlov qo'llab-quvvatlanmaydi: {digit}"))
                continue
            target = ctx.resolve(entry_row.get("dest"))
            entry_warnings += target_warnings(target)
            options.append({"digit": digit, "target_id": target_payload(target)})

        entries.append(Entry(
            kind="ivr", source_ref=source_ref, name=name, number=None,
            action="create", warnings=entry_warnings,
            payload={
                "name": name, "greeting_audio_id": greeting, "invalid_audio_id": invalid_audio,
                "timeout_seconds": timeout_seconds, "repeats": repeats, "direct_dial": direct_dial,
                "timeout_target_id": target_payload(timeout_target),
                "invalid_target_id": target_payload(invalid_target),
                "options": options,
            },
        ))
    return entries
