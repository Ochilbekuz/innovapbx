"""Kutish musiqasi (MOH) sinflari — m1b-contract.md bo'lim 8. CRUD +
`queues.moh_class_id` orqali ishlatiladi (`asterisk_queues` view
`musicclass`ni shu sinf ID'sidan hisoblaydi — realtime, navbat uchun
qo'shimcha reload shart emas, `alembic/sql/0007_moh_musicclass.sql`).

Asterisk'ga yetkazish (`app/services/moh.py` `apply_moh()`): har sinf
papkasidagi (`sounds` umumiy hajm) audio havolalari yangilanadi,
`musiconhold_innova.conf` (`dialplan` umumiy hajm) qayta yoziladi, AMI
`moh reload` bilan kuchga kiritiladi va `moh show classes` orqali
tasdiqlanadi — HAR UCH yozuvchi endpoint'da (`apply_config()`dan alohida,
sabab shu funksiya docstringida)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_admin
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import AudioFile, MohClass, MohClassFile, Queue, User
from app.schemas import AudioOut, CreateMohClassPayload, MohClassMutated, MohClassOut, UpdateMohClassPayload
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.moh import apply_moh, remove_moh_class_dir

router = APIRouter(prefix="/moh-classes", tags=["moh-classes"])

_OPTIONS = (selectinload(MohClass.files).selectinload(MohClassFile.audio_file),)
_NAME_TAKEN = ApiError(409, "name_taken", "Shu nomli kutish musiqasi sinfi allaqachon mavjud", field="name")


def _moh_class_out(moh: MohClass) -> MohClassOut:
    files = [
        AudioOut(id=str(f.audio_file.id), name=f.audio_file.name, duration_ms=f.audio_file.duration_ms,
                  format="wav", created_at=f.audio_file.created_at)
        for f in moh.files
    ]
    return MohClassOut(id=str(moh.id), name=moh.name, shuffle=moh.shuffle, files=files, updated_at=moh.updated_at)


async def _resolve_files(session: AsyncSession, tenant_id: str, file_ids: list[str]) -> list[AudioFile]:
    """`file_ids` tartibini SAQLAYDI (MOH ijro tartibi) — mavjud bo'lmagan
    id bo'lsa 404 (`web/src/api/fake.ts` `resolveMohFiles` bilan BIR XIL)."""
    if not file_ids:
        return []
    found = {str(a.id): a for a in (await session.execute(
        select(AudioFile).where(AudioFile.tenant_id == tenant_id, AudioFile.id.in_(file_ids))
    )).scalars().all()}
    missing = [fid for fid in file_ids if fid not in found]
    if missing:
        raise ApiError(404, "not_found", "Audio fayl topilmadi", field="file_ids")
    return [found[fid] for fid in file_ids]


def _replace_files(moh: MohClass, audio_files: list[AudioFile]) -> None:
    moh.files = [MohClassFile(audio_file_id=a.id, position=i) for i, a in enumerate(audio_files)]


async def _get_moh_or_404(session: AsyncSession, tenant_id: str, moh_id: str) -> MohClass:
    return await get_tenant_scoped_or_404(
        session, MohClass, tenant_id, moh_id, not_found_message="Kutish musiqasi sinfi topilmadi", options=_OPTIONS,
    )


async def _apply_moh_or_502(session: AsyncSession, tenant_id: str, ami) -> None:
    """3 yozuvchi endpoint uchun bir xil "Asterisk'ga yetkaz, bo'lmasa 502"
    qolipi (dryer) — `moh.py` docstringida ko'rsatilgan sababga ko'ra
    `apply_config()`dan MUSTAQIL."""
    tenant_code = await get_tenant_code(session, tenant_id)
    try:
        await apply_moh(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    except Exception as exc:  # noqa: BLE001 — aniq xato xabari bilan 502 qaytariladi
        raise ApiError(502, "moh_sync_failed", f"MOH Asterisk'ga yetkazilmadi: {exc}"[:500]) from exc


async def _moh_class_usages(session: AsyncSession, tenant_id: str, moh_id: str) -> list[dict]:
    rows = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id, Queue.moh_class_id == moh_id)
    )).scalars().all()
    return [{"kind": "queue", "id": str(q.id), "label": q.name, "field": "moh_class_id"} for q in rows]


@router.get("")
async def list_moh_classes(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    items = (await session.execute(
        select(MohClass).where(MohClass.tenant_id == user.tenant_id).order_by(MohClass.name).options(*_OPTIONS)
    )).scalars().all()
    return {"items": [_moh_class_out(m) for m in items]}


@router.post("", response_model=MohClassMutated, status_code=201)
async def create_moh_class(
    payload: CreateMohClassPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> MohClassMutated:
    tenant_id = str(user.tenant_id)
    files = await _resolve_files(session, tenant_id, payload.file_ids)
    moh = MohClass(tenant_id=tenant_id, name=payload.name, shuffle=payload.shuffle)
    _replace_files(moh, files)
    session.add(moh)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="moh_class.create",
                        entity="moh_class", entity_id=str(moh.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await _apply_moh_or_502(session, tenant_id, ami)
    await session.commit()
    moh = await _get_moh_or_404(session, tenant_id, str(moh.id))
    return MohClassMutated(item=_moh_class_out(moh), apply=apply_result.to_dict())


def _apply_simple_moh_fields(moh: MohClass, payload: UpdateMohClassPayload, diff: dict) -> None:
    if payload.name is not None:
        moh.name = payload.name
        diff["name"] = payload.name
    if payload.shuffle is not None:
        moh.shuffle = payload.shuffle
        diff["shuffle"] = payload.shuffle


@router.patch("/{moh_id}", response_model=MohClassMutated)
async def update_moh_class(
    moh_id: str, payload: UpdateMohClassPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> MohClassMutated:
    tenant_id = str(user.tenant_id)
    moh = await _get_moh_or_404(session, tenant_id, moh_id)
    check_not_stale(moh.updated_at, payload.updated_at)

    diff: dict = {}
    _apply_simple_moh_fields(moh, payload, diff)
    if payload.file_ids is not None:
        files = await _resolve_files(session, tenant_id, payload.file_ids)
        _replace_files(moh, files)
        diff["file_ids"] = len(payload.file_ids)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="moh_class.update",
                        entity="moh_class", entity_id=str(moh.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await _apply_moh_or_502(session, tenant_id, ami)
    await session.commit()
    moh = await _get_moh_or_404(session, tenant_id, str(moh.id))
    return MohClassMutated(item=_moh_class_out(moh), apply=apply_result.to_dict())


@router.delete("/{moh_id}", status_code=204, response_model=None)
async def delete_moh_class(
    moh_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    moh = await _get_moh_or_404(session, tenant_id, moh_id)
    if moh.name == "default":
        raise ApiError(409, "in_use", "«default» sinfini o'chirib bo'lmaydi", details={
            "usages": [{"kind": "moh_class", "id": str(moh.id), "label": moh.name, "field": "name"}],
        })
    usages = await _moh_class_usages(session, tenant_id, str(moh.id))
    if usages:
        raise ApiError(409, "in_use", f"«{moh.name}» hali ishlatilmoqda", details={"usages": usages})

    tenant_code = await get_tenant_code(session, tenant_id)
    await session.delete(moh)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="moh_class.delete",
                        entity="moh_class", entity_id=str(moh_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await _apply_moh_or_502(session, tenant_id, ami)
    await session.commit()
    remove_moh_class_dir(tenant_code, moh_id)
