"""`queues_config` + `queues_details` (EAV, `member` ko'p qiymatli) + astdb
`QPENALTY/<N>/agents/*` (dinamik a'zolar) -> `queues` + `queue_members`
(m5a-contract.md §1.2, proof §4: 2 statik + 1 dinamik a'zo)."""
from __future__ import annotations

from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx import tsv as tsv_mod
from app.services.fpbx.mappers import Ctx, Entry, int_or, target_payload, target_warnings


def _static_members(details_rows: list[dict]) -> list[dict]:
    members = []
    for row in details_rows:
        if row.get("keyword") != "member":
            continue
        raw = row.get("data") or ""
        ext_part, _, penalty_part = raw.partition(",")
        extension = ext_part.split("@")[0].split("/")[-1]  # Local/101@from-queue/n -> 101
        members.append({
            "extension_number": extension, "penalty": int(penalty_part) if penalty_part.isdigit() else 0,
            "dynamic": False,
        })
    return members


def _dynamic_members(astdb: dict[str, str], number: str) -> list[dict]:
    return [{
        "extension_number": ext, "penalty": int_or(penalty, 0), "dynamic": True,
    } for ext, penalty in astdb_mod.family(astdb, f"QPENALTY/{number}/agents").items()]


_ANNOUNCE_POSITION_VALUES = frozenset({"yes", "no", "limit", "more"})
_JOIN_EMPTY_VALUES = frozenset({"yes", "no", "strict", "loose"})
_AUTO_PAUSE_VALUES = frozenset({"no", "yes", "all"})


def _enum_or(value: object, allowed: frozenset[str], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _queue_payload(row: dict, name: str, pivoted: dict, timeout_target, members: list[dict]) -> dict:
    """0037 (Queues FreePBX parity): `queues_details` — FreePBX'ning o'z EAV
    jadvali, keyword ustuni AYNAN queues.conf kaliti bilan bir xil (allaqachon
    `strategy`/`music`/`timeout`/... shu yo'l bilan o'qilgan — pastdagi
    qo'shimcha kalitlar ustun NOMINI emas, FAQAT TOPILGAN YANGI maydon
    ro'yxatini kengaytiradi, mexanizm bir xil/tasdiqlangan).

    QASDAN IMPORT QILINMAGAN (hisobot — `docs/qollanma/queues.md`): qo'shilish/
    agent e'loni audiosi va IVR chiqish (`context`) — FreePBX bandi/jadval
    nomi ushbu ko'chirilgan sxemada ishonchli tasdiqlanmagan (noto'g'ri ustun
    bilan import qilish xato ma'lumotdan ko'ra YOMONROQ); davriy e'lon ovozi —
    xuddi shu sabab; `ring_mode`/`mark_answered_elsewhere`/`cid_name_prefix`/
    `alert_info` — FreePBX Queues modulida bunga mos manba maydon UMUMAN YO'Q
    (Innova'ga xos qo'shimcha, import qilinadigan narsa yo'q)."""
    return {
        "name": name, "strategy": pivoted.get("strategy") or "ringall",
        "moh_class_name": pivoted.get("music") or None,
        "agent_ring_seconds": int_or(pivoted.get("timeout"), 15),
        "retry_seconds": int_or(pivoted.get("retry"), 5),
        "wrapup_seconds": int_or(pivoted.get("wrapuptime"), 0),
        "max_wait_seconds": int_or(row.get("maxwait"), 0),
        "max_callers": int_or(pivoted.get("maxlen"), 0),
        "announce_position": _enum_or(pivoted.get("announce-position"), _ANNOUNCE_POSITION_VALUES, "no"),
        "announce_frequency_seconds": int_or(pivoted.get("announce-frequency"), 0),
        "sla_seconds": int_or(pivoted.get("servicelevel"), 60),
        "join_empty": _enum_or(pivoted.get("joinempty"), _JOIN_EMPTY_VALUES, "no"),
        "record": (pivoted.get("recording") or "dontcare") in ("force", "yes"),
        "timeout_target_id": target_payload(timeout_target),
        "members": members,
        # 0037 — qo'shimcha HAQIQIY queues.conf kalitlari (EAV, bir xil manba).
        "weight": int_or(pivoted.get("weight"), 0),
        "autofill": (pivoted.get("autofill") or "no") == "yes",
        "report_hold_time": (pivoted.get("reportholdtime") or "no") == "yes",
        "member_delay_seconds": int_or(pivoted.get("memberdelay"), 0),
        "penalty_members_limit": int_or(pivoted.get("penaltymemberslimit"), 0),
        "auto_pause": _enum_or(pivoted.get("autopause"), _AUTO_PAUSE_VALUES, "no"),
        "auto_pause_delay_seconds": int_or(pivoted.get("autopausedelay"), 0),
        "auto_pause_busy": (pivoted.get("autopausebusy") or "no") == "yes",
        "auto_pause_unavail": (pivoted.get("autopauseunavail") or "no") == "yes",
        "agent_timeout_restart": (pivoted.get("timeoutrestart") or "no") == "yes",
        "max_wait_mode": "loose" if pivoted.get("timeoutpriority") == "conf" else "strict",
        "leave_when_empty": _enum_or(pivoted.get("leavewhenempty"), _JOIN_EMPTY_VALUES, "no"),
        "announce_position_limit": int_or(pivoted.get("announce-position-limit"), 10),
        "announce_hold_time": _enum_or(pivoted.get("announce-holdtime"), frozenset({"yes", "no", "once"}), "yes"),
        "min_announce_frequency_seconds": int_or(pivoted.get("min-announce-frequency"), 15),
        # `ringinuse="yes"` -> band a'zolarga HAM jiringlaydi (SKIP QILMAYDI);
        # sukut/boshqa har qanday qiymat -> `skip_busy_agents=True` (HOZIRGI
        # qattiq 'no' bilan bir xil xatti-harakat).
        "skip_busy_agents": pivoted.get("ringinuse") != "yes",
    }


def map_queue(ctx: Ctx) -> list[Entry]:
    details_by_id = tsv_mod.group_by(ctx.table("queues_details"), "id")
    entries: list[Entry] = []
    for row in ctx.table("queues_config"):
        number = row["extension"]
        source_ref = f"queues_config:{number}"
        name = row.get("descr") or number
        pivoted = tsv_mod.pivot_first(details_by_id.get(number, []))
        entry_warnings: list[dict[str, str]] = []

        members = _static_members(details_by_id.get(number, [])) + _dynamic_members(ctx.astdb, number)

        timeout_target = ctx.resolve(row.get("dest"))
        entry_warnings += target_warnings(timeout_target)

        entries.append(Entry(
            kind="queue", source_ref=source_ref, name=name, number=number,
            action="create", warnings=entry_warnings,
            payload=_queue_payload(row, name, pivoted, timeout_target, members),
        ))
    return entries
