"""Boshqa ilovalar (M9 A2, m9-freepbx-gaps-contract.md) — ichki raqamlar `code`ni
terib mavjud manzilga (`target_id`) yetadi. `code` — feature kodlari VA boshqa
`misc_applications`/ichki raqam-manzil raqamlari bilan to'qnashmasin (409 `code_taken`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import FeatureCode, MiscApplication, User
from app.schemas import (
    CreateMiscApplicationPayload,
    MiscApplicationMutated,
    MiscApplicationOut,
    Paged,
    UpdateMiscApplicationPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.feature_codes import prefix_clash
from app.services.numbers import number_taken
from app.services.target_resolution import resolve_target

router = APIRouter(prefix="/misc-applications", tags=["misc-applications"])


async def _validate_code(session: AsyncSession, tenant_id: str, code: str, exclude_id: str | None = None) -> None:
    """Prefiks-to'qnashuv — boshqa `misc_applications` VA yoqilgan feature
    kodlari bilan (ikkalasi ham literal `exten`, pattern emas). Oddiy raqamli
    kod uchun qo'shimcha: ichki raqam/manzil raqami bilan ANIQ to'qnashuv."""
    siblings_stmt = select(MiscApplication.code).where(MiscApplication.tenant_id == tenant_id)
    if exclude_id:
        siblings_stmt = siblings_stmt.where(MiscApplication.id != exclude_id)
    siblings = (await session.execute(siblings_stmt)).scalars().all()
    feature_codes = (await session.execute(
        select(FeatureCode.code).where(FeatureCode.tenant_id == tenant_id, FeatureCode.enabled)
    )).scalars().all()
    clash = next((o for o in (*siblings, *feature_codes) if prefix_clash(code, o)), None)
    if clash is not None:
        raise ApiError(409, "code_taken", "Bu kod boshqa funksiya bilan to'qnashadi", field="code",
                       details={"conflict": clash})
    if code[0] not in ("*", "#") and await number_taken(session, tenant_id, code):
        raise ApiError(409, "code_taken", "Bu kod ichki raqam/manzil bilan to'qnashadi", field="code")


def _out(m: MiscApplication, target) -> MiscApplicationOut:
    return MiscApplicationOut(id=str(m.id), name=m.name, code=m.code, target=target, enabled=m.enabled,
                               updated_at=m.updated_at)


async def _app_out(session: AsyncSession, tenant_id: str, m: MiscApplication) -> MiscApplicationOut:
    target = await resolve_target(session, tenant_id, str(m.target_id))
    return _out(m, target)


async def _get_or_404(session: AsyncSession, tenant_id: str, item_id: str) -> MiscApplication:
    valid_id = parse_uuid(item_id, not_found_message="Ilova topilmadi")
    item = (await session.execute(
        select(MiscApplication).where(MiscApplication.tenant_id == tenant_id, MiscApplication.id == valid_id)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", "Ilova topilmadi")
    return item


@router.get("", response_model=Paged)
async def list_misc_applications(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    tenant_id = str(user.tenant_id)
    stmt = select(MiscApplication).where(MiscApplication.tenant_id == tenant_id)
    count_stmt = select(func.count()).select_from(MiscApplication).where(MiscApplication.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(MiscApplication.name.ilike(like))
        count_stmt = count_stmt.where(MiscApplication.name.ilike(like))
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(MiscApplication.name).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return Paged(items=[await _app_out(session, tenant_id, m) for m in items], total=total)


@router.get("/{item_id}", response_model=MiscApplicationOut)
async def get_misc_application(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> MiscApplicationOut:
    item = await _get_or_404(session, str(user.tenant_id), item_id)
    return await _app_out(session, str(user.tenant_id), item)


@router.post("", response_model=MiscApplicationMutated, status_code=201)
async def create_misc_application(
    payload: CreateMiscApplicationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> MiscApplicationMutated:
    tenant_id = str(user.tenant_id)
    if await resolve_target(session, tenant_id, payload.target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="target_id")
    await _validate_code(session, tenant_id, payload.code)

    item = MiscApplication(tenant_id=tenant_id, name=payload.name, code=payload.code,
                            target_id=payload.target_id, enabled=payload.enabled)
    session.add(item)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_application.create",
                        entity="misc_application", entity_id=str(item.id), diff={"name": payload.name,
                                                                                  "code": payload.code})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return MiscApplicationMutated(item=await _app_out(session, tenant_id, item), apply=apply_result.to_dict())


@router.patch("/{item_id}", response_model=MiscApplicationMutated)
async def update_misc_application(
    item_id: str, payload: UpdateMiscApplicationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> MiscApplicationMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    check_not_stale(item.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        item.name = payload.name
        diff["name"] = payload.name
    if payload.target_id is not None:
        if await resolve_target(session, tenant_id, payload.target_id) is None:
            raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="target_id")
        item.target_id = payload.target_id
        diff["target_id"] = payload.target_id
    if payload.code is not None:
        await _validate_code(session, tenant_id, payload.code, exclude_id=str(item.id))
        item.code = payload.code
        diff["code"] = payload.code
    if payload.enabled is not None:
        item.enabled = payload.enabled
        diff["enabled"] = payload.enabled

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_application.update",
                        entity="misc_application", entity_id=str(item.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return MiscApplicationMutated(item=await _app_out(session, tenant_id, item), apply=apply_result.to_dict())


@router.delete("/{item_id}", status_code=204, response_model=None)
async def delete_misc_application(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    await session.delete(item)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_application.delete",
                        entity="misc_application", entity_id=str(item_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
