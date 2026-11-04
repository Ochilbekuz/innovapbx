"""`GET/POST /system/update*` — m11-update-contract.md bo'lim 4. Marshrut
xaritasida (`app/core/permissions.py`) ATAYLAB YO'Q — fail-closed, faqat `*`
ruxsatli foydalanuvchi (`require_access`) kiradi."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import User
from app.schemas_update import SystemUpdateLogOut, SystemUpdateOut, SystemUpdateStartIn
from app.services import system_update
from app.services.audit import record_audit

router = APIRouter(tags=["system-update"])

_BUSY_STATES = {"checking", "updating"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def _load(update_dir: Path) -> SystemUpdateOut:
    agent = system_update.agent_available(update_dir)
    if not agent:
        return system_update.build_update_out(
            agent=False, raw_status={}, request_text=None,
            configured_version=settings.innova_version, changelog=[],
        )
    raw_status = system_update.parse_status(_read_text(update_dir / system_update.STATUS_FILENAME))
    request_text = _read_text(system_update.request_path(update_dir)) or None
    current = raw_status.get("current") or settings.innova_version
    changelog_text = _read_text(update_dir / system_update.CHANGELOG_FILENAME)
    changelog = system_update.parse_changelog(changelog_text, current)
    return system_update.build_update_out(
        agent=True, raw_status=raw_status, request_text=request_text,
        configured_version=settings.innova_version, changelog=changelog,
    )


def _guard_can_request(update_dir: Path) -> None:
    """503 — agent yo'q/o'rnatilmagan; 409 — allaqachon band (so'rov kutilmoqda
    yoki agent hozir ishlamoqda)."""
    if not system_update.agent_available(update_dir):
        raise ApiError(503, "update_agent_missing", "Paneldan yangilash agenti o'rnatilmagan")
    if system_update.request_path(update_dir).exists():
        raise ApiError(409, "update_busy", "Boshqa so'rov hali kutilmoqda")
    raw_status = system_update.parse_status(_read_text(update_dir / system_update.STATUS_FILENAME))
    if raw_status.get("state") in _BUSY_STATES:
        raise ApiError(409, "update_busy", "Yangilash agenti hozir band")


def _write_request_or_409(update_dir: Path, word: str) -> None:
    try:
        system_update.write_request(update_dir, word)
    except FileExistsError as exc:
        raise ApiError(409, "update_busy", "Boshqa so'rov hali kutilmoqda") from exc


@router.get("/system/update", response_model=SystemUpdateOut)
async def get_system_update(user: User = Depends(require_access)) -> SystemUpdateOut:
    return _load(Path(settings.update_dir))


@router.post("/system/update/check", response_model=SystemUpdateOut, status_code=202)
async def start_system_update_check(user: User = Depends(require_access)) -> SystemUpdateOut:
    update_dir = Path(settings.update_dir)
    _guard_can_request(update_dir)
    _write_request_or_409(update_dir, "check")
    out = _load(update_dir)
    out.pending = "check"
    return out


@router.post("/system/update/start", response_model=SystemUpdateOut, status_code=202)
async def start_system_update(
    payload: SystemUpdateStartIn, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> SystemUpdateOut:
    update_dir = Path(settings.update_dir)
    _guard_can_request(update_dir)
    raw_status = system_update.parse_status(_read_text(update_dir / system_update.STATUS_FILENAME))
    if raw_status.get("available") != "1":
        raise ApiError(409, "update_not_available", "Yangi versiya mavjud emas")
    latest = raw_status.get("latest")
    if payload.version != latest:
        raise ApiError(409, "update_version_mismatch", "Sahifa eskirgan — qayta tekshiring")
    current = raw_status.get("current") or settings.innova_version
    _write_request_or_409(update_dir, "update")
    await record_audit(
        session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="system.update.start",
        entity="system_update", diff={"from": current, "to": payload.version},
    )
    await session.commit()
    out = _load(update_dir)
    out.pending = "update"
    return out


@router.get("/system/update/log", response_model=SystemUpdateLogOut)
async def get_system_update_log(
    offset: int = Query(0, ge=0), user: User = Depends(require_access),
) -> SystemUpdateLogOut:
    path = Path(settings.update_dir) / system_update.LOG_FILENAME
    new_offset, size, text = system_update.read_log_chunk(path, offset)
    return SystemUpdateLogOut(offset=new_offset, size=size, text=text)
