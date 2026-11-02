"""Analitika (S13) — m2b-contract.md bo'lim 5. Barcha TA'RIFLAR BITTA joyda,
sof (bazasiz) funksiyalar sifatida — `app/api/v1/reports.py` faqat ma'lumot
YIG'ADI (CDR/queue_log/agent_events qatorlari), BUTUN hisoblash mantiqi shu
yerda (ub-mode: "Model the Domain" + "Boundary Discipline").

Ma'lumot manbalari (m2b-contract.md §0):
- navbatsiz (va navbat ichidagi) qo'ng'iroq hajmi/yo'nalish/javob — `cdr`
  (`group_by_linkedid` — transfer/forward/ring group zanjiri BITTA qo'ng'iroq).
- navbat statistikasi (entered/answered/abandoned/timeout/wait/SLA) — `queue_log`
  (Asterisk native, `app/db/models.py:QueueLog`).
- agent login/pauza vaqti — `agent_events` (0015_m2b_agent_state.sql trigger).

MUHIM farq `app/services/cdr_grouping.py`dan: u yerda "qo'ng'iroq" — BITTA
`uniqueid` (masalan Queue() a'zo-urinishlari); bu yerda — BITTA `linkedid`
(m2b-contract.md §5: "transfer/forward/ring group oyoqlari bitta qo'ng'iroq").
`direction`/`blacklist` kabi QAYTA ISHLATISH mumkin bo'lgan qoidalar
`cdr_grouping.py`/`call_direction.py`dan import qilinadi (dryer)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.errors import ApiError
from app.db.models import AgentEvent, Cdr, QueueLog
from app.services.call_direction import Direction, classify_direction
from app.services.cdr_grouping import answered_leg, group_by_linkedid
from app.services.dashboard import local_midnight_utc

MAX_RANGE_DAYS = 92


# --------------------------------------------------------------- sana oralig'i
def validate_range(from_date: date, to_date: date) -> None:
    """m2b-contract.md §5: `from..to` ikkala kun kiradi, oraliq ≤ 92 kun,
    aks holda 422 `bad_range` (`field: "to"`)."""
    days = (to_date - from_date).days + 1
    if days < 1 or days > MAX_RANGE_DAYS:
        raise ApiError(422, "bad_range", f"Oraliq 1..{MAX_RANGE_DAYS} kun bo'lishi kerak", field="to")


def range_bounds_utc(tz_name: str, from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """`from_date`'ning 00:00'idan `to_date`dan KEYINGI kunning 00:00'igacha
    (tenant TZ) — UTC chegaralar, `to_date` TO'LIQ kiradi."""
    return local_midnight_utc(tz_name, from_date), local_midnight_utc(tz_name, to_date + timedelta(days=1))


# --------------------------------------------------------------- CDR -> qo'ng'iroqlar
@dataclass(frozen=True)
class ReportCall:
    """Bitta hisobot "qo'ng'iroq"i — `group_by_linkedid` natijasidan tuzilgan."""

    uniqueid: str
    linkedid: str
    started_at: datetime
    direction: Direction
    answered: bool
    blocked: bool
    talk_seconds: int = 0
    wait_seconds: int = 0


def _ext_answered_leg(group: list[Cdr]) -> Cdr | None:
    """m2b-contract.md §5: "answered" = kamida bitta EXT oyog'i ANSWERED
    (`dstchannel` haqiqiy ichki raqam — trunk EMAS) VA `billsec>0`; IVR'ning
    o'z `Answer()`i (dstchannel bo'sh/trunk) HISOBLANMAYDI (M1a saboq,
    build-log.md B-M1a-05 — "assert_leg_answered DID EXT")."""
    for row in group:
        if (row.disposition or "").upper() == "ANSWERED" and (row.billsec or 0) > 0 \
                and row.dstchannel and "-trunk-" not in row.dstchannel:
            return row
    return None


def _is_blocked(group: list[Cdr]) -> bool:
    """Qora ro'yxat — `Set(CDR(userfield)=blacklisted)` (dialplan_features.py);
    MISSED emas, alohida `blocked` (m2b-contract.md §5)."""
    return any(row.userfield == "blacklisted" for row in group)


