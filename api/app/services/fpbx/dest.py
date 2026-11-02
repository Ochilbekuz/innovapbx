"""FreePBX manzil-satr grammatikasi (`ext-local,101,1` kabi) -> Innova `call_targets.kind`
(m5a-contract.md §1.1). Sof funksiya — hech qanday I/O, faqat `DestCatalog` orqali berilgan
"nima mavjud" to'plamlariga qarab qaror qiladi (test uchun qulay)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_VM_PREFIXES = ("vmu", "vmb", "vms", "vmi")
_HANGUP_APPS = {"hangup", "congestion", "zapateller", "no-service"}
_UNSUPPORTED_BLACKHOLE = {"ring", "musiconhold"}

# `resolve_dest`da bir xil shaklga ega ("context -> DestResult(kind, arg)") 4 ta
# alohida `if` o'rniga BITTA lug'at qarashi (CRAP: har bir `if` resolve_dest'ning
# CC'siga qo'shilardi — birlashtirilgach, xatti-harakat bir xil qoladi).
_EXACT_KIND = {
    "ext-group": "ring_group",
    "ext-queues": "queue",
    "timeconditions": "time_condition",
    "ext-meetme": "conference",
    "ext-conference": "conference",
}

# Prefiksga qarab kesib olinadigan kalit (`ivr-42` -> `ivr`/`42`).
_PREFIX_KIND = (("ivr-", "ivr"), ("app-announcement-", "announcement"))


@dataclass
class DestCatalog:
    """m5a-contract.md §1.1 resolver uchun "nima mavjud" to'plamlari."""

    extensions: frozenset[str] = frozenset()
    ring_groups: frozenset[str] = frozenset()
    queues: frozenset[str] = frozenset()
    ivrs: frozenset[str] = frozenset()
    time_conditions: frozenset[str] = frozenset()
    announcements: frozenset[str] = frozenset()
    conferences: frozenset[str] = frozenset()
    voicemail_boxes: frozenset[str] = frozenset()
    miscdests: dict[str, str] = field(default_factory=dict)


@dataclass
class DestResult:
    """`kind` — `call_targets.kind` qiymati (yoki "hangup"/"busy"); `ref` — shu turdagi
    obyektni aniqlovchi manba kalit (raqam/id); `warning` — `(code, message)` yoki `None`."""

    kind: str
    ref: str | None = None
    warning: tuple[str, str] | None = None


def _split(dest: str) -> list[str]:
    return dest.split(",")


def _internal_fallback(num: str, catalog: DestCatalog) -> DestResult:
    if num in catalog.extensions:
        return DestResult("extension", num)
    if num in catalog.ring_groups:
        return DestResult("ring_group", num)
    if num in catalog.queues:
        return DestResult("queue", num)
    return DestResult("hangup", None, ("dest_unsupported", f"Manzil qo'llab-quvvatlanmaydi: {num}"))


def _resolve_findmefollow(arg: str, dest: str) -> DestResult:
    match = re.fullmatch(r"FM(\d+)", arg)
    if match:
        return DestResult("extension", match.group(1))
    return DestResult("hangup", None, ("dest_unsupported", f"Manzil qo'llab-quvvatlanmaydi: {dest}"))


def _resolve_prefixed(context: str) -> DestResult | None:
    for prefix, kind in _PREFIX_KIND:
        if context.startswith(prefix):
            return DestResult(kind, context[len(prefix):])
    return None


# "context -> (arg, catalog, dest) dan DestResult quradi" shaklidagi, bitta aniq
# kalitga mos keluvchi hodisalar — uch alohida `if`/`==` o'rniga BITTA lug'at
# qarashi (xatti-harakat bir xil, resolve_dest'ning CC'si pasayadi).
_CALL_HANDLERS = {
    "ext-findmefollow": lambda arg, catalog, dest: _resolve_findmefollow(arg, dest),
    "ext-miscdests": lambda arg, catalog, dest: _resolve_miscdest(arg, catalog),
    "app-blackhole": lambda arg, catalog, dest: _resolve_blackhole(arg),
}


def resolve_dest(dest: str | None, catalog: DestCatalog) -> DestResult | None:
    """Bo'sh/`None` manzil uchun `None` qaytaradi — chaqiruvchi o'zining sukut qiymatini
    tanlaydi (masalan "no_answer_target_id yo'q" — CFU yo'q bo'lsa boshqa manbadan)."""
    if not dest:
        return None
    parts = _split(dest)
    context = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if context in ("ext-local", "from-did-direct"):
        return _resolve_ext_local(arg, catalog)
    if context in _EXACT_KIND:
        return DestResult(_EXACT_KIND[context], arg)
    prefixed = _resolve_prefixed(context)
    if prefixed is not None:
        return prefixed
    handler = _CALL_HANDLERS.get(context)
    if handler is not None:
        return handler(arg, catalog, dest)
    if context in ("from-internal", "from-trunk"):
        return _internal_fallback(arg, catalog)
    return DestResult("hangup", None, ("dest_unsupported", f"Manzil qo'llab-quvvatlanmaydi: {dest}"))


def _resolve_ext_local(arg: str, catalog: DestCatalog) -> DestResult:
    for prefix in _VM_PREFIXES:
        if arg.startswith(prefix) and arg[len(prefix):].isdigit():
            number = arg[len(prefix):]
            if number in catalog.voicemail_boxes:
                return DestResult("voicemail", number)
            return DestResult("extension", number,
                               ("voicemail_missing", f"Ovozli pochta {number} topilmadi, raqamga o'tkazildi"))
    return DestResult("extension", arg)


def _resolve_miscdest(misc_id: str, catalog: DestCatalog) -> DestResult:
    destdial = catalog.miscdests.get(misc_id)
    if destdial:
        inner = resolve_dest(destdial, catalog)
        if inner is not None and inner.kind != "hangup":
            return inner
    return DestResult("external", destdial or "")


def _resolve_blackhole(arg: str) -> DestResult:
    if arg in _HANGUP_APPS:
        return DestResult("hangup")
    if arg == "busy":
        return DestResult("busy")
    if arg in _UNSUPPORTED_BLACKHOLE:
        return DestResult("hangup", None, ("blackhole_unsupported", f"'{arg}' qo'llab-quvvatlanmaydi, uzildi"))
    return DestResult("hangup", None, ("dest_unsupported", f"Noma'lum blackhole: {arg}"))
