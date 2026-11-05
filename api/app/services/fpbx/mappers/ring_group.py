"""`ringgroups` -> `ring_groups` + `ring_group_members` (m5a-contract.md §1.2).

0038 (FreePBX Ring Groups parity — hisobot `docs/qollanma/ringgroups.md`):
`annmsg_id`/`alertinfo`/`remotealert_id`/`needsconf`/`ringing`/`recording`
ustunlari HAM ko'chiriladi. QASDAN KO'CHIRILMAGAN: `cwignore`/`cfignore`/
`cpickup`/`toolate_id` — mos Innova xususiyati yo'q (semantikasi noaniq/
ishlatilmagan), `changecid`/`fixedcid` — bu ustunlar haqiqiy FreePBX
`ringgroups` jadvalida UMUMAN YO'Q (ixtiro qilinmaydi)."""
from __future__ import annotations

import re

from app.services.fpbx.mappers import Ctx, Entry, int_or, ref, target_payload, target_warnings, warning

_STRATEGY = {
    "ringall": "ringall", "ringall-prim": "ringall-prim",
    "hunt": "hunt", "hunt-prim": "hunt-prim",
    "memoryhunt": "memoryhunt", "memoryhunt-prim": "memoryhunt-prim",
    "firstavailable": "firstavailable", "firstnotonphone": "firstnotonphone",
}
_RECORDING = {"force": "force", "yes": "force", "dontcare": "dontcare", "no": "no"}
_TRUE = frozenset({"1", "yes", "true"})
# `app/schemas.py::_ALERT_INFO_PATTERN`/`app/services/compiler.py::_ALERT_INFO_RE`
# bilan ATAYLAB BIR XIL (himoya qatlami — shu fayl ikkisidan mustaqil).
_ALERT_INFO_RE = re.compile(r"^[A-Za-z0-9=<>:;/._@-]{1,128}$")


def _strategy(raw: str | None) -> tuple[str, bool]:
    mapped = _STRATEGY.get(raw or "")
    if mapped:
        return mapped, False
    return "ringall", True


def _audio_ref(raw_id: str | None) -> dict | None:
    """`annmsg_id`/`remotealert_id` — FreePBX'da "0"/bo'sh "yo'q" degani."""
    if not raw_id or raw_id == "0":
        return None
    return ref("audio", raw_id)


def _alert_info(raw: str | None) -> tuple[str | None, bool]:
    if not raw:
        return None, False
    if not _ALERT_INFO_RE.fullmatch(raw):
        return None, True
    return raw, False


def _ring_sound(raw_ringing: str | None, music_names: dict[str, str]) -> tuple[str, str | None, bool]:
    """`ringing` — "0"/bo'sh: oddiy jiringlash; aks holda `music.id` havolasi
    (FreePBX "Play Music On Hold?" tanlovi) — topilmasa ogohlantirib oddiy
    jiringlashga qaytadi."""
    if not raw_ringing or raw_ringing == "0":
        return "ring", None, False
    name = music_names.get(raw_ringing)
    if name is None:
        return "ring", None, True
    return "moh", name, False


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
    music_names = {row["id"]: (row.get("category") or row["id"]) for row in ctx.table("music")}
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

        grptime = int_or(row.get("grptime"), 20)
        ring_seconds = max(5, min(300, grptime))

        target = ctx.resolve(row.get("postdest"))
        entry_warnings += target_warnings(target)

        alert_info, bad_alert_info = _alert_info(row.get("alertinfo"))
        if bad_alert_info:
            entry_warnings.append(warning(
                "alert_info_invalid", f"Alert-Info formati noto'g'ri '{row.get('alertinfo')}' -> o'tkazib yuborildi"))

        ring_strategy_sound, moh_class_name, bad_moh = _ring_sound(row.get("ringing"), music_names)
        if bad_moh:
            entry_warnings.append(warning(
                "moh_class_missing", f"MOH sinfi topilmadi (ringing={row.get('ringing')}) -> oddiy jiringlash"))

        entries.append(Entry(
            kind="ring_group", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            payload={
                "name": name, "strategy": strategy, "ring_seconds": ring_seconds,
                "no_answer_target_id": target_payload(target),
                "callerid_prefix": row.get("grppre") or None,
                "members": _members(ctx, row.get("grplist")),
                # 0038 — FreePBX Ring Groups parity qo'shimchalari.
                "announcement_audio_id": _audio_ref(row.get("annmsg_id")),
                "alert_info": alert_info,
                "ring_strategy_sound": ring_strategy_sound,
                "moh_class_name": moh_class_name,
                "confirm_calls": (row.get("needsconf") or "0") in _TRUE,
                "remote_announce_audio_id": _audio_ref(row.get("remotealert_id")),
                "recording_policy": _RECORDING.get(row.get("recording") or "dontcare", "dontcare"),
            },
        ))
    return entries