def report_calls_from_rows(rows: list[Cdr]) -> list[ReportCall]:
    """`rows` — tanlangan oraliqdagi (tenant bo'yicha filtrlangan) xom CDR
    qatorlari. Yo'nalish — guruhning "g'olib" oyog'i bo'yicha (`answered_leg`
    qayta ishlatiladi, `cdr_grouping.call_out_from_group` bilan BIR XIL
    qoida — dryer), lekin "javob berildi"ligi YUQORIDAGI qattiqroq qoida
    bilan (`_ext_answered_leg`) alohida hisoblanadi."""
    calls: list[ReportCall] = []
    for group in group_by_linkedid(rows):
        primary = min(group, key=lambda r: r.calldate)
        ext_leg = _ext_answered_leg(group)
        winner = answered_leg(group) or primary
        direction = classify_direction(primary.channel, winner.dstchannel)
        wait = max((ext_leg.duration or 0) - (ext_leg.billsec or 0), 0) if ext_leg else 0
        calls.append(ReportCall(
            uniqueid=primary.uniqueid, linkedid=primary.linkedid or primary.uniqueid,
            started_at=primary.calldate, direction=direction, answered=ext_leg is not None,
            blocked=_is_blocked(group), talk_seconds=(ext_leg.billsec or 0) if ext_leg else 0,
            wait_seconds=wait,
        ))
    return calls


def filter_calls_by_linkedid(calls: list[ReportCall], linkedids: set[str]) -> list[ReportCall]:
    """`?queue_id=` filtri (summary/hourly/daily) — faqat shu navbatga kirgan
    qo'ng'iroqlar (`linkedids` — shu navbatning `queue_log.callid` to'plami)."""
    return [c for c in calls if c.linkedid in linkedids]


# --------------------------------------------------------------- SLA (umumiy)
def sla_percent(samples: list[tuple[int, int]]) -> float | None:
    """`samples` — (wait_seconds, sla_seconds) juftlari (CONNECT+ABANDON
    hodisalari). Bo'sh bo'lsa `None` (m2b-contract.md §5: "entered=0 -> null",
    bu yerda kengroq — CONNECT/ABANDON yo'q bo'lsa ham, chunki bo'lish 0/0 bo'lardi)."""
    if not samples:
        return None
    hits = sum(1 for wait, sla in samples if wait <= sla)
    return hits / len(samples) * 100


# --------------------------------------------------------------- qo'ng'iroq xulosasi
def busiest_hour(calls: list[ReportCall], tz_name: str) -> int | None:
    """Eng ko'p qo'ng'iroq (BARCHA yo'nalish) bo'lgan soat (tenant TZ);
    teng bo'lsa kichikrogi; umuman qo'ng'iroq bo'lmasa `None`."""
    if not calls:
        return None
    tz = ZoneInfo(tz_name)
    counts = [0] * 24
    for c in calls:
        counts[c.started_at.astimezone(tz).hour] += 1
    return max(range(24), key=lambda h: (counts[h], -h))


def _count_by_direction(calls: list[ReportCall]) -> dict[str, int]:
    counts = {"in": 0, "out": 0, "internal": 0}
    for c in calls:
        counts[c.direction] += 1
    return counts


def _count_missed_and_blocked(calls: list[ReportCall]) -> tuple[int, int]:
    """`missed` — kiruvchi, javobsiz, BLOKLANMAGAN; `blocked` — alohida
    hisoblanadi (m2b-contract.md §5: ikkisi bir-biridan MUSTAQIL metrika)."""
    blocked = sum(1 for c in calls if c.blocked)
    missed = sum(1 for c in calls if c.direction == "in" and not c.answered and not c.blocked)
    return missed, blocked


def _answered_averages(calls: list[ReportCall]) -> tuple[int | None, int | None]:
    """`(avg_wait_seconds, avg_talk_seconds)` — FAQAT javob berilgan
    qo'ng'iroqlar bo'yicha; bo'sh bo'lsa ikkisi ham `None`."""
    answered_calls = [c for c in calls if c.answered]
    if not answered_calls:
        return None, None
    avg_wait = round(sum(c.wait_seconds for c in answered_calls) / len(answered_calls))
    avg_talk = round(sum(c.talk_seconds for c in answered_calls) / len(answered_calls))
    return avg_wait, avg_talk


def build_summary(calls: list[ReportCall], tz_name: str, queue_sla_samples: list[tuple[int, int]]) -> dict:
    """`GET /reports/summary`. `avg_wait_seconds`/`avg_talk_seconds` —
    javob berilgan qo'ng'iroqlarning EXT oyog'i (`duration-billsec`/`billsec`)
    bo'yicha — m1b-contract.md bo'lim 5dagi `dashboard.avg_wait_s` bilan BIR
    XIL tushuncha (ub-mode dryer; navbat kutish vaqti BUTUNLAY boshqacha —
    `queue_log` orqali, faqat `/reports/queues`da aniq). Kichik yordamchi
    funksiyalarga bo'lingan (ub-mode crapper: CRAP<10 har funksiya uchun)."""
    direction_counts = _count_by_direction(calls)
    missed, blocked = _count_missed_and_blocked(calls)
    answered = sum(1 for c in calls if c.answered)
    avg_wait, avg_talk = _answered_averages(calls)
    sla = sla_percent(queue_sla_samples)
    return {
        "total": len(calls), "inbound": direction_counts["in"], "outbound": direction_counts["out"],
        "internal": direction_counts["internal"], "answered": answered, "missed": missed, "blocked": blocked,
        "avg_wait_seconds": avg_wait, "avg_talk_seconds": avg_talk,
        "sla_percent": round(sla, 1) if sla is not None else None,
        "busiest_hour": busiest_hour(calls, tz_name),
    }


