"""Qayta shifrlash registri — to'liqlik va SQL shakli (m4b-contract.md §0/§4.5)."""
from __future__ import annotations

import pytest

from app.db.models import Base
from app.services.crypto_registry import ENCRYPTED_COLUMNS, column_label, rekey_all, rekey_sql


class _FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeSession:
    """Har `execute` chaqiruvida navbatdagi qator-sonini qaytaradi."""

    def __init__(self, rowcounts: list[int]) -> None:
        self._rowcounts = rowcounts
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params):
        self.calls.append((str(stmt), params))
        return _FakeResult(self._rowcounts[len(self.calls) - 1])


def _model_enc_columns() -> set[tuple[str, str]]:
    """`app/db/models.py` dagi barcha `*_enc` bilan tugaydigan ustunlar — ORM
    metadata orqali (qo'lda yurib chiqish o'rniga)."""
    found = set()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name.endswith("_enc"):
                found.add((table.name, column.name))
    return found


def test_every_enc_column_in_models_is_registered():
    registered = {(c.table, c.column) for c in ENCRYPTED_COLUMNS if c.json_path is None}
    missing = _model_enc_columns() - registered
    assert not missing, f"crypto_registry.py da yo'q shifrlangan ustun(lar): {missing}"


def test_registry_has_no_duplicates():
    labels = [column_label(c) for c in ENCRYPTED_COLUMNS]
    assert len(labels) == len(set(labels))


def test_rekey_sql_plain_column_uses_old_and_new_key_params():
    col = next(c for c in ENCRYPTED_COLUMNS if c.table == "trunks")
    sql = rekey_sql(col)
    assert "update trunks set password_enc = encode(pgp_sym_encrypt(" in sql
    assert ":old_key" in sql and ":new_key" in sql
    assert "where coalesce(password_enc, '') <> ''" in sql


def test_rekey_sql_json_path_column_uses_jsonb_set():
    col = next(c for c in ENCRYPTED_COLUMNS if c.json_path)
    sql = rekey_sql(col)
    assert "jsonb_set(provisioning" in sql
    assert "provisioning->>'admin_password_enc'" in sql


def test_column_label_distinguishes_json_path():
    col = next(c for c in ENCRYPTED_COLUMNS if c.json_path)
    assert column_label(col) == "system_settings.provisioning.admin_password_enc"


def test_rekey_sql_nested_json_path_uses_path_operator():
    col = next(c for c in ENCRYPTED_COLUMNS if c.json_path == "targets.s3.secret_key_enc")
    sql = rekey_sql(col)
    assert "backup#>>'{targets,s3,secret_key_enc}'" in sql
    assert "jsonb_set(backup, '{targets,s3,secret_key_enc}'" in sql
    assert "where coalesce(backup#>>'{targets,s3,secret_key_enc}', '') <> ''" in sql


def test_all_backup_settings_secrets_are_registered():
    labels = {column_label(c) for c in ENCRYPTED_COLUMNS}
    assert "system_settings.backup.passphrase_enc" in labels
    assert "system_settings.backup.targets.s3.secret_key_enc" in labels
    assert "system_settings.backup.targets.sftp.password_enc" in labels
    assert "system_settings.backup.targets.sftp.key_enc" in labels


@pytest.mark.asyncio
async def test_rekey_all_runs_every_registered_column_and_sums_rowcounts():
    session = _FakeSession(rowcounts=[1] * len(ENCRYPTED_COLUMNS))
    counts = await rekey_all(session, old_key="old", new_key="new")
    assert len(session.calls) == len(ENCRYPTED_COLUMNS)
    assert set(counts) == {column_label(c) for c in ENCRYPTED_COLUMNS}
    assert all(n == 1 for n in counts.values())
    for _, params in session.calls:
        assert params == {"old_key": "old", "new_key": "new"}


@pytest.mark.asyncio
async def test_rekey_all_reports_zero_when_no_rows_matched():
    session = _FakeSession(rowcounts=[0] * len(ENCRYPTED_COLUMNS))
    counts = await rekey_all(session, old_key="old", new_key="new")
    assert all(n == 0 for n in counts.values())
