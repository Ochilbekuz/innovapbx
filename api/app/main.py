"""FastAPI ilova kirish nuqtasi — Innova PBX M0 backend."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.internal import router as internal_router
from app.api.internal_callback import router as internal_callback_router
from app.api.internal_campaigns import router as internal_campaigns_router
from app.api.internal_cidlookup import router as internal_cidlookup_router
from app.api.internal_conference import router as internal_conference_router
from app.api.internal_day_night import router as internal_day_night_router
from app.api.internal_disa import router as internal_disa_router
from app.api.internal_pinset import router as internal_pinset_router
from app.api.internal_softphone import router as internal_softphone_router
from app.api.internal_toll import router as internal_toll_router
from app.api.internal_voicemail import router as internal_voicemail_router
from app.api.prov import router as prov_router
from app.api.public import router as public_router
from app.api.public_crm import router as public_crm_router
from app.api.public_events_ws import router as public_events_ws_router
from app.api.public_widget import router as public_widget_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.services.maintenance import maintenance_middleware

log = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fon vazifalari: ovozli pochta bildirishnomalari (m1c-contract.md §2,
    `app/services/vm_notify.py`), ogohlantirish navbati (m2c-contract.md §4,
    `app/services/alerts.py`), SIP hujum himoyasi (§2, `app/services/sip_guard.py`)
    va trunk monitoringi (§5, `app/services/trunk_monitor.py`). Har biri mustaqil
    `*_ENABLED` bayroq bilan o'chiriladi, biri yiqilsa ikkinchisiga ta'sir qilmaydi."""
    if settings.stale_job_recovery_enabled:
        await _recover_stale_jobs()
    if settings.startup_dialplan_regen_enabled:
        await _regenerate_dialplan_on_startup()
    _ensure_web_certificate()
    tasks: list[asyncio.Task] = []
    if settings.vm_notify_enabled:
        from app.db.session import SessionLocal
        from app.services.vm_notify import run_forever as vm_notify_run_forever
        tasks.append(asyncio.create_task(vm_notify_run_forever(SessionLocal, settings.vm_notify_interval_s)))
    if settings.alert_dispatch_enabled:
        from app.db.session import SessionLocal
        from app.services.alerts import run_forever as alert_dispatch_run_forever
        tasks.append(asyncio.create_task(
            alert_dispatch_run_forever(SessionLocal, settings.alert_dispatch_interval_s)))
    if settings.sip_guard_task_enabled:
        from app.api.deps import get_ami
        from app.db.session import SessionLocal
        from app.services.sip_guard import run_forever as sip_guard_run_forever
        tasks.append(asyncio.create_task(
            sip_guard_run_forever(SessionLocal, get_ami(), settings.sip_guard_interval_s)))
    if settings.trunk_monitor_enabled:
        from app.api.deps import get_ami
        from app.db.session import SessionLocal
        from app.services.trunk_monitor import run_forever as trunk_monitor_run_forever
        tasks.append(asyncio.create_task(
            trunk_monitor_run_forever(SessionLocal, get_ami(), settings.trunk_monitor_interval_s)))
    if settings.backup_scheduler_enabled:
        from app.db.session import SessionLocal
        from app.db.session import engine as db_engine
        from app.services.backup_scheduler import run_forever as backup_scheduler_run_forever
        tasks.append(asyncio.create_task(
            backup_scheduler_run_forever(SessionLocal, db_engine, settings.backup_scheduler_interval_s)))
    tasks += [asyncio.create_task(job) for job in _m3b_jobs()]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _recover_stale_jobs() -> None:
    from app.db.session import SessionLocal
    from app.db.session import engine as db_engine
    from app.services.stale_jobs import recover_stale_jobs

    try:
        await recover_stale_jobs(SessionLocal, db_engine)
    except Exception:  # noqa: BLE001 — baza hali tayyor bo'lmasa ham API ko'tarilsin
        log.exception("qotib qolgan ishlarni tiklab bo'lmadi")


def _ensure_web_certificate() -> None:
    """1.0.4: nginx 443 uchun o'z-imzoli sertifikat — bo'lmasa BIR MARTA
    yaratiladi (disk, DB kerak emas); diskka yoza olmasa API baribir ko'tarilsin
    (HTTP ishlashda davom etadi, faqat HTTPS/mikrofon ogohlantirishi qolaveradi)."""
    from app.services.web_tls_cert import ensure_web_certificate

    try:
        ensure_web_certificate()
    except OSError:
        log.exception("veb HTTPS sertifikati yaratilmadi")


