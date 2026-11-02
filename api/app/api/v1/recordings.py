"""M3b §1 — `GET /recordings/{id}/audio` (admin — hammasi, operator — o'z qo'ng'iroqlari; `Range`),
`DELETE /recordings/{id}` (admin, audit). Fayl — `recordings` volume (`settings.recordings_dir`)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_access
from app.api.v1.calls import _own_extension_number, _require_calls_permission
from app.core.errors import ApiError
from app.db.models import CallRecording, User
from app.services import recordings
from app.services.audit import record_audit

router = APIRouter(prefix="/recordings", tags=["recordings"])


def not_found() -> ApiError:
    return ApiError(404, "not_found", "Yozuv topilmadi")


def audio_response(rec: CallRecording) -> FileResponse:
    """Starlette `FileResponse` — `Range` (206) o'zi qo'llab-quvvatlaydi."""
    path = recordings.absolute_path(rec.path)
    if not path.is_file():
        raise ApiError(404, "file_missing", "Yozuv fayli diskda topilmadi")
    return FileResponse(path, media_type="audio/wav", filename=recordings.file_name(rec))


@router.get("/{recording_id}/audio")
async def recording_audio(recording_id: str, session: AsyncSession = Depends(get_session),
                          user: User = Depends(get_current_user)) -> FileResponse:
    is_admin = _require_calls_permission(user)
    rec = await recordings.get_active(session, str(user.tenant_id), recording_id)
    if rec is None:
        raise not_found()
    if not is_admin:
        number = await _own_extension_number(session, user)
        if not await recordings.operator_can_access(session, rec, code=user.tenant.code, number=number):
            raise ApiError(403, "forbidden", "Bu yozuvga ruxsat yo'q")
    return audio_response(rec)


@router.delete("/{recording_id}", status_code=204, response_model=None)
async def delete_recording(recording_id: str, session: AsyncSession = Depends(get_session),
                           user: User = Depends(require_access)) -> Response:
    rec = await recordings.get_active(session, str(user.tenant_id), recording_id)
    if rec is None:
        raise not_found()
    try:
        await asyncio.to_thread(recordings.unlink_file, recordings.absolute_path(rec.path))
    except OSError as exc:
        raise ApiError(500, "recording_delete_failed", f"Faylni o'chirib bo'lmadi: {exc.strerror or exc}") from exc
    rec.deleted_at = datetime.now(timezone.utc)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="recording.delete",
                       entity="recording", entity_id=str(rec.id),
                       diff={"linkedid": rec.linkedid, "path": rec.path, "duration_s": rec.duration_s})
    await session.commit()
    return Response(status_code=204)
