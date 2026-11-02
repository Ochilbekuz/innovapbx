"""M5a — `/migration/freepbx` (FreePBX'dan ko'chirish, 1-BOSQICH: tahlil/reja,
sof o'qish). `/tmp/backend-brief.txt`/`/tmp/backend-phase1.txt` bilan AYNAN mos.

Bu modul FAQAT tahlil qatlamini amalga oshiradi: yuklash -> `analyze` (fon vazifa,
M4b `backup_job.py` uslubida) -> reja/ignored/warnings o'qish/PATCH. `POST
/jobs/{id}/apply`, `POST /ssh/*`, `GET /jobs/{id}/report` — 2-BOSQICH (boshqa
muhandis qo'shadi) — ATAYLAB YOZILMAGAN, lekin quyidagi tuzilish ularga tayyor:
alohida `app/services/fpbx/apply_job.py`/`ssh_fetch.py` qo'shilib, shu routerga
yangi endpointlar qo'shiladi (schemas_migration.py'da ularning maydonlari —
`result`, `pre_import_backup_id` — ALLAQACHON bor, Job DTO'sida bo'sh turadi)."""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.config import settings
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.db.models import MigrationItem, MigrationJob, SystemSettings, User
from app.db.session import SessionLocal
from app.db.session import engine as db_engine
from app.schemas_migration import (
    ApplyPayload,
    ByKindSummaryOut,
    IgnoredItemOut,
    IgnoredList,
    JobErrorOut,
    JobItem,
    JobList,
    JobOut,
    OptionsOut,
    PatchPlanPayload,
    PlanItemList,
    PlanItemOut,
    ResultOut,
    SourceMetaOut,
    SummaryOut,
    WarningItemOut,
    WarningList,
)
from app.services.audit import record_audit
from app.services.fpbx import bundle as bundle_mod
from app.services.fpbx import plan as plan_mod
from app.services.fpbx.apply_job import run_apply_job
from app.services.fpbx.apply_plan import PATCHABLE, PlanStaleError, build_report_csv, resolve_final_actions
from app.services.fpbx.analyze_job import run_analyze_job
from app.services.job_lock import JobAlreadyRunningError, try_acquire_job_lock

router = APIRouter(prefix="/migration/freepbx", tags=["migration"])

UPLOAD_CHUNK_SIZE = 1 << 20  # backups.py bilan BIR XIL — butunini xotiraga yuklamaydi.
EXPORT_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "freepbx" / "innova-fpbx-export.sh"
)

# PATCH /jobs/{id}/plan — ruxsat etilgan (joriy_amal -> so'ralgan_amal) o'tishlar
# (brief §«Qilinadigan ish» 3-band): boshqasi 422 `action_not_allowed`.
_ALLOWED_PATCH_TRANSITIONS = PATCHABLE  # apply eskirish tekshiruvi bilan BIR manba
APPLY_CONFIRM = "KOCHIRISH"
_BACKGROUND: set[asyncio.Task] = set()


# ------------------------------------------------------------------ DTO quruvchilar
def _source_meta_out(meta: dict | None) -> SourceMetaOut | None:
    return SourceMetaOut(**meta) if meta else None


def _options_out(options: dict | None) -> OptionsOut:
    return OptionsOut(**(options or {}))


def _error_out(error: dict | None) -> JobErrorOut | None:
    return JobErrorOut(**error) if error else None


def _result_out(result: dict | None) -> ResultOut | None:
    return ResultOut(**result) if result else None


def _summary_out(plan: dict | None) -> SummaryOut | None:
    """`migration_jobs.plan` ustunida SAQLANMAYDI — har so'rovda `plan["items"]`dan
    hisoblanadi (m5a-contract.md §0: faqat ommaviy maydonlar saqlanadi)."""
    if plan is None:
        return None
    by_kind: dict[str, dict[str, int]] = {}
    weak_secrets = 0
    for item in plan.get("items", []):
        counts = by_kind.setdefault(item["kind"], {"create": 0, "skip": 0, "conflict": 0, "unsupported": 0})
        counts[item["action"] if item["action"] in counts else "unsupported"] += 1
        if item.get("weak_secret"):
            weak_secrets += 1
    return SummaryOut(
        by_kind={kind: ByKindSummaryOut(**counts) for kind, counts in by_kind.items()},
        warnings=len(plan.get("warnings", [])), ignored=len(plan.get("ignored", [])),
        weak_secrets=weak_secrets,
    )