async def _regenerate_dialplan_on_startup() -> None:
    """m-sip-login-plain-number §5: migratsiyadan keyin eski dialplan fayli
    eskirgan bo'lishi mumkin — har ishga tushishda qayta qo'llash (arzon,
    `apply_config` o'zi idempotent — hash bir xil bo'lsa yozmaydi)."""
    from app.api.deps import get_ami
    from app.db.session import SessionLocal
    from app.services.startup_regen import regenerate_dialplan_on_startup

    try:
        await regenerate_dialplan_on_startup(SessionLocal, get_ami())
    except Exception:  # noqa: BLE001 — baza hali tayyor bo'lmasa ham API ko'tarilsin
        log.exception("ishga tushishda dialplan qayta qo'llanmadi")


def _m3b_jobs() -> list:
    """M3b: `call_events` (AMI hodisalari + CDR supurgich), `integration_dispatch` (outbox), `recording_purge`."""
    from app.api.deps import get_ami
    from app.db.session import SessionLocal

    jobs = []
    if settings.call_events_enabled:
        from app.services.call_events import run_forever as call_events_run_forever
        jobs.append(call_events_run_forever(SessionLocal, get_ami(), settings.call_events_sweep_interval_s))
    if settings.integration_dispatch_enabled:
        from app.services.integrations.dispatch import run_forever as dispatch_run_forever
        jobs.append(dispatch_run_forever(SessionLocal, settings.integration_dispatch_interval_s))
    if settings.recording_purge_enabled:
        from app.services.recordings import run_forever as purge_run_forever
        jobs.append(purge_run_forever(SessionLocal, settings.recording_purge_interval_s))
    if settings.provision_purge_enabled:  # M4a §1: provision_requests 30 kun
        from app.api.prov import purge_requests_forever
        jobs.append(purge_requests_forever(SessionLocal, settings.provision_purge_interval_s))
    if settings.campaign_dialer_enabled:  # M6 §3: kampaniya avtoterish
        from app.services.campaign_dialer import run_forever as campaign_dialer_run_forever
        jobs.append(campaign_dialer_run_forever(SessionLocal, get_ami(), settings.campaign_dialer_interval_s))
    if settings.events_ws_broadcast_enabled:  # M10 B3: tashqi WS hodisalar tarqatuvchisi
        from app.services.events_ws_broadcast import run_forever as events_ws_run_forever
        jobs.append(events_ws_run_forever(SessionLocal, settings.events_ws_broadcast_interval_s))
    if settings.callback_dialer_enabled:  # M10 A1: qayta chaqirish vidjeti avtoterish
        from app.services.callback_dialer import run_forever as callback_dialer_run_forever
        jobs.append(callback_dialer_run_forever(SessionLocal, get_ami(), settings.callback_dialer_interval_s))
    if settings.missed_notify_enabled:  # M10 A2: o'tkazib yuborilgan qo'ng'iroq bildirishnomasi
        from app.services.missed_call_notify import run_forever as missed_notify_run_forever
        jobs.append(missed_notify_run_forever(SessionLocal, settings.missed_notify_interval_s))
    return jobs


app = FastAPI(title="Innova PBX API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.middleware("http")(maintenance_middleware)
app.include_router(v1_router)
app.include_router(internal_router)
app.include_router(internal_conference_router)
app.include_router(internal_voicemail_router)
app.include_router(internal_toll_router)
app.include_router(internal_softphone_router)
app.include_router(internal_campaigns_router)
app.include_router(internal_pinset_router)
app.include_router(internal_cidlookup_router)
app.include_router(internal_callback_router)
app.include_router(internal_day_night_router)  # M12 A1
app.include_router(internal_disa_router)  # M12 A2
app.include_router(public_router)
app.include_router(public_crm_router)
app.include_router(public_events_ws_router)
app.include_router(public_widget_router)
app.include_router(prov_router)


@app.get("/healthz", tags=["system"])
async def healthz() -> dict:
    """Konteyner darajasidagi oddiy tayyorlik tekshiruvi (bazasiz)."""
    return {"ok": True}
