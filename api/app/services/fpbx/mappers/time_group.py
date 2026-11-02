"""`timegroups_groups` + `timegroups_details` -> `time_groups`/`time_ranges`/
`holidays` (m5a-contract.md §1.2). Bitta FreePBX vaqt guruhi qatori ikki xil
Innova obyektiga aylanishi mumkin: oddiy hafta kuni oraligi -> `time_range`,
aniq kun+oy -> `holiday` (dom/mon `*` emas)."""
from __future__ import annotations

from datetime import date

from app.services.fpbx.mappers import Ctx, Entry, warning

_WEEKDAYS = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7}
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MAX_HOLIDAY_SPAN = 31


def _expand_range(token: str, table: dict[str, int]) -> list[int] | None:
    if token == "*":
        return list(table.values())
    if "-" in token:
        start, end = token.split("-", 1)
        if start not in table or end not in table:
            return None
        return list(range(table[start], table[end] + 1))
    return [table[token]] if token in table else None


def _parse_time_range(token: str) -> tuple[str, str] | None:
    if token == "*":
        return "00:00", "23:59"
    if "-" in token:
        start, end = token.split("-", 1)
        return start, end
    return None


def _weekday_entry(group_id: str, row: dict, dow: str, time_token: str) -> dict | None:
    weekdays = _expand_range(dow, _WEEKDAYS)
    hhmm = _parse_time_range(time_token)
    if weekdays is None or hhmm is None:
        return None
    return {"weekdays": weekdays, "start_time": hhmm[0], "end_time": hhmm[1]}


def _holiday_days(dom: str, mon: str) -> list[tuple[int, int]] | None:
    """`(dom, mon)` -> `[(day, month), ...]` ro'yxati; juftlik oraliq bo'lsa
    (`dash`) har biri alohida kunga yoyiladi (≤31), mos kelmasa `None`."""
    dom_is_range, mon_is_range = "-" in dom, "-" in mon
    if not dom_is_range and not mon_is_range:
        if dom.isdigit() and mon in _MONTHS:
            return [(int(dom), _MONTHS[mon])]
        return None
    if dom_is_range and not mon_is_range:
        start, end = dom.split("-", 1)
        if not (start.isdigit() and end.isdigit()) or mon not in _MONTHS:
            return None
        span = int(end) - int(start) + 1
        if span <= 0 or span > _MAX_HOLIDAY_SPAN:
            return None
        return [(d, _MONTHS[mon]) for d in range(int(start), int(end) + 1)]
    return None  # mon oraliq yoki ikkisi ham oraliq — qo'llab-quvvatlanmaydi


def map_time_group(ctx: Ctx) -> list[Entry]:
    entries: list[Entry] = []
    details_by_group = {}
    for row in ctx.table("timegroups_details"):
        details_by_group.setdefault(row["timegroupid"], []).append(row)

    for group in ctx.table("timegroups_groups"):
        group_id = group["id"]
        name = group.get("description") or f"FreePBX vaqt guruhi {group_id}"
        source_ref = f"timegroups_groups:{group_id}"
        ranges: list[dict] = []
        entry_warnings: list[dict[str, str]] = []

        for detail in details_by_group.get(group_id, []):
            time_token, dow, dom, mon = (detail.get("time") or "*|*|*|*").split("|")
            if dom == "*" and mon == "*":
                parsed = _weekday_entry(group_id, detail, dow, time_token)
                if parsed is None:
                    entry_warnings.append(warning("time_range_unsupported", f"Qo'llab-quvvatlanmaydi: {detail.get('time')}"))
                else:
                    ranges.append(parsed)
                continue
            days = _holiday_days(dom, mon)
            if days is None:
                entries.append(Entry(
                    kind="holiday", source_ref=f"timegroups_details:{detail['id']}",
                    name=f"{name} (bayram)", number=None, action="unsupported", reason="holiday_range_unsupported",
                    warnings=[warning("holiday_range_unsupported", f"Qo'llab-quvvatlanmaydi: {detail.get('time')}")],
                ))
                continue
            this_year = date.today().year
            for day_num, month_num in days:
                entries.append(Entry(
                    kind="holiday", source_ref=f"timegroups_details:{detail['id']}:{day_num:02d}{month_num:02d}",
                    name=f"{name} (bayram)", number=None, action="create",
                    reason="holiday_from_timegroup",
                    warnings=[warning("holiday_from_timegroup", "Vaqt guruhidan ajratilgan bayram")],
                    payload={"name": f"{name} (bayram)", "day": date(this_year, month_num, day_num).isoformat(),
                             "recurring_yearly": True},
                ))

        entries.append(Entry(
            kind="time_group", source_ref=source_ref, name=name, number=None,
            action="create", warnings=entry_warnings,
            payload={"name": name, "ranges": ranges},
        ))
    return entries
