"""`users` + `devices` + `sip` (EAV, PJSIP ham shu yerda!) + astdb `AMPUSER/<N>/*`
-> `extensions` + `dial_numbers` + `call_targets(extension)` (m5a-contract.md §1.2).
Yo'naltirish (`CF`/`CFB`/`CFU`/`DND`, keyingi qator) va Follow Me (`findmefollow`,
keyingi qator) shu bitta ichki raqam `Entry`'siga birlashtiriladi — `CW` esa
Innova'da sozlanmaydigan sifatida ataylab o'qilmaydi/e'tiborsiz qoldiriladi."""
from __future__ import annotations

import re

from app.schemas_follow_me import FOLLOW_ME_MAX_NUMBERS, follow_me_default
from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx.mappers import Ctx, Entry, ref, warning, weak_secret

_KNOWN_CODECS = {"ulaw", "alaw", "g722", "opus"}
_SUPPORTED_TECH = {"pjsip", "sip"}
_FORWARD_NUMBER_RE = re.compile(r"^[0-9]{2,15}$")


def _codecs(allow: str | None) -> tuple[list[str], bool]:
    raw = [c.strip() for c in (allow or "").split(",") if c.strip()]
    known = [c for c in raw if c in _KNOWN_CODECS]
    return known, len(known) != len(raw)


def _max_contacts(value: str | None) -> int:
    n = int(value) if (value or "").isdigit() else 1
    return max(1, min(10, n))


def _ringtimer(value: str | None) -> tuple[int, bool]:
    n = int(value) if (value or "").isdigit() else 0
    if n == 0:
        return 25, False
    clamped = max(5, min(120, n))
    return clamped, clamped != n


def _outbound_callerid(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"<([^>]+)>", raw)
    return (match.group(1) if match else raw).strip() or None


def _recording_mode_for(ampuser: dict[str, str], direction: str) -> str:
    """AMPUSER'da yo'nalish BO'YICHA 2 kalit (`internal`/`external`) bor — boshqa
    yo'nalishning kalitlariga tegilmaydi (M3c §1: `in`/`out` mustaqil siyosat)."""
    values = [ampuser.get(f"recording/{direction}/{side}", "") for side in ("internal", "external")]
    if any(v in ("force", "yes") for v in values):
        return "always"
    if all(v in ("never", "no") for v in values):
        return "never"
    return "on_demand"


def _forward_number(raw: str | None, entry_warnings: list[dict[str, str]]) -> str | None:
    if not raw:
        return None
    cleaned = raw.lstrip("+")
    if not _FORWARD_NUMBER_RE.match(cleaned):
        entry_warnings.append(warning("forward_number_invalid", f"Yo'naltirish raqami noto'g'ri: {raw}"))
        return None
    return cleaned


def _no_answer_target(raw: str | None, ctx: Ctx) -> dict | None:
    """CFU: ichki raqamga -> shu raqamning `extension` targeti, aks holda tashqi."""
    if not raw:
        return None
    cleaned = raw.lstrip("+")
    if cleaned in ctx.catalog.extensions:
        return ref("extension", cleaned)
    if not _FORWARD_NUMBER_RE.match(cleaned):
        return None
    return {"kind": "external", "number": cleaned}


_FM_NUMBER_RE = re.compile(r"^[0-9]{2,15}$")


def _fm_strategy(raw: str | None, entry_warnings: list[dict[str, str]]) -> str:
    """`ringall*` -> `ring_all`; `hunt*`/`memoryhunt*`/`firstavailable`... -> `sequential` (ogohlantirish bilan)."""
    strategy = (raw or "ringallv2").strip()
    if strategy.startswith("ringall"):
        return "ring_all"
    if not strategy.startswith("hunt"):
        entry_warnings.append(warning("partial_mapping", f"Follow Me strategiyasi {strategy} -> ketma-ket"))
    return "sequential"


def _fm_numbers(number: str, grplist: str, entry_warnings: list[dict[str, str]]) -> tuple[list[str], bool]:
    """`grplist` (`101-0901234567#`) -> (raqamlar, o'z raqami ro'yxatdami)."""
    numbers: list[str] = []
    include_extension = False
    for raw_item in grplist.split("-"):
        item = raw_item.strip().rstrip("#").lstrip("+")
        if item == number:
            include_extension = True
        elif item and item not in numbers:
            if _FM_NUMBER_RE.match(item):
                numbers.append(item)
            else:
                entry_warnings.append(warning("partial_mapping", f"Follow Me: noto'g'ri raqam tashlandi: {item}"))
    if len(numbers) > FOLLOW_ME_MAX_NUMBERS:
        entry_warnings.append(warning(
            "partial_mapping", f"Follow Me: {len(numbers)} raqamdan faqat {FOLLOW_ME_MAX_NUMBERS} tasi olindi"))
    return numbers[:FOLLOW_ME_MAX_NUMBERS], include_extension


