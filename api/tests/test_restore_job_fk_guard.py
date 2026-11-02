"""`_pg_restore()` FK-qalqon sinovlari (m4b-contract.md §4 band 4/5).

Bug: `backups`/`backup_copies`/`restore_jobs` (`backup_parts.ALWAYS_EXCLUDED_TABLES`)
`pg_dump`dan ATAYLAB chiqarib tashlanadi ("tarix yo'qolmasin"), lekin ularning
`users`/`tenants`ga ISHORA qiluvchi FOREIGN KEY'lari dump TOC'sida YO'Q bo'lib qoladi.
Natijada haqiqiy Postgres'da `pg_restore --clean` `users_pkey`/`tenants_pkey`ni DROP
qilolmaydi ("other objects depend on it") — HAR bir tiklash (bullet 4: shu serverga,
bullet 5: disaster recovery) ishlamay qoladi. Tuzatish: `_pg_restore()` endi bu FK'larni
tiklashdan OLDIN vaqtincha DROP qiladi va (pg_restore muvaffaqiyatli bo'lsa ham, xato
bersa ham — `finally`) `NOT VALID` bilan QAYTA tiklaydi (MAVJUD qatorlarga TEGMAYDI —
tiklash paytida `tenants`/`users` eski holatga almashgach, `restore_jobs`/`backups`dagi
jonli qatorlar — jumladan AYNAN SHU ishni kuzatuvchi qator! — "yetim" bo'lib qolishi
mumkin; ularni O'CHIRISH/NULL qilish tarixni yo'qotardi, shu sabab FAQAT kelgusi
yozuvlarga amal qiladi, eskilarini tekshirmaydi ham, o'zgartirmaydi ham)."""
from __future__ import annotations

import subprocess

import pytest

from app.services import restore_job as mod


def _completed(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture(autouse=True)
def _fixed_env(monkeypatch):
    monkeypatch.setattr(mod, "libpq_env", lambda: {"PGDATABASE": "innova"})


def _fk_rows() -> str:
    # conrelid conname defn confdeltype column — real pg_constraint ustunlari tartibida
    return "\n".join([
        "backups\tbackups_created_by_fkey\tFOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL\tn\tcreated_by",
        "restore_jobs\trestore_jobs_tenant_id_fkey\tFOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE\tc\ttenant_id",
    ])


def _patch_subprocess(monkeypatch, *, pg_restore_error: subprocess.CalledProcessError | None):
    calls: list[list[str]] = []

    def fake_run(args, **_kw):
        calls.append(list(args))
        if args[0] == "pg_restore":
            if pg_restore_error is not None:
                raise pg_restore_error
            return _completed()
        if args[0] == "psql" and any("select conrelid" in a for a in args):
            return _completed(_fk_rows())
        return _completed()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    return calls


def _sql_of(call: list[str]) -> str:
    return call[-1] if call and call[0] == "psql" else ""


# ---------------------------------------------------------------- muvaffaqiyatli yo'l
def test_pg_restore_drops_fks_before_and_restores_after_success(monkeypatch, tmp_path):
    calls = _patch_subprocess(monkeypatch, pg_restore_error=None)

    mod._pg_restore(tmp_path / "database.dump")

    drop_calls = [c for c in calls if "drop constraint" in _sql_of(c)]
    add_calls = [c for c in calls if "add constraint" in _sql_of(c)]
    restore_idx = next(i for i, c in enumerate(calls) if c[0] == "pg_restore")

    assert {name for c in drop_calls for name in ("backups_created_by_fkey", "restore_jobs_tenant_id_fkey")
            if name in _sql_of(c)} == {"backups_created_by_fkey", "restore_jobs_tenant_id_fkey"}
    assert len(add_calls) == 2
    # ikkisi ham DROP -> pg_restore -> ADD tartibida (FK pg_restore paytida DROP qilingan bo'lishi kerak)
    assert all(calls.index(c) < restore_idx for c in drop_calls)
    assert all(calls.index(c) > restore_idx for c in add_calls)


def test_pg_restore_readds_fks_not_valid_without_touching_existing_rows(monkeypatch, tmp_path):
    """Eski (yetim bo'lib qolgan) qatorlarga TEGMAYDI -- hech qanday UPDATE/DELETE
    chaqirilmaydi, FAQAT `add constraint ... not valid` (m4b-contract.md §4 band 5:
    AYNAN shu tiklash ishini kuzatuvchi `restore_jobs` qatori O'CHIRILIB KETMASLIGI shart)."""
    calls = _patch_subprocess(monkeypatch, pg_restore_error=None)

    mod._pg_restore(tmp_path / "database.dump")

    sqls = [_sql_of(c) for c in calls]
    assert not any(s.strip().lower().startswith("update ") for s in sqls)
    assert not any(s.strip().lower().startswith("delete ") for s in sqls)
    add_calls = [s for s in sqls if "add constraint" in s]
    assert all(s.rstrip().lower().endswith("not valid") for s in add_calls)


# ---------------------------------------------------------------- pg_restore xato beradi
def test_pg_restore_still_restores_fks_when_pg_restore_fails(monkeypatch, tmp_path):
    err = subprocess.CalledProcessError(1, ["pg_restore"], output="", stderr="ERROR: namuna xato")
    calls = _patch_subprocess(monkeypatch, pg_restore_error=err)

    with pytest.raises(RuntimeError, match="namuna xato"):
        mod._pg_restore(tmp_path / "database.dump")

    add_calls = [c for c in calls if "add constraint" in _sql_of(c)]
    assert len(add_calls) == 2, "pg_restore xato bersa ham FK'lar HAR DOIM qaytarilishi kerak (finally)"


def test_excluded_table_fk_defs_queries_only_cross_boundary_fks(monkeypatch):
    seen_queries: list[str] = []

    def fake_run(args, **_kw):
        seen_queries.append(args[-1])
        return _completed(_fk_rows())

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    rows = mod._excluded_table_fk_defs()

    assert len(rows) == 2
    query = seen_queries[0]
    for excluded in ("backups", "backup_copies", "restore_jobs"):
        assert f"'{excluded}'" in query
    assert "confrelid::regclass::text not in" in query
