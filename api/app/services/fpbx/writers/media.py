"""audio (`recordings`) va moh (`music`) yozuvchilari. DB qatori shu yerda,
fayl o'girish (ffmpeg) esa keyin — `apply_job._convert_audio()` (`ctx.audio_jobs`).
`duration_ms` CHECK > 0 — o'girishgacha vaqtinchalik 1, keyin haqiqiy qiymat."""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import func

from app.db.models import AudioFile, MohClass, MohClassFile
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import (
    AudioJob,
    SkipItem,
    WriteCtx,
    dashed,
    lookup_id,
    matches,
    pick,
    unique_name,
)

_LANGUAGES = frozenset({"uz", "ru", "en"})
_MOH_NAME = r"[a-z0-9_-]{1,32}"


def _bundle_file(ctx: WriteCtx, relpath: str | None) -> Path:
    """To'plam ichidagi fayl (yo'l to'plamdan tashqariga chiqmasin)."""
    root = ctx.bundle_dir.resolve()
    src = (root / (relpath or "")).resolve()
    if not relpath or not src.is_file() or not src.is_relative_to(root):
        raise SkipItem("audio_missing", f"Audio fayl to'plamda yo'q: {relpath}")
    return src


async def add_audio(ctx: WriteCtx, *, name: str, language: str | None, relpath: str | None,
                    newest: bool = False) -> str:
    """`newest=True` — `created_at=clock_timestamp()` (bir tranzaksiyadagi `now()`
    hammaga bir xil; yozuvlar (recordings) MOH treklaridan keyingi deb tartiblanadi)."""
    src = _bundle_file(ctx, relpath)
    audio_id = str(uuid.uuid4())
    audio = AudioFile(
        id=audio_id, tenant_id=ctx.tenant_id, name=await unique_name(ctx, AudioFile, name),
        language=pick(language, _LANGUAGES, "uz"), source="upload",
        storage_path=f"sounds/{ctx.tenant_code}/{audio_id}", duration_ms=1,
    )
    if newest:
        audio.created_at = func.clock_timestamp()
    ctx.session.add(audio)
    ctx.audio_jobs.append(AudioJob(audio_id, src, ctx.sounds_dir / ctx.tenant_code / f"{audio_id}.wav"))
    return audio_id


async def write_audio(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    return await add_audio(ctx, name=p.get("name") or entry.name, language=p.get("language"),
                           relpath=p.get("source_relpath"), newest=True)


async def _moh_name(ctx: WriteCtx, name: str) -> str:
    if not matches(_MOH_NAME, name):
        raise SkipItem("moh_name_invalid", f"MOH sinf nomi yaroqsiz: {name}")
    return await unique_name(ctx, MohClass, name, dashed)


async def write_moh(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    name = p.get("name") or entry.name
    moh = MohClass(tenant_id=ctx.tenant_id, name=await _moh_name(ctx, name), shuffle=bool(p.get("shuffle")))
    ctx.session.add(moh)
    await ctx.session.flush()
    ctx.moh_ids[name] = str(moh.id)
    position = 0
    for relpath in p.get("files") or []:
        try:
            audio_id = await add_audio(ctx, name=f"MOH {moh.name} · {Path(relpath).stem}",
                                       language="uz", relpath=relpath)
        except SkipItem as exc:
            ctx.warn(entry.source_ref, exc.code, exc.message)
            continue
        ctx.session.add(MohClassFile(moh_class_id=moh.id, audio_file_id=audio_id, position=position))
        position += 1
    return str(moh.id)


async def moh_id_by_name(ctx: WriteCtx, name: str | None) -> str | None:
    return await lookup_id(ctx, ctx.moh_ids, MohClass.name, name)