def _fm_ring_seconds(raw: object) -> int:
    text = str(raw or "")
    return max(5, min(120, int(text))) if text.isdigit() else 20


def _follow_me(number: str, findmefollow_by_ext: dict[str, dict], ddial: str | None,
               entry_warnings: list[dict[str, str]]) -> dict:
    """`findmefollow` + astdb `AMPUSER/<N>/followme/ddial` -> `follow_me`. FreePBX'da faqat `DIRECT` = yoqilgan
    (kalit yo'q yoki `EXTENSION` — dialplan ichki raqamni to'g'ridan teradi, `FOLLOWME_DISABLED` standarti).
    FreePBX'da Follow Me qo'ng'iroqni darhol oladi (`pre_ring`), Innova'da — ichki raqam javob bermagach."""
    row = findmefollow_by_ext.get(number)
    if row is None:
        return follow_me_default()
    numbers, include_extension = _fm_numbers(number, row.get("grplist") or "", entry_warnings)
    entry_warnings.append(warning(
        "partial_mapping", "Follow Me: Innova'da ichki raqam javob bermagach ishga tushadi (pre_ring yo'q)"))
    return {"enabled": bool(numbers) and (ddial or "").upper() == "DIRECT", "numbers": numbers,
            "strategy": _fm_strategy(row.get("strategy"), entry_warnings), "include_extension": include_extension,
            "ring_seconds": _fm_ring_seconds(row.get("grptime")), "confirm": row.get("needsconf") == "CHECKED"}


def map_extension(ctx: Ctx) -> list[Entry]:
    devices_by_id = {row["id"]: row for row in ctx.table("devices")}
    sip_by_id = ctx.eav("sip")
    findmefollow_by_ext = {row["grpnum"]: row for row in ctx.table("findmefollow")}
    cf = astdb_mod.top_level(ctx.astdb, "CF")
    cfb = astdb_mod.top_level(ctx.astdb, "CFB")
    cfu = astdb_mod.top_level(ctx.astdb, "CFU")
    dnd = astdb_mod.top_level(ctx.astdb, "DND")

    entries: list[Entry] = []
    for row in ctx.table("users"):
        number = row["extension"]
        source_ref = f"users:{number}"
        name = row.get("name") or number
        device = devices_by_id.get(number)

        if device is None or device.get("tech") not in _SUPPORTED_TECH:
            tech = device.get("tech") if device else None
            entries.append(Entry(
                kind="extension", source_ref=source_ref, name=name, number=number,
                action="unsupported", reason="device_tech_unsupported",
                warnings=[warning("device_tech_unsupported",
                                   f"Qo'llab-quvvatlanmaydigan qurilma turi: {tech}")],
            ))
            continue

        sip = sip_by_id.get(number, {})
        ampuser = astdb_mod.family(ctx.astdb, f"AMPUSER/{number}")
        entry_warnings: list[dict[str, str]] = []

        secret = sip.get("secret")
        codecs, codecs_dropped = _codecs(sip.get("allow"))
        if codecs_dropped:
            entry_warnings.append(warning(
                "codec_unsupported", f"Innova qo'llab-quvvatlamaydigan kodek(lar) tashlandi: {sip.get('allow')}"))

        ringtimer, ring_clamped = _ringtimer(row.get("ringtimer"))
        if ring_clamped:
            entry_warnings.append(warning(
                "ring_seconds_clamped", f"ringtimer {row.get('ringtimer')} -> {ringtimer}"))

        forward_always = _forward_number(cf.get(number), entry_warnings)
        forward_busy = _forward_number(cfb.get(number), entry_warnings)
        no_answer_target_id = _no_answer_target(cfu.get(number), ctx)
        follow_me = _follow_me(number, findmefollow_by_ext, ampuser.get("followme/ddial"), entry_warnings)

        entries.append(Entry(
            kind="extension", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            has_secret=bool(secret), weak_secret=weak_secret(secret, equals_number=number),
            payload={
                "number": number, "name": name,
                "secret_plain": secret,
                "codecs": codecs,
                "max_contacts": _max_contacts(sip.get("max_contacts")),
                "outbound_callerid": _outbound_callerid(row.get("outboundcid")),
                "ringtimer": ringtimer,
                "recording": _recording_mode_for(ampuser, "in"),
                "recording_out": _recording_mode_for(ampuser, "out"),
                "dnd": (dnd.get(number) or "").upper() == "YES",
                "forward_always": forward_always,
                "forward_busy": forward_busy,
                "no_answer_target_id": no_answer_target_id,
                "follow_me": follow_me,
            },
        ))
    return entries
