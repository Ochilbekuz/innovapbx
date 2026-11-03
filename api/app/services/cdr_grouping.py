"""`cdr` qatorlarini MANTIQIY qo'ng'iroqlarga yig'ish — BITTA joyda (ub-mode
DRY): `/calls` (tarix) VA `/dashboard` (bugungi statistika/o'tkazib
yuborilganlar) ikkisi ham AYNAN BIR XIL qoidani ishlatadi.

Diqqat (build-log.md PROOF(b)): kiruvchi marshrut `Goto()` bilan `dest-<target_id>`
kontekstiga sakraydi, shu sabab Asterisk CDR'ning `dcontext`/`dst` ustunlari OXIRGI
kontekst/exten'ni ko'rsatadi ("t1-dest-...", "s"), DID emas — original DID faqat
`userfield`da saqlanadi (dialplan kompilyatori shuni ataylab yozadi).

M1a: bitta qo'ng'iroq Asterisk'da BIR NECHTA `cdr` qatorini hosil qilishi
mumkin (`uniqueid` bo'yicha bo'linadi) — masalan `Queue()` har a'zo-urinishi
uchun alohida qator yaratadi. Shu sabab bir xil `uniqueid`ga ega qatorlar
BITTA mantiqiy qo'ng'iroqqa yig'iladi: agar GURUH ICHIDA biror qator
`disposition=ANSWERED` bo'lsa — butun qo'ng'iroq "javob berildi" deb
ko'rsatiladi, `billsec`/`duration` ESA O'SHA javob berilgan oyoqnikidan olinadi.

M1b (chiquvchi marshrutlar, m1b-contract.md bo'lim 2): `compiler.py`
`_route_trunk_dial_lines` har bir trunk urinishidan OLDIN
`Set(CDR(userfield)=<trunk nomi>)` yozadi va `Dial(PJSIP/...@<code>-trunk-<id>)`
qiladi — shu sabab chiquvchi qo'ng'iroqda WINNER oyoqning `dstchannel`'i
"-trunk-" ni o'z ichiga oladi (manba `channel` ESA ICHKI kanal, trunk emas).
Shu farq bilan `in` (manba trunk) va `out` (manzil trunk) bir-biridan
ajratiladi; `out` uchun `Call.trunk` — userfield'da yozilgan trunk NOMI."""
from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Cdr, Trunk
from app.schemas import CallDirection, CallDisposition, CallOut
from app.services.call_direction import classify_direction

_CLID_NAME = re.compile(r'^\s*"?([^"<]*?)"?\s*<[^>]*>\s*$')

_DISPOSITION_MAP = {"ANSWERED": "answered", "NO ANSWER": "no_answer", "BUSY": "busy"}


def direction_of(channel: str | None, dstchannel: str | None) -> CallDirection:
    return classify_direction(channel, dstchannel)


def disposition_of(raw: str | None) -> CallDisposition:
    return _DISPOSITION_MAP.get((raw or "").upper(), "failed")


def resolve_dst(cdr: Cdr) -> str:
    if cdr.dst and cdr.dst not in ("s", ""):
        return cdr.dst
    return cdr.userfield or ""


