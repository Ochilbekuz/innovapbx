"""Ko'p-buyruqli (`;` bilan ajratilgan) xom SQL fayllarni migratsiyalarda bajarish.

Nega `op.execute()`/`exec_driver_sql()` EMAS: ilova `asyncpg` drayveri bilan
ishlaydi, u esa HAR DOIM tayyorlangan bayonot (prepared statement) orqali
yuboradi — bitta bayonotda bittadan ortiq SQL buyrug'i bo'lsa, asyncpg
"cannot insert multiple commands into a prepared statement" bilan rad etadi
(0001/0002 fayllarida o'nlab `create table`/`create view`/`do $$ ... $$`
buyruqlari ketma-ket). Yagona oddiy va ishonchli yechim — `psql`ning sodda
so'rov protokoli (u istalgan sondagi buyruqni bitta faylda qabul qiladi,
`format('...%I...', ...)` kabi PL/pgSQL ichidagi `%`larni ham muammosiz
o'tkazadi — client-side parametr skanerlash yo'q). Bu modul `app/db/` ostida
(`alembic/` emas) — chunki `alembic/` papkasi `__init__.py`siz, PyPI
`alembic` paketi bilan nom to'qnashuvi xavfi bor."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import settings


def libpq_env() -> dict[str, str]:
    """`DATABASE_URL`dan `psql`/`pg_dump`/`pg_restore` uchun `PG*` muhit o'zgaruvchilari
    (`backup_job.py`/`restore_job.py` ham ishlatadi — DRY, bir xil parslash)."""
    parts = urlsplit(settings.database_url.replace("+asyncpg", ""))
    env = dict(os.environ)
    env["PGHOST"] = parts.hostname or "localhost"
    env["PGPORT"] = str(parts.port or 5432)
    env["PGUSER"] = parts.username or ""
    env["PGPASSWORD"] = parts.password or ""
    env["PGDATABASE"] = parts.path.lstrip("/") or ""
    return env


def run_sql_file(path: Path) -> None:
    subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)],
        env=libpq_env(), check=True,
    )


def run_sql_text(sql: str) -> None:
    subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-q"],
        input=sql, text=True, env=libpq_env(), check=True,
    )
