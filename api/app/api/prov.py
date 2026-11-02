"""M4a §0 — `GET /prov/{token}/{filename}` (autentifikatsiyasiz; `web` nginx `/prov/` ni shu yerga proksi qiladi).

Mijoz IP — `request.client.host` (uvicorn `FORWARDED_ALLOW_IPS` + nginx `X-Forwarded-For $remote_addr`).
Javob doim `Cache-Control: no-store`. Mantiq — `app/services/prov_serve.py`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.db.models import ProvisionRequest
from app.services.prov_serve import ProvRequest, serve
from app.services.integrations.crm import purge_old_links
from app.services.qr_provisioning import QR_FILENAME, purge_expired, serve_qr

router = APIRouter(prefix="/prov", tags=["provisioning"], include_in_schema=False)
log = logging.getLogger(__name__)
RETENTION_DAYS = 30
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _prov_request(token: str, filename: str, request: Request, **extra) -> ProvRequest:
    return ProvRequest(token=token, filename=filename, ip=request.client.host if request.client else None,
                       user_agent=request.headers.get("user-agent"),
                       host=request.headers.get("x-forwarded-host") or request.headers.get("host"), **extra)


def _response(result) -> Response:
    return Response(content=result.body, status_code=result.status, media_type=result.content_type,
                    headers=NO_STORE)


@router.get("/qr/{token}/" + QR_FILENAME)
async def provision_qr(token: str, request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    """M5b §2 — Linphone QR havolasi (bir martalik token; `allowed_networks` qo'llanmaydi)."""
    return _response(await serve_qr(session, _prov_request(token, QR_FILENAME, request, path_prefix="/prov/qr")))


@router.get("/{token}/{filename}")
async def provision(token: str, filename: str, request: Request,
                    session: AsyncSession = Depends(get_session)) -> Response:
    return _response(await serve(session, _prov_request(token, filename, request)))


# ------------------------------------------------------------------ jurnal tozalovchi (30 kun)
async def purge_requests_once(session_factory, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    async with session_factory() as session:
        result = await session.execute(delete(ProvisionRequest).where(ProvisionRequest.at < cutoff))
        await purge_expired(session)  # M5b: eskirgan QR tokenlar (xeshlar ham qolmasin)
        await purge_old_links(session, now)  # CRM qo'ng'iroq bog'lanishlari (30 kun)
        await session.commit()
        return result.rowcount or 0


async def purge_requests_forever(session_factory, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            removed = await purge_requests_once(session_factory)
            if removed:
                log.info("provision_requests: %d eski yozuv o'chirildi", removed)
        except Exception:  # noqa: BLE001 — fon vazifa yiqilmasin
            log.exception("provision_requests tozalovchi xatosi")
        await asyncio.sleep(interval_s)
