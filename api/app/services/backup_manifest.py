"""Zaxira manifesti — arxiv ichidagi metadata (m4b-contract.md §0/§1).

`format, product_version, alembic_revision, created_at, source_host, components[],
parts[{name,size,sha256}], db_key_fp` (`db_key_fp` = `INNOVA_DB_KEY` ning sha256'idan
16 belgi — kalitning o'zi EMAS, faqat moslikni tekshirish uchun)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from alembic.script import ScriptDirectory
    from sqlalchemy.ext.asyncio import AsyncSession

FORMAT = "INNOVABK1"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


class ManifestError(Exception):
    """Manifest formatini tushunib bo'lmadi (`backup_corrupt`)."""


@dataclass(frozen=True)
class PartInfo:
    name: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True)
class Manifest:
    product_version: str
    alembic_revision: str
    created_at: datetime
    source_host: str
    components: tuple[str, ...]
    parts: tuple[PartInfo, ...]
    db_key_fp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "product_version": self.product_version,
            "alembic_revision": self.alembic_revision,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "source_host": self.source_host,
            "components": list(self.components),
            "parts": [part.to_dict() for part in self.parts],
            "db_key_fp": self.db_key_fp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        if data.get("format") != FORMAT:
            raise ManifestError(f"noma'lum manifest formati: {data.get('format')!r}")
        try:
            return cls(
                product_version=data["product_version"],
                alembic_revision=data["alembic_revision"],
                created_at=datetime.fromisoformat(data["created_at"]),
                source_host=data["source_host"],
                components=tuple(data["components"]),
                db_key_fp=data["db_key_fp"],
                parts=tuple(PartInfo(**part) for part in data["parts"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"manifest to'liq emas: {exc}") from exc


def db_key_fingerprint(db_key: str) -> str:
    return hashlib.sha256(db_key.encode("utf-8")).hexdigest()[:16]


def is_revision_newer(script_dir: Any, manifest_revision: str, current_revision: str) -> bool:
    """`script_dir` — `alembic.script.ScriptDirectory` (yoki shu interfeysga mos
    soxta ob'ekt: `iterate_revisions(upper, lower) -> Iterable[rev-with-.revision]`).
    Manifestdagi reviziya joriyning AJDODI (yoki joriyning O'ZI) bo'lsa — eski/teng
    (False); aks holda (noma'lum yoki avlod) — YANGIROQ (True, 422 `backup_newer`)."""
    if manifest_revision == current_revision:
        return False
    ancestors = {rev.revision for rev in script_dir.iterate_revisions(current_revision, "base")}
    return manifest_revision not in ancestors


async def current_alembic_revision(session: "AsyncSession") -> str:
    """Joriy `alembic_version.version_num` — `is_revision_newer()`ning `current_revision`
    argumenti va manifestga yoziladigan qiymat (`backup_job.py`/`restore_job.py`)."""
    result = await session.execute(text("select version_num from alembic_version"))
    return result.scalar_one()


def load_script_directory() -> "ScriptDirectory":
    """`alembic.ini` (loyiha ildizida, `api/`) dan `ScriptDirectory` — `is_revision_newer()`
    uchun (DB bilan ishlamaydi, faqat `alembic/versions/` fayllarini o'qiydi)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