def _group_by_key(rows: list[Cdr], key_of) -> list[list[Cdr]]:
    """Umumiy guruhlash algoritmi (dryer): `key_of(row)` bo'yicha, DASTLABKI
    uchrash tartibini saqlab (kirish `rows` tartibi o'zgarmaydi)."""
    groups: dict[str, list[Cdr]] = {}
    order: list[str] = []
    for row in rows:
        key = key_of(row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    return [groups[key] for key in order]


def group_by_uniqueid(rows: list[Cdr]) -> list[list[Cdr]]:
    """Bir xil `uniqueid`ga ega qatorlarni (masalan `Queue()` har a'zo-urinishi
    uchun yaratgan alohida qatorlar) bitta guruhga yig'adi — `/calls` va
    `/dashboard` ishlatadigan "mantiqiy qo'ng'iroq" (bitta bog'lanish urinishi)."""
    return _group_by_key(rows, lambda r: r.uniqueid or "")


def group_by_linkedid(rows: list[Cdr]) -> list[list[Cdr]]:
    """m2b-contract.md §5: hisobot "qo'ng'iroq"i — bitta `linkedid` (transfer/
    forward/ring group oyoqlari, ya'ni BIR NECHTA `uniqueid`, bitta qo'ng'iroq
    hisoblanadi) — `group_by_uniqueid`dan KENGROQ guruhlash, `/reports/*`
    uchun (`app/services/report_defs.py`). `linkedid` NULL bo'lsa `uniqueid`ga
    tushadi (Asterisk har doim to'ldiradi, lekin himoya uchun)."""
    return _group_by_key(rows, lambda r: r.linkedid or r.uniqueid or "")


def answered_leg(group: list[Cdr]) -> Cdr | None:
    return next((r for r in group if (r.disposition or "").upper() == "ANSWERED"), None)


def primary_leg(group: list[Cdr]) -> Cdr:
    """Guruhdagi ENG BIRINCHI oyoq (eng kichik `sequence`) — asl qo'ng'iroq
    metama'lumotlarini (DID/yo'nalish/src) o'z ichiga oladi; keyingi (forklangan)
    oyoqlarda bular odatda bo'sh/meros qilinmagan bo'ladi."""
    return min(group, key=lambda r: r.sequence if r.sequence is not None else 0)


def trunk_id_of(channel: str | None) -> str | None:
    """`PJSIP/<code>-trunk-<id>-<hex>` → `<id>`; trunk kanali bo'lmasa `None`."""
    _, sep, rest = (channel or "").partition("-trunk-")
    return rest.rsplit("-", 1)[0] if sep and "-" in rest else None


async def trunk_names(session: AsyncSession, tenant_id: str) -> dict[str, str]:
    """Kiruvchi qo'ng'iroq trunki — kanal nomida faqat id bor; nom shu xaritadan."""
    rows = (await session.execute(select(Trunk.id, Trunk.name).where(Trunk.tenant_id == tenant_id))).all()
    return {str(tid): name for tid, name in rows}


def _trunk_of(direction: str, primary: Cdr, winner: Cdr, names: Mapping[str, str]) -> str | None:
    """`out` — userfield'dagi trunk nomi (har urinish oldidan yoziladi); `in` — manba kanal id'si bo'yicha nom."""
    if direction == "out":
        return winner.userfield
    if direction == "in":
        return names.get(trunk_id_of(primary.channel) or "")
    return None


def call_out_from_group(group: list[Cdr], names: Mapping[str, str] | None = None) -> CallOut:
    primary = primary_leg(group)
    winner = answered_leg(group) or primary
    direction = direction_of(primary.channel, winner.dstchannel)
    did = primary.userfield if direction == "in" else None
    trunk = _trunk_of(direction, primary, winner, names or {})
    return CallOut(
        uniqueid=primary.uniqueid, started_at=primary.calldate, src=primary.src or "",
        dst=resolve_dst(winner), did=did, direction=direction,
        disposition=disposition_of(winner.disposition), duration=winner.duration,
        billsec=winner.billsec, trunk=trunk, linkedid=primary.linkedid or primary.uniqueid,
        src_name=clid_name(primary.clid), pin_label=_pin_label_of(group),
    )


def clid_name(clid: str | None) -> str | None:
    """`"Ali Valiyev" <201>` → `Ali Valiyev`; ism yo'q yoki faqat raqam bo'lsa — `None`."""
    found = _CLID_NAME.match(clid or "")
    name = found.group(1).strip() if found else ""
    return None if not name or name.lstrip("+").isdigit() else name


def _pin_label_of(group: list[Cdr]) -> str | None:
    """PIN to'plami yorlig'i dialplanda bitta oyoqqa yoziladi — guruhdagi birinchi bo'sh bo'lmagani."""
    return next((row.pin_label for row in group if row.pin_label), None)


def calls_from_rows(rows: list[Cdr], names: Mapping[str, str] | None = None) -> list[CallOut]:
    """`rows` (kirish tartibida, odatda `calldate desc`) — guruhlangan va
    `CallOut`ga aylangan mantiqiy qo'ng'iroqlar ro'yxati. `names` — kiruvchi trunk nomlari (`trunk_names`)."""
    return [call_out_from_group(g, names) for g in group_by_uniqueid(rows)]
