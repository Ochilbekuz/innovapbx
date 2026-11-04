"""M12 A2 — DISA (tashqaridan PIN bilan chiquvchi marshrutga kirish).
`app/services/compiler.py::_disa_dest_lines` — PIN tekshiruvi ichki CURL()
orqali, muvaffaqiyatli bo'lsa FAQAT `{code}-outbound-rg`ga Goto (ichki xizmat
kodlariga yo'l YO'Q).

PIN HECH QACHON ochiq qaytmaydi/saqlanmaydi — faqat `has_pin` (`has_pin`
qolipi boshqa CRUD'lar BILAN BIR XIL), HMAC-SHA256. Xavfsizlik: PIN bo'sh
FAQAT `allow_no_pin=true` bilan (m12-contract.md A2) — Pydantic (`schemas.py`)
VA DB CHECK (`0035_m12a...sql`) ikki qatlamda mustahkamlaydi."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import Disa, User
from app.schemas import CreateDisaPayload, DisaMutated, DisaOut, UpdateDisaPayload
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.pin_hmac import hash_pin
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/disa", tags=["disa"])

_NOT_FOUND = "DISA topilmadi"


def _out(item: Disa) -> DisaOut:
    return DisaOut(
        id=str(item.id), name=item.name, has_pin=item.pin_hmac is not None,
        allow_no_pin=item.allow_no_pin, cid_override=item.cid_override,
        digit_timeout=item.digit_timeout, response_timeout=item.response_timeout,
        max_attempts=item.max_attempts, enabled=item.enabled, updated_at=item.updated_at,
    )


async def _get_or_404(session: AsyncSession, tenant_id: str, row_id: str) -> Disa:
    valid_id = parse_uuid(row_id, not_found_message=_NOT_FOUND)
    item = (await session.execute(
        select(Disa).where(Disa.tenant_id == tenant_id, Disa.id == valid_id)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", _NOT_FOUND)
    return item


@router.get("")
async def list_disa(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(Disa).where(Disa.tenant_id == user.tenant_id).order_by(Disa.name)
    )).scalars().all()
    return {"items": [_out(item) for item in items]}


@router.post("", response_model=DisaMutated, status_code=201)
async def create_disa(
    payload: CreateDisaPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DisaMutated:
    tenant_id = str(user.tenant_id)
    target = await create_target(session, tenant_id, "disa", payload.name)
    pin_hmac = hash_pin(settings.require_secret_key(), payload.pin) if payload.pin else None
    row = Disa(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, pin_hmac=pin_hmac,
        allow_no_pin=payload.allow_no_pin, cid_override=payload.cid_override,
        digit_timeout=payload.digit_timeout, response_timeout=payload.response_timeout,
        max_attempts=payload.max_attempts, enabled=payload.enabled,
    )
    session.add(row)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="disa.create",
                        entity="disa", entity_id=str(row.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    row = await _get_or_404(session, tenant_id, str(row.id))
    return DisaMutated(item=_out(row), apply=apply_result.to_dict())


def _apply_disa_simple_fields(row: Disa, payload: UpdateDisaPayload) -> dict:
    """`update_disa`dan ajratilgan — 6 oddiy ixtiyoriy maydon (nomi/PIN'dan
    farqli, side-effect'siz) — CC'ni pasaytirish uchun (crapper, CRAP<10)."""
    diff: dict = {}
    if payload.allow_no_pin is not None:
        row.allow_no_pin = payload.allow_no_pin
        diff["allow_no_pin"] = payload.allow_no_pin
    if payload.cid_override is not None:
        row.cid_override = payload.cid_override or None
        diff["cid_override"] = payload.cid_override
    if payload.digit_timeout is not None:
        row.digit_timeout = payload.digit_timeout
        diff["digit_timeout"] = payload.digit_timeout
    if payload.response_timeout is not None:
        row.response_timeout = payload.response_timeout
        diff["response_timeout"] = payload.response_timeout
    if payload.max_attempts is not None:
        row.max_attempts = payload.max_attempts
        diff["max_attempts"] = payload.max_attempts
    if payload.enabled is not None:
        row.enabled = payload.enabled
        diff["enabled"] = payload.enabled
    return diff


@router.patch("/{row_id}", response_model=DisaMutated)
async def update_disa(
    row_id: str, payload: UpdateDisaPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DisaMutated:
    tenant_id = str(user.tenant_id)
    row = await _get_or_404(session, tenant_id, row_id)
    check_not_stale(row.updated_at, payload.updated_at)

    diff = _apply_disa_simple_fields(row, payload)
    if payload.name is not None:
        row.name = payload.name
        await rename_target(session, str(row.target_id), payload.name)
        diff["name"] = payload.name
    if payload.pin_clear:
        row.pin_hmac = None
        diff["pin"] = "***"
    elif payload.pin is not None:
        row.pin_hmac = hash_pin(settings.require_secret_key(), payload.pin)
        diff["pin"] = "***"

    # m12-contract.md A2: PIN bo'sh FAQAT `allow_no_pin=true` bilan — DB CHECK
    # ham bor, lekin shu yerda ANIQ 422 xabar bilan ERTA tekshiramiz.
    if row.pin_hmac is None and not row.allow_no_pin:
        raise ApiError(422, "pin_required", "PIN bo'sh bo'lishi uchun allow_no_pin=true kerak", field="pin")

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="disa.update",
                        entity="disa", entity_id=str(row.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    row = await _get_or_404(session, tenant_id, str(row.id))
    return DisaMutated(item=_out(row), apply=apply_result.to_dict())


@router.delete("/{row_id}", status_code=204, response_model=None)
async def delete_disa(
    row_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    row = await _get_or_404(session, tenant_id, row_id)
    usages = await usages_for_target(session, tenant_id, str(row.target_id))
    if usages:
        raise ApiError(409, "in_use", "DISA ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, row, str(row.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="disa.delete",
                        entity="disa", entity_id=str(row_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
