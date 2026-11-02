"""M5a apply — saqlangan (ommaviy, ehtimol PATCH qilingan) reja bilan YANGI tahlilni
solishtirish va har element uchun yakuniy qaror; CSV hisobot. Sof funksiyalar (DB'siz).

Eskirish qoidasi: element to'plami (kind, source_ref) va `action`/`reason`dan
tashqari BARCHA ommaviy maydonlar teng bo'lishi shart. `action` farqi faqat
PATCH ruxsat bergan o'tishlar bo'lsa (`migration.py::_ALLOWED_PATCH_TRANSITIONS`
bilan bir xil) — admin tanlovi; boshqa har qanday farq -> `plan_stale`."""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.services.fpbx.mappers import Entry

PATCHABLE = frozenset({("conflict", "skip"), ("conflict", "replace"), ("create", "skip"), ("skip", "create")})
_IGNORED_FIELDS = ("action", "reason")
REPORT_COLUMNS = ("kind", "source_ref", "name", "number", "action", "reason", "result", "innova_id")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_PLAIN_NUMBER = r"[+-]?[0-9 ]+"


class PlanStaleError(Exception):
    """Tahlildan keyin Innova yoki to'plam o'zgargan — admin qayta tahlil qilsin."""

    code = "plan_stale"


@dataclass(frozen=True)
class Decision:
    entry: Entry
    action: str
    write: bool
    note: str | None = None  # yozilmaslik sababi (action create/replace bo'lsa ham)


def _key(item: Mapping[str, Any]) -> tuple[str, str]:
    return item["kind"], item["source_ref"]


def _fields(item: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k not in _IGNORED_FIELDS}


def _stale(entry: Entry, why: str) -> PlanStaleError:
    return PlanStaleError(f"Reja eskirgan ({entry.kind} {entry.source_ref}: {why}) — qayta tahlil qiling")


def decide(entry: Entry, stored: Mapping[str, Any]) -> Decision:
    fresh = entry.public_dict()
    if _fields(fresh) != _fields(stored):
        raise _stale(entry, "maydonlar o'zgargan")
    fresh_action, action = fresh["action"], stored["action"]
    if fresh_action == action:
        if fresh["reason"] != stored["reason"]:
            raise _stale(entry, "sabab o'zgargan")
        return Decision(entry, action, action == "create")
    if (fresh_action, action) not in PATCHABLE:
        raise _stale(entry, f"{fresh_action} -> {action}")
    if action == "replace":
        return Decision(entry, action, False, "replace_unsupported")
    if fresh["reason"] == "already_imported":
        return Decision(entry, action, False, "already_imported")
    return Decision(entry, action, action == "create")


def resolve_final_actions(stored_items: list[Mapping[str, Any]], fresh: list[Entry]) -> list[Decision]:
    stored = {_key(item): item for item in stored_items}
    if sorted(map(_key, stored_items)) != sorted((e.kind, e.source_ref) for e in fresh):
        raise PlanStaleError("Reja eskirgan (elementlar to'plami o'zgargan) — qayta tahlil qiling")
    return [decide(entry, stored[(entry.kind, entry.source_ref)]) for entry in fresh]


# ------------------------------------------------------------------ CSV hisobot
def csv_cell(value: Any) -> str:
    """CSV-formula in'ektsiyasidan himoya (`=`, `@`...) — sof raqamlar (+998...) tegilmaydi."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_START) and re.fullmatch(_PLAIN_NUMBER, text) is None:
        return "'" + text
    return text


def item_result(item: Mapping[str, Any], *, created: Mapping[str, str | None], result: Mapping[str, Any] | None,
                applied: bool) -> tuple[str, str | None]:
    """(natija, sabab). Sir/parol HECH QACHON — faqat `rotated` belgisi."""
    key = f"{item['kind']}:{item['source_ref']}"
    result = result or {}
    if key in created:
        rotated = item["source_ref"] in (result.get("rotated") or [])
        return ("created;rotated" if rotated else "created"), item.get("reason")
    if not applied:
        return "not_applied", item.get("reason")
    note = (result.get("not_created") or {}).get(key)
    if item["action"] == "unsupported":
        return "unsupported", item.get("reason")
    return "skipped", note or item.get("reason")


def build_report_csv(items: Iterable[Mapping[str, Any]], *, created: Mapping[str, str | None],
                     result: Mapping[str, Any] | None, applied: bool) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(REPORT_COLUMNS)
    for item in items:
        outcome, reason = item_result(item, created=created, result=result, applied=applied)
        key = f"{item['kind']}:{item['source_ref']}"
        writer.writerow([csv_cell(v) for v in (
            item["kind"], item["source_ref"], item.get("name"), item.get("number"), item["action"],
            reason, outcome, created.get(key),
        )])
    return out.getvalue()
