"""M10 Bo'lak B1 — Sifat baholash (QA) ball hisobi, sof funksiyalar.

Qoida (m10-onlinepbx-contract.md Bo'lak B1):
- `yesno` mezon: ha=1, yo'q=0, og'irlik bilan ko'paytiriladi.
- `scale5` mezon: (qiymat-1)/4, og'irlik bilan ko'paytiriladi (1..5 -> 0..1).
- `critical` mezon muvaffaqiyatsiz bo'lsa (yesno="no" YOKI scale5 < max) —
  BUTUN baholash foizi 0 (boshqa mezonlar hisobga olinmaydi).
- Foiz = (Σ olingan ball / Σ og'irlik) * 100, 2 xonaga yaxlitlanadi."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

CriterionKind = Literal["yesno", "scale5"]


@dataclass(frozen=True)
class Criterion:
    id: str
    kind: CriterionKind
    weight: float
    critical: bool = False


@dataclass(frozen=True)
class Answer:
    criterion_id: str
    value: object  # yesno: bool, scale5: int(1..5)


def criterion_fraction(criterion: Criterion, value: object) -> float:
    """0..1 oraliqda ulush (og'irlikdan oldin). `None` -> 0 (javobsiz)."""
    if value is None:
        return 0.0
    if criterion.kind == "yesno":
        return 1.0 if bool(value) else 0.0
    if criterion.kind == "scale5":
        v = int(value)
        return max(0.0, min(1.0, (v - 1) / 4))
    raise ValueError(f"noma'lum mezon turi: {criterion.kind}")


def is_critical_fail(criterion: Criterion, value: object) -> bool:
    """Kritik mezon muvaffaqiyatsiz bo'lgan-bo'lmaganini aniqlaydi (sof
    predikat): yesno uchun False/yo'q, scale5 uchun maksimal (5) dan kam."""
    if not criterion.critical:
        return False
    if value is None:
        return True
    if criterion.kind == "yesno":
        return not bool(value)
    if criterion.kind == "scale5":
        return int(value) < 5
    raise ValueError(f"noma'lum mezon turi: {criterion.kind}")


def missing_criterion_ids(criteria: list[Criterion], answers: list[Answer]) -> list[str]:
    answered = {a.criterion_id for a in answers}
    return [c.id for c in criteria if c.id not in answered]


def score_pct(criteria: list[Criterion], answers: list[Answer]) -> Decimal:
    """Foizni Decimal(2 xona, ROUND_HALF_UP) qilib qaytaradi. Bo'sh mezonlar
    ro'yxati -> 0.00. Og'irliklar yig'indisi 0 bo'lsa (hammasi 0 og'irlik)
    -> 0.00 (bo'lishga urinmaydi)."""
    by_id = {a.criterion_id: a.value for a in answers}
    total_weight = sum(c.weight for c in criteria)
    if total_weight <= 0:
        return Decimal("0.00")

    for criterion in criteria:
        value = by_id.get(criterion.id)
        if is_critical_fail(criterion, value):
            return Decimal("0.00")

    earned = sum(criterion_fraction(c, by_id.get(c.id)) * c.weight for c in criteria)
    pct = Decimal(str(earned / total_weight * 100))
    return pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
