"""`app/services/fpbx/plan.py::analyze()` — haqiqiy to'plam (`tests/freepbx-fixture/
bundle/fpbx-export-fixture.tar.gz`) ustida. DB'siz: to'qnashuv so'rovlari uchun
soxta sessiya (`execute(query).first()` -> None, hech qanday to'qnashuv yo'q)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.fpbx import bundle
from app.services.fpbx import plan as plan_mod

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "freepbx-fixture" / "bundle" / "fpbx-export-fixture.tar.gz"

SECRET_NEEDLES = ("SinovSecret", "SinovTrunkSecret", "SinovRoutePass", "1105", "4321", "4242")

_EXPECTED_CREATE_COUNTS = {
    "extension": 6, "trunk": 2, "inbound_route": 3, "outbound_route": 2, "ring_group": 1,
    "queue": 1, "ivr": 1, "time_group": 1, "holiday": 1, "time_condition": 1,
    "announcement": 1, "audio": 1, "moh": 1, "conference": 1, "voicemail": 1,
    "blacklist": 1, "feature_code": 1,
}


class _NoConflictResult:
    def first(self):
        return None


class _NoConflictSession:
    """`plan.analyze()` to'qnashuv tekshiruvi uchun FAQAT `execute(select(...)).first()`
    chaqiradi — bo'sh Innova DB'ni simulyatsiya qiladi (hech qanday raqam/kod band emas)."""

    async def execute(self, _query):
        return _NoConflictResult()


@pytest.fixture(scope="module")
def extracted(tmp_path_factory) -> Path:
    dest_dir = tmp_path_factory.mktemp("fpbx-plan-bundle")
    bundle.extract_bundle(FIXTURE, dest_dir, max_total_bytes=20 * 1024 * 1024 * 1024)
    return bundle.find_bundle_root(dest_dir)


@pytest.fixture(scope="module")
def analysis(extracted: Path):
    import asyncio

    return asyncio.run(plan_mod.analyze(extracted, _NoConflictSession(), "t1"))


def _by_kind_action_counts(analysis) -> dict[str, dict[str, int]]:
    return plan_mod.summary_by_kind(analysis.items)


def test_create_counts_match_fixture(analysis) -> None:
    counts = _by_kind_action_counts(analysis)
    for kind, expected in _EXPECTED_CREATE_COUNTS.items():
        actual = counts.get(kind, {}).get("create", 0)
        assert actual == expected, f"{kind}: kutilgan {expected}, olingan {actual}"


def test_extension_numbers_match_fixture(analysis) -> None:
    numbers = sorted(
        e.number for e in analysis.items if e.kind == "extension" and e.action == "create"
    )
    assert numbers == ["101", "102", "103", "105", "106", "107"]


def test_moh_default_is_not_created(analysis) -> None:
    moh_default = next(e for e in analysis.items if e.kind == "moh" and e.name == "default")
    assert moh_default.action != "create"


def test_ignored_voicemail_without_extension(analysis) -> None:
    assert any(
        "1234" in item["key"] and "voicemail" in item["table"] for item in analysis.ignored
    )


def test_custom_dialplan_warning_present(analysis) -> None:
    assert any(w["code"] == "custom_dialplan_present" for w in analysis.warnings)


def test_extension_101_has_secret(analysis) -> None:
    ext_101 = next(e for e in analysis.items if e.kind == "extension" and e.number == "101")
    assert ext_101.has_secret is True


def test_no_secrets_leak_into_public_fields(analysis) -> None:
    rendered = repr([e.public_dict() for e in analysis.items]) + repr(analysis.ignored) + repr(analysis.warnings)
    for needle in SECRET_NEEDLES:
        assert needle not in rendered, f"sir sizib chiqdi: {needle}"


def test_no_silent_loss_every_item_has_kind_and_source_ref(analysis) -> None:
    for entry in analysis.items:
        assert entry.kind and entry.source_ref
    for item in analysis.ignored:
        assert item["table"] and item["reason"]


def test_entries_are_deterministic_across_calls(extracted: Path) -> None:
    import asyncio

    first = asyncio.run(plan_mod.analyze(extracted, _NoConflictSession(), "t1"))
    second = asyncio.run(plan_mod.analyze(extracted, _NoConflictSession(), "t1"))
    assert [e.public_dict() for e in first.items] == [e.public_dict() for e in second.items]