def build_hourly(calls: list[ReportCall], tz_name: str) -> list[dict]:
    """`GET /reports/hourly` — 24 qator HAR DOIM; yig'indi = summary
    (`inbound`/`answered`/`missed`, m2b-contract.md §5/§6 ssenariy 7)."""
    tz = ZoneInfo(tz_name)
    buckets = [{"inbound": 0, "answered": 0, "missed": 0} for _ in range(24)]
    for c in calls:
        hour = c.started_at.astimezone(tz).hour
        if c.direction == "in":
            buckets[hour]["inbound"] += 1
            if not c.answered and not c.blocked:
                buckets[hour]["missed"] += 1
        if c.answered:
            buckets[hour]["answered"] += 1
    return [{"hour": h, **buckets[h]} for h in range(24)]


def build_daily(calls: list[ReportCall], tz_name: str, from_date: date, to_date: date) -> list[dict]:
    """`GET /reports/daily` — oraliqdagi HAR bir kun (bo'sh kun 0 bilan)."""
    tz = ZoneInfo(tz_name)
    days = [from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)]
    buckets = {d: {"total": 0, "answered": 0, "missed": 0} for d in days}
    for c in calls:
        d = c.started_at.astimezone(tz).date()
        bucket = buckets.get(d)
        if bucket is None:
            continue  # himoya: oraliqdan tashqari qator (kutilmagan)
        bucket["total"] += 1
        if c.answered:
            bucket["answered"] += 1
        if c.direction == "in" and not c.answered and not c.blocked:
            bucket["missed"] += 1
    return [{"date": d.isoformat(), **buckets[d]} for d in days]


# --------------------------------------------------------------- queue_log -> navbat
def _to_int(value: str | None) -> int:
    try:
        return int(value) if value else 0
    except ValueError:
        return 0


def _queue_log_wait(row: QueueLog) -> int | None:
    """CONNECT -> `data1` (holdtime); ABANDON -> `data3` (waittime) —
    m2b-contract.md §5 (haqiqiy PG ma'lumotida tasdiqlangan, Asterisk 22
    `app_queue.c` log formati: ENTERQUEUE=url|callerid|pos,
    CONNECT=holdtime|peer_uniqueid|ringtime, ABANDON=pos|origpos|waittime)."""
    if row.event == "CONNECT":
        return _to_int(row.data1)
    if row.event == "ABANDON":
        return _to_int(row.data3)
    return None


@dataclass(frozen=True)
class QueueStats:
    entered: int = 0
    answered: int = 0
    abandoned: int = 0
    timeout: int = 0
    waits: list[int] = field(default_factory=list)


def queue_stats_from_log(rows: list[QueueLog]) -> QueueStats:
    entered = sum(1 for r in rows if r.event == "ENTERQUEUE")
    answered = sum(1 for r in rows if r.event == "CONNECT")
    abandoned = sum(1 for r in rows if r.event == "ABANDON")
    timeout = sum(1 for r in rows if r.event in ("EXITWITHTIMEOUT", "EXITEMPTY"))
    waits = [w for w in (_queue_log_wait(r) for r in rows) if w is not None]
    return QueueStats(entered=entered, answered=answered, abandoned=abandoned, timeout=timeout, waits=waits)


def queue_wait_samples(rows: list[QueueLog], sla_seconds_by_queuename: dict[str, int]) -> list[tuple[int, int]]:
    """`GET /reports/summary`ning umumiy SLA'si uchun: bir nechta navbat
    bitta to'plamga yig'ilganda ham HAR BIR qatorga MOS `sla_seconds`
    bilan juftlanadi (har navbatning chegarasi boshqacha bo'lishi mumkin)."""
    samples: list[tuple[int, int]] = []
    for row in rows:
        wait = _queue_log_wait(row)
        sla = sla_seconds_by_queuename.get(row.queuename or "")
        if wait is not None and sla is not None:
            samples.append((wait, sla))
    return samples


