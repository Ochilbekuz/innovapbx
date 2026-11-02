"""Zaxira manifesti — serializatsiya va moslik tekshiruvi (m4b-contract.md §0/§1)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.backup_manifest import (
    Manifest,
    ManifestError,
    PartInfo,
    db_key_fingerprint,
    is_revision_newer,
)


def _manifest(**overrides) -> Manifest:
    base = dict(
        product_version="0.1.0", alembic_revision="0021", created_at=datetime.now(timezone.utc),
        source_host="pbx1", components=("config", "history"),
        parts=(PartInfo("config.dump", 100, "a" * 64),), db_key_fp="f" * 16,
    )
    base.update(overrides)
    return Manifest(**base)


def test_round_trip_to_dict_and_back():
    manifest = _manifest()
    restored = Manifest.from_dict(manifest.to_dict())
    assert restored == manifest


def test_to_dict_has_format_marker():
    assert _manifest().to_dict()["format"] == "INNOVABK1"


def test_from_dict_rejects_unknown_format():
    data = _manifest().to_dict()
    data["format"] = "OTHER"
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_from_dict_rejects_missing_field():
    data = _manifest().to_dict()
    del data["db_key_fp"]
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_db_key_fingerprint_is_short_and_deterministic():
    fp1 = db_key_fingerprint("sirli-kalit")
    fp2 = db_key_fingerprint("sirli-kalit")
    assert fp1 == fp2
    assert len(fp1) == 16


def test_db_key_fingerprint_differs_for_different_keys():
    assert db_key_fingerprint("a") != db_key_fingerprint("b")


class _Rev:
    def __init__(self, revision: str) -> None:
        self.revision = revision


class _FakeScriptDir:
    """`0019 <- 0020 <- 0021` zanjiri — `iterate_revisions(upper, 'base')` ustidan yuradi."""

    CHAIN = ["0021", "0020", "0019", "0018"]

    def iterate_revisions(self, upper: str, lower: str):  # noqa: ARG002
        idx = self.CHAIN.index(upper)
        return [_Rev(r) for r in self.CHAIN[idx:]]


def test_same_revision_is_not_newer():
    assert is_revision_newer(_FakeScriptDir(), "0020", "0020") is False


def test_ancestor_revision_is_not_newer():
    assert is_revision_newer(_FakeScriptDir(), "0018", "0021") is False


def test_descendant_or_unknown_revision_is_newer():
    assert is_revision_newer(_FakeScriptDir(), "0021", "0020") is True
    assert is_revision_newer(_FakeScriptDir(), "9999", "0020") is True
