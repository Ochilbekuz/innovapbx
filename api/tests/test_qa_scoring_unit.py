"""QA ball hisobi sof funksiyalari — m10-onlinepbx-contract.md Bo'lak B1."""
from __future__ import annotations

from decimal import Decimal

from app.services.qa_scoring import Answer, Criterion, is_critical_fail, missing_criterion_ids, score_pct


def test_score_pct_all_yesno_full_marks():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", True), Answer("c2", True)]
    assert score_pct(criteria, answers) == Decimal("100.00")


def test_score_pct_all_yesno_zero():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", False), Answer("c2", False)]
    assert score_pct(criteria, answers) == Decimal("0.00")


def test_score_pct_mixed_yesno_half():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", True), Answer("c2", False)]
    assert score_pct(criteria, answers) == Decimal("50.00")


def test_score_pct_scale5_full_marks():
    criteria = [Criterion("c1", "scale5", weight=2.0)]
    answers = [Answer("c1", 5)]
    assert score_pct(criteria, answers) == Decimal("100.00")


def test_score_pct_scale5_min_is_zero():
    criteria = [Criterion("c1", "scale5", weight=2.0)]
    answers = [Answer("c1", 1)]
    assert score_pct(criteria, answers) == Decimal("0.00")


def test_score_pct_scale5_middle_value():
    # (3-1)/4 = 0.5 -> 50%
    criteria = [Criterion("c1", "scale5", weight=1.0)]
    answers = [Answer("c1", 3)]
    assert score_pct(criteria, answers) == Decimal("50.00")


def test_score_pct_weighted_average():
    criteria = [Criterion("c1", "yesno", weight=3.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", True), Answer("c2", False)]
    # (3*1 + 1*0) / 4 = 0.75 -> 75%
    assert score_pct(criteria, answers) == Decimal("75.00")


def test_score_pct_critical_yesno_fail_zeroes_everything():
    criteria = [
        Criterion("c1", "yesno", weight=1.0, critical=True),
        Criterion("c2", "yesno", weight=1.0),
    ]
    answers = [Answer("c1", False), Answer("c2", True)]
    assert score_pct(criteria, answers) == Decimal("0.00")


def test_score_pct_critical_scale5_below_max_zeroes_everything():
    criteria = [
        Criterion("c1", "scale5", weight=1.0, critical=True),
        Criterion("c2", "yesno", weight=1.0),
    ]
    answers = [Answer("c1", 4), Answer("c2", True)]
    assert score_pct(criteria, answers) == Decimal("0.00")


def test_score_pct_critical_scale5_at_max_does_not_zero():
    criteria = [
        Criterion("c1", "scale5", weight=1.0, critical=True),
        Criterion("c2", "yesno", weight=1.0),
    ]
    answers = [Answer("c1", 5), Answer("c2", True)]
    assert score_pct(criteria, answers) == Decimal("100.00")


def test_score_pct_missing_critical_answer_counts_as_fail():
    criteria = [Criterion("c1", "yesno", weight=1.0, critical=True)]
    answers: list[Answer] = []
    assert score_pct(criteria, answers) == Decimal("0.00")


def test_score_pct_missing_non_critical_answer_counts_as_zero_fraction():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", True)]
    assert score_pct(criteria, answers) == Decimal("50.00")


def test_score_pct_empty_criteria_is_zero():
    assert score_pct([], []) == Decimal("0.00")


def test_score_pct_rounds_half_up_to_two_decimals():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0),
                Criterion("c3", "yesno", weight=1.0)]
    answers = [Answer("c1", True), Answer("c2", False), Answer("c3", False)]
    # 1/3 * 100 = 33.333... -> 33.33
    assert score_pct(criteria, answers) == Decimal("33.33")


def test_is_critical_fail_non_critical_always_false():
    c = Criterion("c1", "yesno", weight=1.0, critical=False)
    assert is_critical_fail(c, False) is False


def test_missing_criterion_ids_returns_unanswered():
    criteria = [Criterion("c1", "yesno", weight=1.0), Criterion("c2", "yesno", weight=1.0)]
    answers = [Answer("c1", True)]
    assert missing_criterion_ids(criteria, answers) == ["c2"]
