"""M5a apply fon vazifasi (m5a-contract.md §0/§3): pre_import zaxira -> qayta
tahlil + eskirish tekshiruvi -> BITTA tranzaksiyada barcha obyektlar (`writers`) ->
audio o'girish -> BITTA dialplan reviziyasi «FreePBX importi» -> audit -> commit.
Har qanday xato: rollback, shu ish yaratgan audio fayllar o'chiriladi, reviziya
yo'q, `status=failed`, `error{code,message}` (sirsiz, SQL parametrlarisiz)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code
from app.db.models import AudioFile, MigrationJob
from app.services import backup_job, backup_parts
from app.services.apply import apply_config
from app.services.audio_tools import AudioConversionError, convert_to_wav_8k_mono
from app.services.audit import record_audit
from app.services.conference import apply_confbridge
from app.services.fpbx import plan as plan_mod
from app.services.fpbx.apply_plan import Decision, PlanStaleError, resolve_final_actions
from app.services.fpbx.writers import TestFailError, WriteCtx, maybe_test_fail, write_entries
from app.services.fpbx.writers.context import CodedError, entry_key
from app.services.job_lock import JobLock
from app.services.live_status import reload_pjsip
from app.services.moh import apply_moh
from app.services.voicemail import apply_voicemail

log = logging.getLogger(__name__)

_MAX_ERROR_MESSAGE = 500
REVISION_NOTE = "FreePBX importi"
# Sarlavhasiz (raw) Asterisk formatlari — ffmpeg o'zi aniqlay olmaydi.
_RAW_INPUTS: dict[str, tuple[str, ...]] = {
    ".ulaw": ("-f", "mulaw", "-ar", "8000", "-ac", "1"), ".ul": ("-f", "mulaw", "-ar", "8000", "-ac", "1"),
    ".mulaw": ("-f", "mulaw", "-ar", "8000", "-ac", "1"), ".alaw": ("-f", "alaw", "-ar", "8000", "-ac", "1"),
    ".al": ("-f", "alaw", "-ar", "8000", "-ac", "1"), ".sln": ("-f", "s16le", "-ar", "8000", "-ac", "1"),
    ".raw": ("-f", "s16le", "-ar", "8000", "-ac", "1"), ".sln16": ("-f", "s16le", "-ar", "16000", "-ac", "1"),
    ".sln48": ("-f", "s16le", "-ar", "48000", "-ac", "1"), ".gsm": ("-f", "gsm",), ".g722": ("-f", "g722",),
}
# Commit'dan KEYIN Asterisk'ka yetkaziladigan qismlar (xatosi — ogohlantirish).
_POST_APPLY = (("moh", apply_moh), ("voicemail", apply_voicemail), ("conference", apply_confbridge))


class ApplyError(CodedError):
    """Apply bosqichi xatosi (zaxira, audio, dialplan) — `error.code` shu."""


_CODED_ERRORS = (CodedError, TestFailError, PlanStaleError)


@dataclass
class _Snapshot:
    """Ish qatoridan BIR MARTA o'qilgan qiymatlar (keyingi commit/rollback'larga bog'liq emas)."""

    job_id: str
    tenant_id: str
    bundle_dir: Path
    stored_items: list[dict[str, Any]]
    rotate_weak: bool


def ffmpeg_input_args(src: Path) -> tuple[str, ...]:
    return _RAW_INPUTS.get(src.suffix.lower(), ())


def error_of(exc: BaseException) -> dict[str, str]:
    """Xavfsiz xato: DB xatosidan faqat birinchi qator (parametrlar/qator qiymatlari YO'Q)."""
    message = str(exc.orig).splitlines()[0] if isinstance(exc, DBAPIError) else str(exc)
    code = exc.code if isinstance(exc, _CODED_ERRORS) else "apply_failed"  # SQLAlchemy'ning `code`i EMAS
    return {"code": code,
            "message": (message or type(exc).__name__)[:_MAX_ERROR_MESSAGE]}


async def run_apply_job(
    session_factory: async_sessionmaker, lock: JobLock, job_id: str, tenant_id: str, *,
    ami: Any, user_id: str | None = None,
) -> None:
    """Qulf (`job_lock`) endpoint'da olingan — shu yerda `finally`da bo'shatiladi."""
    try:
        async with session_factory() as session:
            await _run(session_factory, session, job_id, tenant_id, ami=ami, user_id=user_id)
    finally:
        await lock.release()


