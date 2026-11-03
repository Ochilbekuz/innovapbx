"""M5a — `POST /migration/freepbx/ssh/test`, `POST /migration/freepbx/ssh/fetch`
(m5a-contract.md §3, `/tmp/backend-ssh.txt`). `app/api/v1/migration.py`ga ATAYLAB
TEGILMAGAN (parallel ish — `apply`/`report`) — shu sabab bu yerda `JobOut` qurilishi
(`_job_out`) KICHIK TAKRORI bor (o'sha fayldagi xususiy funksiyani import qilish
mo'rt bo'lardi). `router.py`ga bu modulni ALOHIDA muhandis ulaydi."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.db.models import MigrationJob, SystemSettings, User
from app.db.session import SessionLocal
from app.schemas_migration import JobErrorOut, JobItem, JobOut, OptionsOut, SourceMetaOut
from app.services.audit import record_audit
from app.services.fpbx.ssh_fetch import SshCredentials, run_ssh_fetch_job, test_connection

router = APIRouter(prefix="/migration/freepbx/ssh", tags=["migration"])


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SshAuthPayload(_Strict):
    """`password` YOKI `private_key`dan FAQAT bittasi — ikkisi ham, ikkisi ham yo'q
    bo'lsa 422 (m5a-contract.md §3)."""

    host: str
    port: int = Field(22, ge=1, le=65535)
    username: str
    password: str | None = None
    private_key: str | None = None

    @model_validator(mode="after")
    def _exactly_one_secret(self) -> "SshAuthPayload":
        if bool(self.password) == bool(self.private_key):
            raise ValueError("password YOKI private_key — ikkisidan FAQAT bittasi")
        return self

    def to_credentials(self) -> SshCredentials:
        return SshCredentials(host=self.host, port=self.port, username=self.username,
                               password=self.password, private_key=self.private_key)


class SshFetchPayload(SshAuthPayload):
    host_key_fp: str


class SshTestResult(BaseModel):
    ok: bool
    host_key_fp: str | None = None
    error: str | None = None


async def _backup_ready(session: AsyncSession, tenant_id: str) -> bool:
    """`app/api/v1/migration.py::_backup_ready` BILAN BIR XIL mantiq (shu faylga
    tegilmagani uchun qayta yozilgan — bir xil manba: `SystemSettings.backup`)."""
    row = await session.get(SystemSettings, tenant_id)
    cfg = (row.backup if row else None) or {}
    return bool(cfg.get("passphrase_enc"))


async def _job_out(session: AsyncSession, job: MigrationJob) -> JobOut:
    """`app/api/v1/migration.py::_job_out` bilan BIR XIL shakl — yangi ish uchun
    `plan`/`result` doim `None`, shu sabab `summary`/`result` soddalashtirilgan."""
    return JobOut(
        id=str(job.id), source=job.source, status=job.status, step=job.step, progress=job.progress,
        source_meta=SourceMetaOut(**job.source_meta) if job.source_meta else None, summary=None,
        options=OptionsOut(**(job.options or {})), result=None,
        error=JobErrorOut(**job.error) if job.error else None,
        pre_import_backup_id=None, backup_ready=await _backup_ready(session, str(job.tenant_id)),
        created_by=str(job.created_by) if job.created_by else None,
        created_at=job.created_at, finished_at=job.finished_at,
    )


@router.post("/test", response_model=SshTestResult)
async def ssh_test(payload: SshAuthPayload, user: User = Depends(require_access)) -> SshTestResult:
    ok, host_key_fp, error = await test_connection(payload.to_credentials())
    return SshTestResult(ok=ok, host_key_fp=host_key_fp, error=error)


@router.post("/fetch", status_code=202, response_model=JobItem)
async def ssh_fetch(
    payload: SshFetchPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> JobItem:
    """Tezkor (sinxron) ulanish+parol+host-kalit tekshiruvi — xato bo'lsa ish
    YARATILMAYDI (422). Muvaffaqiyatda ish darhol `fetching`/`step=ssh_fetch` bilan
    yaratiladi, 202 qaytariladi, haqiqiy eksport+olish fon vazifasida davom etadi.

    `payload.host_key_fp` ENDI `test_connection`ga uzatiladi — host kaliti
    AUTENTIFIKATSIYADAN OLDIN tekshiriladi (avvalgi xato: avval to'liq ulanib
    (parol/kalit yuborilib) KEYIN `observed_fp != payload.host_key_fp`
    solishtirilardi — MITM parolni allaqachon olib bo'lgan bo'lardi)."""
    ok, _observed_fp, error = await test_connection(payload.to_credentials(), payload.host_key_fp)
    if not ok:
        raise ApiError(422, error or "ssh_unreachable", "SSH ulanishi muvaffaqiyatsiz")

    tenant_id = str(user.tenant_id)
    job = MigrationJob(tenant_id=tenant_id, source="ssh", status="fetching", step="ssh_fetch", progress=0,
                        source_meta={"host": payload.host}, options={"rotate_weak_secrets": False},
                        created_by=user.id)
    session.add(job)
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="migration.ssh_fetch",
                        entity="migration", entity_id=job.id, diff={"op": "ssh_fetch", "host": payload.host})
    await session.commit()

    asyncio.create_task(
        run_ssh_fetch_job(SessionLocal, str(job.id), payload.to_credentials(), payload.host_key_fp)
    )
    return JobItem(item=await _job_out(session, job))
