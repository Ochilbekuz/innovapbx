"""M4a §2 — avtoprovizioning lug'ati (sof funksiyalar, bazasiz): MAC normallashtirish, User-Agent tahlili,
so'rov fayl nomi tahlili, qo'llab-quvvatlanadigan modellar ro'yxati.

Lug'at:
  * **MAC** — 12 ta kichik hex belgi (`805ec0aabbcc`); kirishda `AA:BB-..`/`aabb.ccdd.eeff` ham qabul qilinadi.
  * **umumiy fayl** (`common`) — model bo'yicha umumiy, SIRSIZ config (Yealink `y0000000000xx.cfg`).
  * **apparat fayli** (`device`) — MAC'ga xos, SIP paroli shu faylda (faqat ro'yxatdagi MAC'ga).
  * **legacy_binary** — Grandstream eski firmware'ining `cfg<mac>` (xml'siz, shifrlangan binar) so'rovi — 404.

`keys` (dastur tugmalari soni) — ishlab chiqaruvchi ma'lumotnomasidan TAXMINIY (sahifalar bilan); jonli apparatda
TEKSHIRILMAGAN — UI faqat BLF tahrirlovchida yuqori chegara sifatida ishlatadi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Vendor = Literal["yealink", "grandstream", "fanvil"]
VENDORS: tuple[Vendor, ...] = ("yealink", "grandstream", "fanvil")
MAX_KEYS = 60


@dataclass(frozen=True)
class PhoneModel:
    vendor: Vendor
    model: str
    keys: int
    family: str


def _models(vendor: Vendor, family: str, spec: str) -> list[PhoneModel]:
    """`"T31P:2 T33G:4"` → modellar (jadvalni ixcham saqlash uchun)."""
    out = []
    for item in spec.split():
        name, keys = item.split(":")
        out.append(PhoneModel(vendor, name, int(keys), family))
    return out


MODELS: tuple[PhoneModel, ...] = tuple(
    _models("yealink", "T3x", "T30P:0 T31P:2 T31G:2 T33G:4 T34W:4")
    + _models("yealink", "T4x", "T41S:15 T42S:15 T46S:27 T48S:29 T42U:15 T43U:21 T44U:21 T46U:27 T48U:29")
    + _models("yealink", "T5x", "T53W:21 T54W:27 T57W:29 T58W:27")
    + _models("grandstream", "GXP16xx", "GXP1610:0 GXP1615:0 GXP1620:2 GXP1625:2 GXP1628:8 GXP1630:8")
    + _models("grandstream", "GXP17xx", "GXP1760:6 GXP1780:8 GXP1782:8")
    + _models("grandstream", "GXP21xx", "GXP2130:8 GXP2135:8 GXP2140:4 GXP2160:24 GXP2170:12")
    + _models("grandstream", "GRP26xx", "GRP2612:16 GRP2613:24 GRP2614:24 GRP2615:40 GRP2616:40")
    + _models("fanvil", "X1", "X1S:2 X1SP:2")
    + _models("fanvil", "X3", "X3S:2 X3SP:2 X3U:6")
    + _models("fanvil", "X4", "X4U:12")
    + _models("fanvil", "X5", "X5U:16")
    + _models("fanvil", "X6", "X6U:20")
    + _models("fanvil", "X7", "X7:30 X7C:30")
)
_BY_KEY = {(m.vendor, m.model.upper()): m for m in MODELS}


def find_model(vendor: str | None, model: str | None) -> PhoneModel | None:
    if not vendor or not model:
        return None
    return _BY_KEY.get((vendor, model.strip().upper()))


# ------------------------------------------------------------ MAC
_MAC_SEPARATORS = re.compile(r"[\s:.\-]")
_MAC_RE = re.compile(r"^[0-9a-f]{12}$")


class InvalidMac(ValueError):
    pass


def normalize_mac(raw: str) -> str:
    """`AA:BB:CC:DD:EE:FF` / `aa-bb-..` / `aabb.ccdd.eeff` / `AABBCCDDEEFF` → `aabbccddeeff`."""
    value = _MAC_SEPARATORS.sub("", raw or "").lower()
    if not _MAC_RE.fullmatch(value) or value == "000000000000":
        raise InvalidMac(raw)
    return value


def try_mac(raw: str | None) -> str | None:
    try:
        return normalize_mac(raw or "")
    except InvalidMac:
        return None


# ------------------------------------------------------------ User-Agent
@dataclass(frozen=True)
class UaInfo:
    vendor: Vendor | None = None
    model: str | None = None
    firmware: str | None = None
    mac: str | None = None


# Namuna satrlar — m4a-contract.md §2 (jonli apparatda TEKSHIRILMAGAN, ishlab chiqaruvchi hujjatlaridagi shakl):
#   `Yealink SIP-T46U 108.86.0.20 805ec0aabbcc`
#   `Grandstream Model HW GXP2170 SW 1.0.11.3 DevId c074ad112233`
#   `Fanvil X4U 2.12.1 0c383e112233`
_UA_PATTERNS: tuple[tuple[Vendor, re.Pattern[str]], ...] = (
    ("yealink", re.compile(r"^Yealink\s+(?:SIP-)?(?P<model>[\w-]+)\s+(?P<fw>[\w.]+)(?:\s+(?P<mac>[0-9A-Fa-f:]{12,17}))?",
                           re.IGNORECASE)),
    ("grandstream", re.compile(r"^Grandstream\s+Model\s+HW\s+(?P<model>[\w-]+)\s+SW\s+(?P<fw>[\w.]+)"
                               r"(?:\s+DevId\s+(?P<mac>[0-9A-Fa-f:]{12,17}))?", re.IGNORECASE)),
    ("fanvil", re.compile(r"^Fanvil\s+(?P<model>[\w-]+)\s+(?P<fw>[\w.]+)(?:\s+(?P<mac>[0-9A-Fa-f:]{12,17}))?",
                          re.IGNORECASE)),
)


def parse_user_agent(ua: str | None) -> UaInfo:
    """Noma'lum UA → bo'sh `UaInfo` (xato emas — apparat baribir jurnalga yoziladi)."""
    text = (ua or "").strip()
    for vendor, pattern in _UA_PATTERNS:
        match = pattern.match(text)
        if match:
            return UaInfo(vendor=vendor, model=match.group("model").upper(), firmware=match.group("fw"),
                          mac=try_mac(match.group("mac")))
    return UaInfo()


# ------------------------------------------------------------ so'rov fayli
FileKind = Literal["common", "device_cfg", "device_xml", "legacy_binary", "unknown"]


@dataclass(frozen=True)
class ProvFile:
    kind: FileKind
    mac: str | None = None


_COMMON_RE = re.compile(r"^y0{10}[0-9a-f]{2}\.cfg$")
_DEVICE_CFG_RE = re.compile(r"^(?P<mac>[0-9a-f]{12})\.cfg$")
_DEVICE_XML_RE = re.compile(r"^cfg(?P<mac>[0-9a-f]{12})\.xml$")
_LEGACY_RE = re.compile(r"^cfg(?P<mac>[0-9a-f]{12})$")


def parse_filename(filename: str) -> ProvFile:
    """`y000000000000.cfg` (va `y0000000000xx.cfg`) → common; `<mac>.cfg` → Yealink/Fanvil;
    `cfg<mac>.xml` → Grandstream; `cfg<mac>` → legacy_binary; boshqasi → unknown."""
    name = (filename or "").lower()
    if _COMMON_RE.fullmatch(name):
        return ProvFile("common")
    for kind, pattern in (("device_cfg", _DEVICE_CFG_RE), ("device_xml", _DEVICE_XML_RE),
                          ("legacy_binary", _LEGACY_RE)):
        match = pattern.fullmatch(name)
        if match and match.group("mac") != "000000000000":
            return ProvFile(kind, match.group("mac"))  # type: ignore[arg-type]
    return ProvFile("unknown")


def file_vendors(kind: FileKind) -> tuple[Vendor, ...]:
    """Fayl turi qaysi vendor(lar)ga tegishli: `<mac>.cfg` nomini Yealink va Fanvil ikkisi ham ishlatadi."""
    return {"device_cfg": ("yealink", "fanvil"), "device_xml": ("grandstream",),
            "legacy_binary": ("grandstream",), "common": ("yealink",)}.get(kind, ())


def guess_vendor(kind: FileKind, ua: UaInfo) -> Vendor | None:
    """Ro'yxatda yo'q apparat uchun vendor: UA'dan (fayl turiga mos bo'lsa), aks holda fayl turi yagona bo'lsa — u."""
    candidates = file_vendors(kind)
    if ua.vendor in candidates:
        return ua.vendor
    return candidates[0] if len(candidates) == 1 else None
