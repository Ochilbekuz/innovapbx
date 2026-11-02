"""Zaxira qismlari — har DB jadvali ANIQ bitta toifaga tegishli (m4b-contract.md §0/§1)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.backup_parts import (
    ALL_COMPONENTS,
    ALWAYS_EXCLUDED_TABLES,
    CONFIG_TABLES,
    DEFAULT_COMPONENTS,
    HISTORY_TABLES,
    pg_dump_args,
    validate_components,
)

_SQL_DIR = Path(__file__).resolve().parents[1] / "alembic" / "sql"
_CREATE_TABLE_RE = re.compile(r"create table (?:if not exists )?(\w+)", re.IGNORECASE)


def _all_created_tables() -> set[str]:
    names = set()
    for sql_file in _SQL_DIR.glob("*.sql"):
        names |= set(_CREATE_TABLE_RE.findall(sql_file.read_text()))
    return names


def test_three_lists_are_pairwise_disjoint():
    assert not (CONFIG_TABLES & HISTORY_TABLES)
    assert not (CONFIG_TABLES & ALWAYS_EXCLUDED_TABLES)
    assert not (HISTORY_TABLES & ALWAYS_EXCLUDED_TABLES)


def test_every_table_created_in_sql_is_classified():
    """Har migratsiyada yaratilgan jadval config/history/always_excluded dan
    BIRIDA bo'lishi SHART — yangi jadval qo'shilib tasniflanmasa, bu test qiziladi."""
    classified = CONFIG_TABLES | HISTORY_TABLES | ALWAYS_EXCLUDED_TABLES
    created = _all_created_tables()
    missing = created - classified
    assert not missing, f"backup_parts.py da tasniflanmagan jadval(lar): {missing}"


def test_validate_components_requires_config():
    with pytest.raises(ValueError, match="config"):
        validate_components(["history"])


def test_validate_components_rejects_unknown():
    with pytest.raises(ValueError, match="noma'lum"):
        validate_components(["config", "unknown"])


def test_validate_components_accepts_default_set():
    assert validate_components(list(DEFAULT_COMPONENTS)) == list(DEFAULT_COMPONENTS)


def test_pg_dump_args_always_excludes_backup_tables():
    args = pg_dump_args(["config", "history"])
    for table in ALWAYS_EXCLUDED_TABLES:
        assert f"--exclude-table={table}" in args


def test_pg_dump_args_excludes_history_data_when_history_not_selected():
    args = pg_dump_args(["config"])
    for table in HISTORY_TABLES:
        assert f"--exclude-table-data={table}" in args


def test_pg_dump_args_keeps_history_data_when_history_selected():
    args = pg_dump_args(["config", "history"])
    assert not any("--exclude-table-data=" in a for a in args)


def test_all_components_includes_every_file_component():
    assert set(ALL_COMPONENTS) >= {"sounds", "voicemail", "recordings", "certs", "config", "history"}
