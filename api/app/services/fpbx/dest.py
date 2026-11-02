"""FreePBX manzil-satr grammatikasi (`ext-local,101,1` kabi) -> Innova `call_targets.kind`
(m5a-contract.md §1.1). Sof funksiya — hech qanday I/O, faqat `DestCatalog` orqali berilgan
"nima mavjud" to'plamlariga qarab qaror qiladi (test uchun qulay)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_VM_PREFIXES = ("vmu", "vmb", "vms", "vmi")
_HANGUP_APPS = {"hangup", "congestion", "zapateller", "no-service"}
_UNSUPPORTED_BLACKHOLE = {"ring", "musiconhold"}


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
    if context == "ext-group":
        return DestResult("ring_group", arg)
    if context == "ext-queues":
        return DestResult("queue", arg)
    if context.startswith("ivr-"):
        return DestResult("ivr", context[len("ivr-"):])
    if context == "timeconditions":
        return DestResult("time_condition", arg)
    if context.startswith("app-announcement-"):
        return DestResult("announcement", context[len("app-announcement-"):])
    if context in ("ext-meetme", "ext-conference"):
        return DestResult("conference", arg)
    if context == "ext-findmefollow":
        match = re.fullmatch(r"FM(\d+)", arg)
        return DestResult("extension", match.group(1)) if match else \
            DestResult("hangup", None, ("dest_unsupported", f"Manzil qo'llab-quvvatlanmaydi: {dest}"))
    if context == "ext-miscdests":
        return _resolve_miscdest(arg, catalog)
    if context == "app-blackhole":
        return _resolve_blackhole(arg)
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
