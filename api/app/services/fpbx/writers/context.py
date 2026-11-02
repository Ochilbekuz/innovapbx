"""M5a apply — barcha yozuvchilar (`writers/<guruh>.py`) bo'lishadigan holat.
`WriteCtx` BITTA apply chaqiruvi davomida yashaydi: yaratilgan call_target/entity
id'lari (`$ref` hal qilish uchun), keyin o'giriladigan audio ro'yxati, ogohlantirishlar
va hisoblagichlar. Bu yerda commit YO'Q — tranzaksiya chegarasi `apply_job.py`da."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fpbx.mappers import Entry


class CodedError(Exception):
    """Mashina o'qiydigan `code` + inson uchun `message` (sirsiz)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SkipItem(CodedError):
    """Yozuvchi elementni YARATMAYDI (masalan, sana band) — ogohlantirish sifatida
    yoziladi, ish davom etadi (atomarlik buzilmaydi: hech narsa qo'shilmagan)."""


class WriteError(CodedError):
    """Majburiy bog'liqlik hal bo'lmadi — butun import bekor (rollback)."""


@dataclass
class AudioJob:
    audio_id: str
    src: Path
    dst: Path


@dataclass
class WriteCtx:
    session: AsyncSession
    tenant_id: str
    tenant_code: str
    job_id: str
    bundle_dir: Path
    sounds_dir: Path
    rotate_weak: bool = False
    targets: dict[str, str] = field(default_factory=dict)
    entities: dict[str, str] = field(default_factory=dict)
    ext_ids: dict[str, str] = field(default_factory=dict)
    moh_ids: dict[str, str] = field(default_factory=dict)
    audio_jobs: list[AudioJob] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    rotated: list[str] = field(default_factory=list)
    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)  # `<kind>:<source_ref>` -> sabab kodi
    builtin: dict[str, str] = field(default_factory=dict)

    def warn(self, source_ref: str | None, code: str, message: str) -> None:
        self.warnings.append({"code": code, "message": message, "source_ref": source_ref})

    def target_for(self, entry: Entry) -> str:
        return self.targets[entry_key(entry)]


def entry_key(entry: Entry) -> str:
    """`$ref` qiymati bilan BIR XIL shakl (`mappers.ref()`): `<kind>:<source_ref>`."""
    return f"{entry.kind}:{entry.source_ref}"


def clamp(value: Any, low: int, high: int | None, default: int) -> int:
    """Manba qiymati Innova CHECK chegarasidan tashqarida bo'lsa — eng yaqin chegara."""
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    if high is not None and value > high:
        return high
    return max(value, low)


def pick(value: Any, allowed: frozenset[str] | set[str], default: str) -> str:
    return value if value in allowed else default


def matches(pattern: str, value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _spaced(name: str, n: int) -> str:
    return f"{name} ({n})"


def dashed(name: str, n: int) -> str:
    return f"{name}-{n}"[:32]


async def unique_name(
    ctx: WriteCtx, model: Any, name: str, fmt: Callable[[str, int], str] = _spaced,
) -> str:
    """`(tenant_id, name)` UNIQUE jadvallar — band bo'lsa `nom (2)`, `nom (3)`..."""
    candidate, n = name, 1
    while (await ctx.session.execute(
        select(model.id).where(model.tenant_id == ctx.tenant_id, model.name == candidate).limit(1)
    )).first() is not None:
        n += 1
        candidate = fmt(name, n)
    return candidate


async def lookup_id(ctx: WriteCtx, cache: dict[str, str], column: Any, value: str | None) -> str | None:
    """Shu apply'da yaratilgan (`cache`) YOKI Innova'da mavjud (qo'lda) obyekt id'si."""
    if not value:
        return None
    if value in cache:
        return cache[value]
    model = column.class_
    row = (await ctx.session.execute(
        select(model.id).where(model.tenant_id == ctx.tenant_id, column == value).limit(1)
    )).first()
    return str(row[0]) if row is not None else None