async def _run(session_factory: async_sessionmaker, session: AsyncSession, job_id: str, tenant_id: str, *,
               ami: Any, user_id: str | None) -> None:
    job = await session.get(MigrationJob, job_id)
    if job is None or str(job.tenant_id) != tenant_id:
        return
    snap = _Snapshot(job_id=str(job.id), tenant_id=tenant_id, bundle_dir=Path(job.bundle_path or ""),
                     stored_items=list((job.plan or {}).get("items") or []),
                     rotate_weak=bool((job.options or {}).get("rotate_weak_secrets")))
    created_files: list[Path] = []
    try:
        ctx, result = await _apply(session_factory, session, job, snap, created_files, ami=ami, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — har qanday xato -> rollback + failed (stek logga YO'Q)
        error = error_of(exc)
        log.warning("M5a apply %s muvaffaqiyatsiz: %s (%s)", job_id, error["code"], type(exc).__name__)
        await session.rollback()
        _unlink(created_files)
        await _mark_failed(session, job_id, error)
        return
    await _progress(session_factory, job_id, "finalize", 95)
    await _finish(session, job, with_problems(result, await _post_apply_problems(session, ctx, ami)))


async def _apply(session_factory: async_sessionmaker, session: AsyncSession, job: MigrationJob, snap: _Snapshot,
                 created_files: list[Path], *, ami: Any, user_id: str | None) -> tuple[WriteCtx, dict[str, Any]]:
    await _progress(session_factory, snap.job_id, "backup", 5)
    job.pre_import_backup_id = await _pre_import_backup(session, snap.tenant_id)
    await session.commit()

    await _progress(session_factory, snap.job_id, "analyze", 25)
    analysis = await plan_mod.analyze(snap.bundle_dir, session, snap.tenant_id)
    decisions = resolve_final_actions(snap.stored_items, analysis.items)

    await _progress(session_factory, snap.job_id, "write", 40)
    ctx = WriteCtx(session=session, tenant_id=snap.tenant_id, tenant_code=await get_tenant_code(session, snap.tenant_id),
                   job_id=snap.job_id, bundle_dir=snap.bundle_dir, sounds_dir=Path(settings.sounds_dir),
                   rotate_weak=snap.rotate_weak)
    _note_unwritten(ctx, decisions)
    await write_entries(ctx, [d.entry for d in decisions if d.write])

    await _progress(session_factory, snap.job_id, "audio", 70)
    await _convert_audio(session, ctx, created_files)
    maybe_test_fail("audio")

    await _progress(session_factory, snap.job_id, "dialplan", 85)
    revision_id = await _apply_dialplan(session, snap.tenant_id, user_id, ami)
    result = build_result(ctx, decisions, revision_id)
    await record_audit(session, tenant_id=snap.tenant_id, user_id=user_id, action="migration.apply",
                       entity="migration", entity_id=snap.job_id,
                       diff={"op": "apply", "note": REVISION_NOTE, "counts": result["created"],
                             "skipped": result["skipped"], "rotated": len(ctx.rotated)})
    await session.commit()  # obyektlar + migration_items + revision + audit — BITTA tranzaksiya
    return ctx, result


async def _finish(session: AsyncSession, job: MigrationJob, result: dict[str, Any]) -> None:
    """`ok` — fayl/registratsiya ishlaridan (`_post_apply_problems`) KEYIN: `ok` ko'ringanda
    Asterisk modullari qayta yuklanib bo'lgan (proof §5 darhol `pjsip show endpoint` qiladi)."""
    await session.refresh(job)  # step/progress alohida sessiyada yozilgan — eski qiymat bilan solishtirilmasin
    job.status, job.step, job.progress, job.error = "ok", None, 100, None
    job.result = result
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()


async def _progress(session_factory: async_sessionmaker, job_id: str, step: str, progress: int) -> None:
    """Asosiy sessiya BITTA uzun tranzaksiyada — bosqich alohida qisqa sessiyada yoziladi."""
    async with session_factory() as progress_session:
        await progress_session.execute(
            update(MigrationJob).where(MigrationJob.id == job_id).values(step=step, progress=progress))
        await progress_session.commit()


async def _pre_import_backup(session: AsyncSession, tenant_id: str) -> str:
    """`restore_job._create_pre_restore_backup` qolipi; parolsiz/xato — import YO'Q."""
    try:
        backup = await backup_job.create_backup_record(
            session, tenant_id=tenant_id, kind="pre_import",
            components=list(backup_parts.DEFAULT_COMPONENTS), created_by=None,
        )
    except backup_job.PassphraseRequiredError as exc:
        raise ApplyError("passphrase_required", "Zaxira paroli o'rnatilmagan") from exc
    await session.commit()
    await backup_job._run_backup_job(session, backup.id, tenant_id)  # qulf bizda — PUBLIC emas
    if backup.status == "failed":
        raise ApplyError("backup_failed", "pre_import zaxira muvaffaqiyatsiz — import boshlanmadi")
    return str(backup.id)


def _note_unwritten(ctx: WriteCtx, decisions: list[Decision]) -> None:
    for decision in decisions:
        if decision.note:
            ctx.skipped[entry_key(decision.entry)] = decision.note
            if decision.note == "replace_unsupported":
                ctx.warn(decision.entry.source_ref, decision.note,
                         "Almashtirish (replace) qo'llab-quvvatlanmaydi — mavjud obyekt saqlandi")


async def _convert_audio(session: AsyncSession, ctx: WriteCtx, created_files: list[Path]) -> None:
    for job in ctx.audio_jobs:
        created_files.append(job.dst)
        try:
            duration = await asyncio.to_thread(convert_to_wav_8k_mono, job.src, job.dst, ffmpeg_input_args(job.src))
        except AudioConversionError as exc:
            raise ApplyError("audio_failed", f"Audio o'girilmadi: {job.src.name}") from exc
        await session.execute(update(AudioFile).where(AudioFile.id == job.audio_id).values(duration_ms=duration))


async def _apply_dialplan(session: AsyncSession, tenant_id: str, user_id: str | None, ami: Any) -> str | None:
    try:
        res = await apply_config(session, tenant_id=tenant_id, user_id=user_id, ami=ami)
    except ApiError as exc:
        raise ApplyError(exc.code, exc.message) from exc
    if res.status == "rolled_back":
        raise ApplyError("apply_failed", res.message or "Dialplan qo'llanmadi")
    return str(res.revision) if res.revision is not None else None


def build_result(ctx: WriteCtx, decisions: list[Decision], revision_id: str | None) -> dict[str, Any]:
    """`ResultOut` maydonlari + CSV uchun qo'shimcha (`rotated` — faqat source_ref, `not_created`)."""
    created = sum(ctx.created.values())
    return {
        "created": dict(ctx.created), "skipped": len(decisions) - created, "warnings": len(ctx.warnings),
        "revision_id": revision_id, "rotated": list(ctx.rotated), "not_created": dict(ctx.skipped),
        "warning_items": ctx.warnings[:200],
    }


def with_problems(result: dict[str, Any], problems: list[dict[str, Any]]) -> dict[str, Any]:
    """MOH/pochta/konferensiya fayllari va trunk registratsiyasi xatosi — import qaytarilmaydi
    (ma'lumot commit qilingan), natijaga ogohlantirish bo'lib qo'shiladi."""
    return {**result, "warnings": result["warnings"] + len(problems),
            "warning_items": [*result["warning_items"], *problems]}


async def _post_apply_problems(session: AsyncSession, ctx: WriteCtx, ami: Any) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for kind, apply_fn in _POST_APPLY:
        if not ctx.created.get(kind):
            continue
        try:
            await apply_fn(session, tenant_id=ctx.tenant_id, tenant_code=ctx.tenant_code, ami=ami)
        except Exception as exc:  # noqa: BLE001 — import allaqachon commit qilingan; ogohlantirish
            problems.append({"code": f"{kind}_apply_failed", "message": type(exc).__name__, "source_ref": None})
    if ctx.created.get("trunk") and not await _safe_reload(ami):
        problems.append({"code": "pjsip_reload_failed", "message": "pjsip reload", "source_ref": None})
    return problems


async def _safe_reload(ami: Any) -> bool:
    try:
        return bool(await reload_pjsip(ami))
    except Exception:  # noqa: BLE001
        return False


def _unlink(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


async def _mark_failed(session: AsyncSession, job_id: str, error: dict[str, str]) -> None:
    job = await session.get(MigrationJob, job_id)
    if job is None:
        return
    job.status, job.step, job.error = "failed", None, error
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()
