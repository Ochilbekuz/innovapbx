"""M5a — mapperlar uchun umumiy interfeys (m5a-contract.md §1).

Har bir `app/services/fpbx/mappers/<kind>.py` BITTA funksiya eksport qiladi:
`map_<kind>(ctx: Ctx) -> list[Entry]`. `Entry` — ommaviy PlanItem maydonlari
(`plan.py` shulardan `migration_jobs.plan`ga yoziladigan JSON'ni quradi) +
XUSUSIY `payload` (hech qachon saqlanmaydi/qaytarilmaydi — faqat `apply`
bosqichida ishlatiladi, ikkinchi marta `analyze()` chaqirilganda qayta hosil
bo'ladi, shu sabab `analyze()` DETERMINISTIK bo'lishi SHART)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.fpbx import dest as dest_mod
from app.services.fpbx import tsv as tsv_mod

__all__ = [
    "Ctx", "Entry", "ref", "target_payload", "target_warnings", "warning", "weak_secret",
]


def warning(code: str, message: str) -> dict[str, str]:
    """`PlanItem.warnings[]`/`GlobalWarning` elementi — ikkisi ham bir xil shakl."""
    return {"code": code, "message": message}


def weak_secret(secret: str | None, *, equals_number: str | None = None) -> bool:
    """m5a-contract.md §0/§1.2: uzunlik < 12, YOKI faqat raqam/harf, YOKI (ichki
    raqam uchun) o'z raqamiga teng bo'lsa — zaif."""
    if not secret:
        return False
    if len(secret) < 12:
        return True
    if secret.isdigit() or secret.isalpha():
        return True
    return equals_number is not None and secret == equals_number


@dataclass
class Entry:
    """Bitta FreePBX obyektining reja elementi. `payload` — Innova ustunlariga mos
    xom qiymatlar (sirlar ochiq matnda, masalan `secret_plain`/`pin_plain` kaliti
    ostida — chunki `analyze()` sof/DB'siz, haqiqiy `encrypt_secret()`/bcrypt faqat
    `apply`da, qayta hisoblangan payload ustida bajariladi)."""

    kind: str
    source_ref: str
    name: str
    number: str | None
    action: str  # "create" | "skip" | "unsupported" (conflict'ni plan.py qo'yadi)
    reason: str | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    replaceable: bool = True
    has_secret: bool = False
    weak_secret: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        """`payload` BU YERDA YO'Q — faqat ommaviy PlanItem maydonlari (m5a-contract.md §0)."""
        return {
            "kind": self.kind, "source_ref": self.source_ref, "name": self.name,
            "number": self.number, "action": self.action, "reason": self.reason,
            "warnings": self.warnings, "depends_on": self.depends_on,
            "replaceable": self.replaceable, "has_secret": self.has_secret,
            "weak_secret": self.weak_secret,
        }


# Har `kind` o'zining Entry.source_ref'ini QAYSI manba jadvalidan boshlab quradi
# (`"<jadval>:<kalit>"`, m5a-contract.md §1: "source_ref = <jadval>:<kalit>").
# `dest.resolve_dest()` faqat YALANG'OCH kalitni biladi (masalan "101") — forward
# `$ref` qurishda shu jadval bilan to'ldirib, boshqa Entry.source_ref bilan mos
# keladigan to'liq shaklga keltiramiz (apply ikkinchi o'tishda shu bo'yicha topadi).
PRIMARY_TABLE: dict[str, str] = {
    "extension": "users", "ring_group": "ringgroups", "queue": "queues_config",
    "ivr": "ivr_details", "time_condition": "timeconditions", "announcement": "announcement",
    "conference": "meetme", "trunk": "trunks", "audio": "recordings", "moh": "music",
    "time_group": "timegroups_groups",
}


def ref(kind: str, bare_key: str | None) -> dict[str, str] | None:
    """Boshqa (hali yaratilmagan bo'lishi mumkin) obyektga forward-havola —
    `apply` ikkinchi o'tishda hal qiladi (m5a-contract.md §0 bog'liqlik tartibi).
    `voicemail` — alohida: manbasi jadval emas, `conf/voicemail.conf` (`[default]`
    bo'limi), shu sabab `voicemail.py`dagi `Entry.source_ref` bilan bir xil shaklga
    (`voicemail.conf:default/<mailbox>`) maxsus keltiriladi."""
    if bare_key is None:
        return None
    if kind == "voicemail":
        return {"$ref": f"voicemail:voicemail.conf:default/{bare_key}"}
    table = PRIMARY_TABLE.get(kind, kind)
    return {"$ref": f"{kind}:{table}:{bare_key}"}


def target_payload(result: dest_mod.DestResult | None) -> dict[str, Any] | None:
    """`dest.resolve_dest()` natijasini payload'ga yoziladigan shaklga keltiradi:
    `hangup`/`busy` — tayyor turgan maqsadlar (sinonim), `external` — tashqi raqam,
    boshqa barchasi — `$ref` (chunki shu obyekt reja ichida alohida yaratiladi)."""
    if result is None:
        return None
    if result.kind in ("hangup", "busy"):
        return {"kind": result.kind}
    if result.kind == "external":
        return {"kind": "external", "number": result.ref}
    return ref(result.kind, result.ref)


def target_warnings(result: dest_mod.DestResult | None) -> list[dict[str, str]]:
    return [warning(*result.warning)] if result is not None and result.warning else []


@dataclass
class Ctx:
    """Bir `analyze()` chaqiruviga tegishli, barcha mapperlar o'qiydigan sof
    ma'lumotlar to'plami — hech qanday DB/tarmoq, faqat ochilgan to'plam papkasi."""

    root: Path
    meta: dict[str, Any]
    catalog: dest_mod.DestCatalog
    astdb: dict[str, str] = field(default_factory=dict)
    vm_boxes: dict[str, dict] = field(default_factory=dict)
    _tables: dict[str, list[dict]] = field(default_factory=dict)

    def table(self, name: str) -> list[dict]:
        """`tables/<name>.tsv`ni (bor bo'lsa) o'qiydi va keshlaydi — bir xil
        jadval bir nechta mapper tomonidan so'ralishi mumkin (masalan `users`)."""
        if name not in self._tables:
            path = self.root / "tables" / f"{name}.tsv"
            self._tables[name] = tsv_mod.parse_tsv_file(path) if path.exists() else []
        return self._tables[name]

    def eav(self, name: str, *, id_field: str = "id") -> dict[str, dict[str, str | None]]:
        """EAV jadval (`sip`/`pjsip`/...) -> `{id: {keyword: data}}` (takrorlangan
        ko'p qiymatli kalitlar — masalan `queues_details.member` — bu yerda
        YO'QOLADI, ularni chaqiruvchi `table()` + `tsv.group_by` bilan o'zi oladi)."""
        grouped = tsv_mod.group_by(self.table(name), id_field)
        return {key: tsv_mod.pivot_first(rows) for key, rows in grouped.items()}

    def resolve(self, raw_dest: str | None) -> dest_mod.DestResult | None:
        return dest_mod.resolve_dest(raw_dest, self.catalog)
