"""`meetme` -> `conferences` (m5a-contract.md §1.2, §1.1 stendda sinalmagan —
unit test bilan tasdiqlanadi)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, weak_secret


def map_conference(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for row in ctx.table("meetme"):
        number = row["exten"]
        source_ref = f"meetme:{number}"
        name = row.get("description") or number
        user_pin, admin_pin = row.get("userpin"), row.get("adminpin")

        entries.append(Entry(
            kind="conference", source_ref=source_ref, name=name, number=number,
            action="create",
            has_secret=bool(user_pin or admin_pin),
            weak_secret=weak_secret(user_pin, equals_number=number) or weak_secret(admin_pin, equals_number=number),
            payload={
                "name": name, "pin_plain": user_pin, "admin_pin_plain": admin_pin,
                "record": False,
                "max_members": int(row["users"]) if (row.get("users") or "0").isdigit() and row.get("users") != "0" else None,
            },
        ))
    return entries