async def _backup_ready(session: AsyncSession, tenant_id: str) -> bool:
    """`app/api/v1/settings_backup.py::_settings_out`dagi `has_passphrase` bilan
    BIR XIL mantiq — `pre_import` zaxira ham M4b passphrase bilan shifrlanadi."""
    row = await session.get(SystemSettings, tenant_id)
    cfg = (row.backup if row else None) or {}
    return bool(cfg.get("passphrase_enc"))


async def _job_out(session: AsyncSession, job: MigrationJob) -> JobOut:
    return JobOut(
        id=str(job.id), source=job.source, status=job.status, step=job.step, progress=job.progress,
        source_meta=_source_meta_out(job.source_meta), summary=_summary_out(job.plan),
        options=_options_out(job.options), result=_result_out(job.result), error=_error_out(job.error),
        pre_import_backup_id=str(job.pre_import_backup_id) if job.pre_import_backup_id else None,
        backup_ready=await _backup_ready(session, str(job.tenant_id)),
        created_by=str(job.created_by) if job.created_by else None,
        created_at=job.created_at, finished_at=job.finished_at,
    )


async def _job_item(session: AsyncSession, job: MigrationJob) -> JobItem:
    return JobItem(item=await _job_out(session, job))


def _require_plan(job: MigrationJob) -> dict:
    if job.plan is None:
        raise ApiError(409, "not_analyzed", "Ish hali tahlil qilinmagan")
    return job.plan


async def _get_job_or_404(session: AsyncSession, tenant_id: str, job_id: str) -> MigrationJob:
    return await get_tenant_scoped_or_404(session, MigrationJob, tenant_id, job_id, not_found_message="Ish topilmadi")


# ------------------------------------------------------------------ eksport skripti
@router.get("/export-script")
async def download_export_script(user: User = Depends(require_admin)) -> FileResponse:
    if not EXPORT_SCRIPT_PATH.is_file():
        raise ApiError(404, "not_found", "Eksport skripti topilmadi")
    return FileResponse(EXPORT_SCRIPT_PATH, media_type="text/x-shellscript",
                         filename="innova-fpbx-export.sh")


# ------------------------------------------------------------------ yuklash (streaming) + bog'liqlik tartibi
async def _stream_and_extract(file: UploadFile, work_dir: Path) -> tuple[Path, dict, int]:
    """To'liq fayl xotiraga yuklanmasdan diskka yoziladi; keyin xavfsiz ochiladi
    (`bundle.extract_bundle` — `../`/mutlaq yo'l/ramziy havola/hajm-bombasi
    himoyasi) — xato bo'lsa `BundleInvalidError` (router 422'ga aylantiradi)."""
    archive_path = work_dir / "bundle.tar.gz"
    max_bytes = settings.migration_upload_max_bytes
    size = 0
    with archive_path.open("wb") as out:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise bundle_mod.BundleInvalidError("to'plam hajmi chegaradan katta")
            out.write(chunk)
    archive_path.chmod(0o600)
    extracted_dir = work_dir / "extracted"
    bundle_mod.extract_bundle(archive_path, extracted_dir, max_total_bytes=max_bytes)
    bundle_root = bundle_mod.find_bundle_root(extracted_dir)
    meta = bundle_mod.read_meta(bundle_root)
    return bundle_root, meta, size


@router.post("/upload", status_code=201, response_model=JobItem)
async def upload_bundle(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobItem:
    tenant_id = str(user.tenant_id)
    migrations_dir = Path(settings.migrations_dir)
    migrations_dir.mkdir(parents=True, exist_ok=True)
    work_dir = migrations_dir / f"upload-{uuid.uuid4().hex}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        bundle_root, meta, size = await _stream_and_extract(file, work_dir)
    except bundle_mod.BundleInvalidError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise ApiError(422, "bundle_invalid", str(exc)[:500]) from exc

    source_meta = {
        "file_name": file.filename, "size_bytes": size, "host": meta.get("host"),
        "freepbx_version": meta.get("freepbx_version"), "asterisk_version": meta.get("asterisk_version"),
        "created_at": meta.get("created_at"),
    }
    job = MigrationJob(tenant_id=tenant_id, source="upload", status="uploaded", source_meta=source_meta,
                        options={"rotate_weak_secrets": False}, created_by=user.id)
    session.add(job)
    await session.flush()
    final_dir = migrations_dir / str(job.id)
    work_dir.rename(final_dir)
    job.bundle_path = str(final_dir / bundle_root.relative_to(work_dir))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="migration.upload",
                        entity="migration", entity_id=job.id,
                        diff={"op": "upload", "file_name": file.filename, "size_bytes": size})
    await session.commit()
    return await _job_item(session, job)