def build_queue_report_row(stats: QueueStats, sla_seconds: int) -> dict:
    """`GET /reports/queues` — bitta navbat qatori (m2b-contract.md §5)."""
    avg_wait = round(sum(stats.waits) / len(stats.waits)) if stats.waits else 0
    max_wait = max(stats.waits) if stats.waits else 0
    sla = sla_percent([(w, sla_seconds) for w in stats.waits])
    return {
        "entered": stats.entered, "answered": stats.answered, "abandoned": stats.abandoned,
        "timeout": stats.timeout, "avg_wait_seconds": avg_wait, "max_wait_seconds": max_wait,
        "sla_percent": round(sla, 1) if sla is not None else None,
    }


# --------------------------------------------------------------- agent hisobotlari
def active_seconds(events: list[tuple[datetime, bool]], start: datetime, end: datetime) -> int:
    """`events` — (vaqt, yangi_holat) juftlari, VAQT bo'yicha o'sish tartibida,
    `start`dan OLDINGI yozuvlarni ham o'z ichiga olishi mumkin (boshlang'ich
    holatni bilish uchun). Qaytaradi: `[start, end)` oralig'ida `True`
    holatda o'tgan butun soniyalar. `end` — odatda `min(oraliq_oxiri, now())`,
    shu sabab "hali ochiq sessiya" avtomatik `now()`gacha hisoblanadi
    (m2b-contract.md §5), oraliqdan tashqariga chiqmaydi."""
    state = False
    cursor = start
    total = timedelta()
    for at, new_state in events:
        if at <= start:
            state = new_state
            continue
        if at >= end:
            break
        if state:
            total += at - cursor
        cursor = at
        state = new_state
    if state:
        total += end - cursor
    return int(total.total_seconds())


def _event_pairs(events: list[AgentEvent], active_event: str, inactive_event: str) -> list[tuple[datetime, bool]]:
    """`agent_events`dan (allaqachon BITTA extension bo'yicha filtrlangan,
    vaqt bo'yicha o'sish tartibida) `active_seconds`ga mos (vaqt, holat)
    juftlari. Bir xil (`at`, `event`) takrorlari (ext bir nechta navbatga
    a'zo bo'lsa, *45/*46 HAR BIR a'zolik uchun alohida yozuv yaratadi,
    m2b-contract.md §1) BITTA hodisaga tenglashtiriladi (dedup, `set`)."""
    seen = sorted({(e.at, e.event) for e in events if e.event in (active_event, inactive_event)})
    return [(at, event == active_event) for at, event in seen]


def login_pause_seconds(events: list[AgentEvent], window_start: datetime, window_end: datetime) -> tuple[int, int]:
    """`events` — BITTA extension'ning BARCHA `agent_events`i (xohlagan
    vaqtda, `window_end`gacha — boshlang'ich holatni bilish uchun `window_start`dan
    oldingilar ham kerak). Qaytaradi: `(login_seconds, pause_seconds)`."""
    login_seconds = active_seconds(_event_pairs(events, "login", "logout"), window_start, window_end)
    pause_seconds = active_seconds(_event_pairs(events, "pause", "unpause"), window_start, window_end)
    return login_seconds, pause_seconds


@dataclass(frozen=True)
class AgentQueueStats:
    answered: int = 0
    missed_ring: int = 0
    talk_seconds: int = 0


def agent_queue_stats(rows: list[QueueLog]) -> dict[str, AgentQueueStats]:
    """`rows.agent` — navbat a'zosining `membername` qiymati (Asterisk
    CONNECT/COMPLETE*/RINGNOANSWER hodisalarida), 0015_m2b_agent_state.sql
    `asterisk_queue_members` view'ida `e.name as membername` — shu sabab
    kalit `extensions.name`, RAQAM EMAS."""
    acc: dict[str, dict[str, int]] = {}
    for row in rows:
        if not row.agent or row.agent in ("NONE", "REALTIME"):
            continue
        bucket = acc.setdefault(row.agent, {"answered": 0, "missed_ring": 0, "talk_seconds": 0})
        if row.event == "CONNECT":
            bucket["answered"] += 1
        elif row.event == "RINGNOANSWER":
            bucket["missed_ring"] += 1
        elif row.event in ("COMPLETECALLER", "COMPLETEAGENT"):
            bucket["talk_seconds"] += _to_int(row.data2)
    return {name: AgentQueueStats(**v) for name, v in acc.items()}


def build_agent_report_row(
    *, extension_number: str, extension_name: str, queue_stats: AgentQueueStats,
    login_seconds: int, pause_seconds: int,
) -> dict:
    avg_talk = round(queue_stats.talk_seconds / queue_stats.answered) if queue_stats.answered else None
    return {
        "extension": extension_number, "name": extension_name,
        "answered": queue_stats.answered, "missed_ring": queue_stats.missed_ring,
        "talk_seconds": queue_stats.talk_seconds, "avg_talk_seconds": avg_talk,
        "login_seconds": login_seconds, "pause_seconds": pause_seconds,
    }
