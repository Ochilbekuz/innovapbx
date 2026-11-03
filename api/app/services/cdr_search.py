"""Qo'ng'iroqlar tarixining kengaytirilgan qidiruvi (FreePBX «CDR Reports» shabloni, M9).

Filtr mantiqiy qo'ng'iroqqa (`CallOut`, `cdr_grouping` yig'gandan KEYIN) qo'llanadi —
`dst`/yo'nalish/trunk faqat yig'ilgandan keyin ma'lum. Hammasi sof funksiya."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from app.core.errors import ApiError
from app.schemas import CallDisposition, CallOut
from app.services.fpbx.apply_plan import csv_cell

MatchMode = Literal["contains", "begins", "ends", "exact"]
RecordingFilter = Literal["any", "with", "without"]
MATCH_MODES: tuple[str, ...] = get_args(MatchMode)
RECORDING_FILTERS: tuple[str, ...] = get_args(RecordingFilter)
DISPOSITIONS: tuple[str, ...] = get_args(CallDisposition)
EXPORT_LIMIT = 10_000
_TZ = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class TextMatch:
    value: str
    mode: MatchMode = "contains"
    negate: bool = False

    def __call__(self, candidate: str | None) -> bool:
        return _matches(candidate or "", self.value, self.mode) != self.negate


@dataclass(frozen=True)
class CallSearch:
    src: TextMatch | None = None
    dst: TextMatch | None = None
    did: TextMatch | None = None
    name: TextMatch | None = None
    ext: str | None = None
    trunk: TextMatch | None = None
    account: TextMatch | None = None
    dispositions: frozenset[str] = field(default_factory=frozenset)
    min_duration: int | None = None
    max_duration: int | None = None
    recording: RecordingFilter = "any"

    @property
    def needs_recordings(self) -> bool:
        return self.recording != "any"


def _matches(candidate: str, value: str, mode: str) -> bool:
    cand, val = candidate.lower(), value.lower()
    if mode == "begins":
        return cand.startswith(val)
    if mode == "ends":
        return cand.endswith(val)
    if mode == "exact":
        return cand == val
    return val in cand


def _text_match(field_name: str, value: str | None, mode: str | None, negate: bool) -> TextMatch | None:
    if not value or not value.strip():
        return None
    mode = mode or "contains"
    if mode not in MATCH_MODES:
        raise ApiError(422, "validation_error", "Qidiruv rejimi noto'g'ri", field=f"{field_name}_mode")
    return TextMatch(value.strip(), mode, negate)  # type: ignore[arg-type]


def _dispositions(raw: str | None) -> frozenset[str]:
    items = frozenset(p.strip() for p in (raw or "").split(",") if p.strip())
    if items - set(DISPOSITIONS):
        raise ApiError(422, "validation_error", "Holat qiymati noto'g'ri", field="disposition")
    return items


def _duration_bounds(min_d: int | None, max_d: int | None) -> tuple[int | None, int | None]:
    if (min_d is not None and min_d < 0) or (max_d is not None and max_d < 0):
        raise ApiError(422, "validation_error", "Davomiylik manfiy bo'lmaydi", field="min_duration")
    if min_d is not None and max_d is not None and min_d > max_d:
        raise ApiError(422, "validation_error", "Min davomiylik max dan katta", field="max_duration")
    return min_d, max_d


def _clean(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def build_search(*, src: str | None = None, src_mode: str | None = None, src_not: bool = False,
                 dst: str | None = None, dst_mode: str | None = None, dst_not: bool = False,
                 did: str | None = None, did_mode: str | None = None, did_not: bool = False,
                 name: str | None = None, ext: str | None = None, trunk: str | None = None,
                 account: str | None = None, disposition: str | None = None,
                 min_duration: int | None = None, max_duration: int | None = None,
                 recording: str | None = None) -> CallSearch:
    """Query parametrlaridan tekshirilgan `CallSearch` (xato — 422 `field` bilan)."""
    recording = recording or "any"
    if recording not in RECORDING_FILTERS:
        raise ApiError(422, "validation_error", "Yozuv filtri noto'g'ri", field="recording")
    min_d, max_d = _duration_bounds(min_duration, max_duration)
    return CallSearch(
        src=_text_match("src", src, src_mode, src_not), dst=_text_match("dst", dst, dst_mode, dst_not),
        did=_text_match("did", did, did_mode, did_not), name=_text_match("name", name, None, False),
        ext=_clean(ext), trunk=_text_match("trunk", trunk, "exact", False),
        account=_text_match("account", account, None, False), dispositions=_dispositions(disposition),
        min_duration=min_d, max_duration=max_d, recording=recording,  # type: ignore[arg-type]
    )


def _text_ok(search: CallSearch, call: CallOut) -> bool:
    checks = ((search.src, call.src), (search.dst, call.dst), (search.did, call.did),
              (search.name, call.src_name), (search.account, call.pin_label), (search.trunk, call.trunk))
    if not all(m(v) for m, v in checks if m is not None):
        return False
    return not search.ext or search.ext in (call.src, call.dst)


def _numeric_ok(search: CallSearch, call: CallOut) -> bool:
    if search.dispositions and call.disposition not in search.dispositions:
        return False
    if search.min_duration is not None and call.duration < search.min_duration:
        return False
    return search.max_duration is None or call.duration <= search.max_duration


def _recording_ok(search: CallSearch, call: CallOut) -> bool:
    if search.recording == "any":
        return True
    return bool(call.recordings) == (search.recording == "with")


def call_matches(search: CallSearch, call: CallOut) -> bool:
    return _text_ok(search, call) and _numeric_ok(search, call) and _recording_ok(search, call)


def filter_calls(search: CallSearch, calls: list[CallOut]) -> list[CallOut]:
    return [c for c in calls if call_matches(search, c)]


CSV_HEADER = ("started_at", "direction", "src", "src_name", "dst", "did", "disposition",
              "duration", "billsec", "trunk", "accountcode", "recordings", "uniqueid")


def _csv_row(call: CallOut) -> tuple:
    started = call.started_at.astimezone(_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return (started, call.direction, call.src, call.src_name or "", call.dst, call.did or "",
            call.disposition, call.duration, call.billsec, call.trunk or "", call.pin_label or "",
            len(call.recordings), call.uniqueid)


def calls_csv(calls: list[CallOut]) -> str:
    """CSV (Asia/Tashkent vaqti, UTF-8 BOM — Excel kirill/lotinni to'g'ri ochsin)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    writer.writerows(tuple(csv_cell(v) for v in _csv_row(c)) for c in calls[:EXPORT_LIMIT])
    return "﻿" + buf.getvalue()