# ------------------------------------------------------------------ tahlil (fon vazifa)
@router.post("/jobs/{job_id}/analyze", status_code=202, response_model=JobItem)
async def analyze_job_endpoint(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> JobItem:
    tenant_id = str(user.tenant_id)
    job = await _get_job_or_404(session, tenant_id, job_id)
    if not job.bundle_path:
        raise ApiError(409, "bundle_missing", "To'plam topilmadi (avval yuklang)")
    try:
        lock = await try_acquire_job_lock(db_engine)
    except JobAlreadyRunningError as exc:
        raise ApiError(409, "job_running", "Boshqa zaxira/ko'chirish ishi ketayotgan edi") from exc
    job.status, job.step, job.progress = "analyzing", None, 0
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="migration.analyze",
                        entity="migration", entity_id=job.id, diff={"op": "analyze"})
    await session.commit()
    asyncio.create_task(run_analyze_job(SessionLocal, db_engine, lock, str(job.id), tenant_id))
    return await _job_item(session, job)


# ------------------------------------------------------------------ ro'yxat/bitta ish
@router.get("/jobs", response_model=JobList)
async def list_jobs(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> JobList:
    rows = (await session.execute(
        select(MigrationJob).where(MigrationJob.tenant_id == user.tenant_id)
        .order_by(MigrationJob.created_at.desc())
    )).scalars().all()
    return JobList(items=[await _job_out(session, row) for row in rows])


@router.get("/jobs/{job_id}", response_model=JobItem)
async def get_job(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> JobItem:
    job = await _get_job_or_404(session, str(user.tenant_id), job_id)
    return await _job_item(session, job)


# ------------------------------------------------------------------ reja/ignored/warnings (o'qish)
@router.get("/jobs/{job_id}/plan", response_model=PlanItemList)
async def get_job_plan(
    job_id: str, kind: str | None = None, action: str | None = None, q: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> PlanItemList:
    job = await _get_job_or_404(session, str(user.tenant_id), job_id)
    items = _require_plan(job)["items"]
    if kind:
        items = [i for i in items if i["kind"] == kind]
    if action:
        items = [i for i in items if i["action"] == action]
    if q:
        needle = q.lower()
        items = [i for i in items if needle in i["name"].lower() or needle in i["source_ref"].lower()
                 or needle in (i.get("number") or "").lower()]
    total = len(items)
    start = (page - 1) * page_size
    return PlanItemList(items=[PlanItemOut(**i) for i in items[start:start + page_size]], total=total)


@router.get("/jobs/{job_id}/ignored", response_model=IgnoredList)
async def get_job_ignored(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> IgnoredList:
    job = await _get_job_or_404(session, str(user.tenant_id), job_id)
    return IgnoredList(items=[IgnoredItemOut(**i) for i in _require_plan(job)["ignored"]])


@router.get("/jobs/{job_id}/warnings", response_model=WarningList)
async def get_job_warnings(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> WarningList:
    job = await _get_job_or_404(session, str(user.tenant_id), job_id)
    return WarningList(items=[WarningItemOut(**w) for w in _require_plan(job)["warnings"]])


# ------------------------------------------------------------------ reja ustida qo'lda tanlov (PATCH)
def _validate_patch_action(item: dict, new_action: str) -> None:
    current = item["action"]
    if (current, new_action) not in _ALLOWED_PATCH_TRANSITIONS:
        raise ApiError(422, "action_not_allowed", f"{current} -> {new_action} ruxsat etilmagan", field="action")
    if new_action == "replace" and not item["replaceable"]:
        raise ApiError(422, "action_not_allowed", "Qo'lda yaratilgan obyekt almashtirilmaydi", field="action")


@router.patch("/jobs/{job_id}/plan", response_model=JobItem)
async def patch_job_plan(
    job_id: str, payload: PatchPlanPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobItem:
    tenant_id = str(user.tenant_id)
    job = await _get_job_or_404(session, tenant_id, job_id)
    plan = _require_plan(job)
    by_ref = {(i["kind"], i["source_ref"]): i for i in plan["items"]}

    updates: dict[tuple[str, str], str] = {}
    changes: list[dict] = []
    for change in payload.items:
        key = (change.kind, change.source_ref)
        item = by_ref.get(key)
        if item is None:
            raise ApiError(404, "not_found", f"Reja elementi topilmadi: {change.source_ref}", field="source_ref")
        _validate_patch_action(item, change.action)
        updates[key] = change.action
        changes.append({"kind": change.kind, "source_ref": change.source_ref,
                         "from": item["action"], "to": change.action})

    # JSONB ustuniga YANGI obyekt tayinlanadi (`settings_backup.py::update_backup_settings`
    # bilan BIR XIL qolip) — joy-ustida mutatsiya SQLAlchemy'ga "o'zgardi" deb ko'rinmasligi mumkin.
    new_items = []
    for item in plan["items"]:
        new_action = updates.get((item["kind"], item["source_ref"]))
        if new_action is None:
            new_items.append(item)
            continue
        new_item = {**item, "action": new_action}
        if new_action == "create":
            new_item["reason"] = None
        new_items.append(new_item)
    job.plan = {**plan, "items": new_items}

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="migration.update_plan",
                        entity="migration", entity_id=job.id, diff={"op": "patch_plan", "changes": changes})
    await session.commit()
    return await _job_item(session, job)


# ------------------------------------------------------------------ apply / hisobot
async def _acquire_lock():
    try:
        return await try_acquire_job_lock(db_engine)
    except JobAlreadyRunningError as exc:
        raise ApiError(409, "job_running", "Boshqa zaxira/ko'chirish ishi ketayotgan edi") from exc


async def _ensure_plan_fresh(session: AsyncSession, job: MigrationJob, tenant_id: str) -> None:
    """Saqlangan reja (PATCH tanlovlari bilan) hozirgi Innova holatiga mosmi — aks holda 409."""
    if not job.bundle_path:
        raise ApiError(409, "bundle_missing", "To'plam topilmadi (avval yuklang)")
    analysis = await plan_mod.analyze(Path(job.bundle_path), session, tenant_id)
    try:
        resolve_final_actions(job.plan["items"], analysis.items)
    except PlanStaleError as exc:
        raise ApiError(409, "plan_stale", str(exc)) from exc


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND.add(task)  # GC fon vazifasini yo'qotmasin
    task.add_done_callback(_BACKGROUND.discard)


@router.post("/jobs/{job_id}/apply", status_code=202, response_model=JobItem)
async def apply_job_endpoint(
    job_id: str, payload: ApplyPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> JobItem:
    if payload.confirm != APPLY_CONFIRM:
        raise ApiError(422, "confirm_required", f'Tasdiqlash uchun confirm="{APPLY_CONFIRM}" yuboring', field="confirm")
    tenant_id = str(user.tenant_id)
    job = await _get_job_or_404(session, tenant_id, job_id)
    if job.status != "analyzed" or job.plan is None:
        raise ApiError(409, "job_not_analyzed", "Ish tahlil qilingan holatda emas")
    if not await _backup_ready(session, tenant_id):
        raise ApiError(409, "passphrase_required", "Avval zaxira parolini o'rnating (pre_import zaxira uchun)")
    lock = await _acquire_lock()
    try:
        await _ensure_plan_fresh(session, job, tenant_id)
    except BaseException:
        await lock.release()
        raise
    job.status, job.step, job.progress, job.error, job.result = "applying", None, 0, None, None
    job.options = {"rotate_weak_secrets": payload.options.rotate_weak_secrets}
    await session.commit()
    _spawn(run_apply_job(SessionLocal, lock, str(job.id), tenant_id, ami=ami, user_id=str(user.id)))
    return await _job_item(session, job)


@router.get("/jobs/{job_id}/report", response_class=PlainTextResponse)
async def get_job_report(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> PlainTextResponse:
    """CSV: kind,source_ref,name,number,action,reason,result,innova_id — sirsiz."""
    job = await _get_job_or_404(session, str(user.tenant_id), job_id)
    plan = _require_plan(job)
    rows = (await session.execute(
        select(MigrationItem.kind, MigrationItem.source_ref, MigrationItem.innova_id)
        .where(MigrationItem.job_id == job.id)
    )).all()
    created = {f"{kind}:{ref}": (str(innova_id) if innova_id else None) for kind, ref, innova_id in rows}
    body = build_report_csv(plan["items"], created=created, result=job.result, applied=job.status == "ok")
    return PlainTextResponse(body, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="migration-{job.id}.csv"'})


# ------------------------------------------------------------------ o'chirish
@router.delete("/jobs/{job_id}", status_code=204, response_model=None)
async def delete_job(
    job_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> Response:
    tenant_id = str(user.tenant_id)
    job = await _get_job_or_404(session, tenant_id, job_id)
    if job.status in ("analyzing", "applying"):
        raise ApiError(409, "job_running", "Ish ketayotgan edi, avval tugashini kuting")
    shutil.rmtree(Path(settings.migrations_dir) / str(job.id), ignore_errors=True)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="migration.delete",
                        entity="migration", entity_id=job.id, diff={"op": "delete"})
    await session.delete(job)
    await session.commit()
    return Response(status_code=204)
