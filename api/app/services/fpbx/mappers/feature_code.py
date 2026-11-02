"""`featurecodes` (`customcode` bo'sh emas va != `defaultcode`) -> `feature_codes`
(m5a-contract.md §1.2). O'zgartirilmagan (standart) qatorlar — `skip`
`builtin` — Innova o'z standart kodi (jim yo'qolish testi uchun hali Entry); Innova'da
mosi yo'q xususiyatlar — `skip` `no_innova_feature` (shartnomada "ignored" deb
atalgan, bu yerda bitta Entry orqali hisoblanadi — `plan.py` buni `items`da
qoldiradi, chunki u haligacha o'zi "qator" darajasida kuzatiladi)."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, warning

_FEATURE_MAP = {
    ("voicemail", "myvoicemail"): "voicemail",
    ("voicemail", "dialvoicemail"): "voicemail_other",
    ("donotdisturb", "dnd_toggle"): "dnd_toggle",
    ("callforward", "cfon"): "cf_always_on",
    ("callforward", "cfoff"): "cf_always_off",
    ("callforward", "cfbon"): "cf_busy_on",
    ("callforward", "cfboff"): "cf_busy_off",
    ("core", "pickup"): "pickup_direct",
    ("core", "pickupexten"): "pickup_group",
    ("parking", "parkedcall"): "park",
}


def map_feature_code(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    for row in ctx.table("featurecodes"):
        module, feature_name = row.get("modulename") or "", row.get("featurename") or ""
        source_ref = f"featurecodes:{module}.{feature_name}"
        name = row.get("description") or f"{module}.{feature_name}"
        custom = row.get("customcode")
        default = row.get("defaultcode")

        if not custom or custom == "NULL" or custom == default:
            entries.append(Entry(
                kind="feature_code", source_ref=source_ref, name=name, number=None,
                action="skip", reason="builtin",
            ))
            continue

        innova_feature = _FEATURE_MAP.get((module, feature_name))
        if innova_feature is None:
            entries.append(Entry(
                kind="feature_code", source_ref=source_ref, name=name, number=custom,
                action="skip", reason="no_innova_feature",
                warnings=[warning("no_innova_feature", f"Mos keluvchi Innova xususiyati yo'q: {module}.{feature_name}")],
            ))
            continue

        entries.append(Entry(
            kind="feature_code", source_ref=source_ref, name=name, number=custom,
            action="create",
            payload={
                "feature": innova_feature, "code": custom,
                "enabled": (row.get("enabled") or "1") != "0",
            },
        ))
    return entries
