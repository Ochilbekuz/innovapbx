"""E'lonlar (M9 A1, m9-freepbx-gaps-contract.md) — xabar o'ynab, keyin boshqa
manzilga o'tkazadi. Dialplan mantiqi: `app/services/dialplan_features.py`
(`announcement_lines`), `_announcement_dest_lines` — `compiler.py`."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import Announcement, AudioFile, User
from app.schemas import (
    AnnouncementMutated,
    AnnouncementOut,
    AudioOut,
    CreateAnnouncementPayload,
    Paged,
    UpdateAnnouncementPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _audio_out(audio: AudioFile) -> AudioOut:
    return AudioOut(id=str(audio.id), name=audio.name, duration_ms=audio.duration_ms,
                     format="wav", created_at=audio.created_at)


async def _get_audio_or_422(session: AsyncSession, tenant_id: str, audio_id: str, field: str) -> AudioFile:
    audio = (await session.execute(
        select(AudioFile).where(AudioFile.tenant_id == tenant_id, AudioFile.id == audio_id)
    )).scalar_one_or_none()
    if audio is None:
        raise ApiError(422, "invalid_audio", "Noto'g'ri audio", field=field)
    return audio


async def _ann_out(session: AsyncSession, tenant_id: str, ann: Announcement) -> AnnouncementOut:
    audio = await session.get(AudioFile, ann.audio_file_id)
    next_target = await resolve_target(session, tenant_id, str(ann.next_target_id))
    return AnnouncementOut(
        id=str(ann.id), name=ann.name, audio=_audio_out(audio), allow_skip=ann.allow_skip,
        repeat_key=ann.repeat_key, answer=ann.answer, next_target=next_target, updated_at=ann.updated_at,
    )


async def _get_or_404(session: AsyncSession, tenant_id: str, ann_id: str) -> Announcement:
    valid_id = parse_uuid(ann_id, not_found_message="E'lon topilmadi")
    ann = (await session.execute(
        select(Announcement).where(Announcement.tenant_id == tenant_id, Announcement.id == valid_id)
    )).scalar_one_or_none()
    if ann is None:
        raise ApiError(404, "not_found", "E'lon topilmadi")
    return ann


@router.get("", response_model=Paged)
async def list_announcements(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    tenant_id = str(user.tenant_id)
    stmt = select(Announcement).where(Announcement.tenant_id == tenant_id)
    count_stmt = select(func.count()).select_from(Announcement).where(Announcement.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Announcement.name.ilike(like))
        count_stmt = count_stmt.where(Announcement.name.ilike(like))
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Announcement.name).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return Paged(items=[await _ann_out(session, tenant_id, a) for a in items], total=total)


@router.get("/{ann_id}", response_model=AnnouncementOut)
async def get_announcement(
    ann_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> AnnouncementOut:
    tenant_id = str(user.tenant_id)
    ann = await _get_or_404(session, tenant_id, ann_id)
    return await _ann_out(session, tenant_id, ann)


async def _validate_next_target(session: AsyncSession, tenant_id: str, target_id: str) -> None:
    if await resolve_target(session, tenant_id, target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="next_target_id")


@router.post("", response_model=AnnouncementMutated, status_code=201)
async def create_announcement(
    payload: CreateAnnouncementPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> AnnouncementMutated:
    tenant_id = str(user.tenant_id)
    await _get_audio_or_422(session, tenant_id, payload.audio_file_id, "audio_file_id")
    await _validate_next_target(session, tenant_id, payload.next_target_id)

    target = await create_target(session, tenant_id, "announcement", payload.name)
    ann = Announcement(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, audio_file_id=payload.audio_file_id,
        next_target_id=payload.next_target_id, allow_skip=payload.allow_skip,
        repeat_key=payload.repeat_key, answer=payload.answer,
    )
    session.add(ann)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="announcement.create",
                        entity="announcement", entity_id=str(ann.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return AnnouncementMutated(item=await _ann_out(session, tenant_id, ann), apply=apply_result.to_dict())


@router.patch("/{ann_id}", response_model=AnnouncementMutated)
async def update_announcement(
    ann_id: str, payload: UpdateAnnouncementPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> AnnouncementMutated:
    tenant_id = str(user.tenant_id)
    ann = await _get_or_404(session, tenant_id, ann_id)
    check_not_stale(ann.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        ann.name = payload.name
        await rename_target(session, str(ann.target_id), payload.name)
        diff["name"] = payload.name
    if payload.audio_file_id is not None:
        await _get_audio_or_422(session, tenant_id, payload.audio_file_id, "audio_file_id")
        ann.audio_file_id = payload.audio_file_id
        diff["audio_file_id"] = payload.audio_file_id
    if payload.next_target_id is not None:
        await _validate_next_target(session, tenant_id, payload.next_target_id)
        ann.next_target_id = payload.next_target_id
        diff["next_target_id"] = payload.next_target_id
    for field in ("allow_skip", "repeat_key", "answer"):
        if field in payload.model_fields_set:
            setattr(ann, field, getattr(payload, field))
            diff[field] = getattr(payload, field)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="announcement.update",
                        entity="announcement", entity_id=str(ann.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return AnnouncementMutated(item=await _ann_out(session, tenant_id, ann), apply=apply_result.to_dict())


@router.delete("/{ann_id}", status_code=204, response_model=None)
async def delete_announcement(
    ann_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    ann = await _get_or_404(session, tenant_id, ann_id)
    usages = await usages_for_target(session, tenant_id, str(ann.target_id))
    if usages:
        raise ApiError(409, "in_use", "E'lon ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, ann, str(ann.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="announcement.delete",
                        entity="announcement", entity_id=str(ann_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
