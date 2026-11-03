"""`app/services/qa.py` sof qismlari — ORM'ga bog'liq emas (duck-typing orqali
sinaladi, haqiqiy DB kerak emas)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.qa import answers_from_payload, compute_score_pct, criteria_from_checklist


@dataclass
class _FakeCriterion:
    id: str
    kind: str
    weight: float
    critical: bool = False


@dataclass
class _FakeChecklist:
    criteria: list[_FakeCriterion] = field(default_factory=list)


def test_criteria_from_checklist_maps_fields():
    checklist = _FakeChecklist(criteria=[_FakeCriterion(id="c1", kind="yesno", weight=2.0, critical=True)])
    criteria = criteria_from_checklist(checklist)
    assert len(criteria) == 1
    assert criteria[0].id == "c1" and criteria[0].kind == "yesno"
    assert criteria[0].weight == 2.0 and criteria[0].critical is True


def test_answers_from_payload_maps_dict_to_answers():
    answers = answers_from_payload({"c1": True, "c2": 3})
    by_id = {a.criterion_id: a.value for a in answers}
    assert by_id == {"c1": True, "c2": 3}


def test_compute_score_pct_full_marks():
    checklist = _FakeChecklist(criteria=[_FakeCriterion(id="c1", kind="yesno", weight=1.0)])
    assert compute_score_pct(checklist, {"c1": True}) == 100.0


def test_compute_score_pct_critical_fail_is_zero():
    checklist = _FakeChecklist(criteria=[_FakeCriterion(id="c1", kind="yesno", weight=1.0, critical=True)])
    assert compute_score_pct(checklist, {"c1": False}) == 0.0
