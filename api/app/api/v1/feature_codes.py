"""Xususiyat kodlari (S24) — m2a-contract.md §2. O'zgarish dialplan'ga yoziladi (apply)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.db.models import FeatureCode, FeatureCodeDefault, TimeCondition, User
from app.schemas_features import FeatureCodeList, FeatureCodeMutated, FeatureCodeOut, UpdateFeatureCodePayload
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.dialplan_features import FEATURE_ORDER
from app.services.feature_codes import validate_feature_code

router = APIRouter(prefix="/feature-codes", tags=["feature-codes"])


async def _load_codes(session: AsyncSession, tenant_id: str) -> dict[str, FeatureCode]:
    """Faqat M2a'da ishlatiladigan funksiyalar (`queue_*` va h.k. ro'yxatda yo'q)."""
    rows = (await session.execute(
        select(FeatureCode).where(FeatureCode.tenant_id == tenant_id, FeatureCode.feature.in_(FEATURE_ORDER))
    )).scalars().all()
    return {r.feature: r for r in rows}


async def _load_defaults(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(FeatureCodeDefault))).scalars().all()
    return {r.feature: r.code for r in rows}


async def _toggle_codes(session: AsyncSession, tenant_id: str) -> list[str]:
    return list((await session.execute(
        select(TimeCondition.toggle_code).where(
            TimeCondition.tenant_id == tenant_id, TimeCondition.toggle_code.is_not(None))
    )).scalars().all())


async def feature_code_strings(session: AsyncSession, tenant_id: str) -> list[str]:
    """Tenant barcha xususiyat kodlari (faqat satrlar) — vaqt sharti `toggle_code`
    to'qnashuvini tekshirish uchun (`time_conditions.py`, tuzatish b), `_load_codes`
    bilan BIR XIL so'rovdan (dryer: alohida so'rov yozilmasin)."""
    return [c.code for c in (await _load_codes(session, tenant_id)).values()]


def _item(fc: FeatureCode, defaults: dict[str, str]) -> FeatureCodeOut:
    return FeatureCodeOut(feature=fc.feature, code=fc.code, default_code=defaults.get(fc.feature, fc.code),
                          enabled=fc.enabled)


@router.get("", response_model=FeatureCodeList)
async def list_feature_codes(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> FeatureCodeList:
    codes = await _load_codes(session, str(user.tenant_id))
    defaults = await _load_defaults(session)
    return FeatureCodeList(items=[_item(codes[f], defaults) for f in FEATURE_ORDER if f in codes])


async def _change(session: AsyncSession, user: User, ami, feature: str, *, code: str | None,
                  enabled: bool | None, action: str) -> FeatureCodeMutated:
    tenant_id = str(user.tenant_id)
    codes = await _load_codes(session, tenant_id)
    fc = codes.get(feature)
    if fc is None:
        raise ApiError(404, "not_found", "Bunday funksiya kodi yo'q")
    defaults = await _load_defaults(session)
    diff: dict = {}
    if code is not None and code != fc.code:
        others = [c.code for f, c in codes.items() if f != feature]
        validate_feature_code(code, others, await _toggle_codes(session, tenant_id))
        diff["code"] = {"from": fc.code, "to": code}
        fc.code = code
    if enabled is not None and enabled != fc.enabled:
        diff["enabled"] = {"from": fc.enabled, "to": enabled}
        fc.enabled = enabled
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action=action,
                        entity="feature_code", entity_id=feature, diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return FeatureCodeMutated(item=_item(fc, defaults), apply=apply_result.to_dict())


@router.patch("/{feature}", response_model=FeatureCodeMutated)
async def update_feature_code(
    feature: str, payload: UpdateFeatureCodePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> FeatureCodeMutated:
    return await _change(session, user, ami, feature, code=payload.code, enabled=payload.enabled,
                         action="feature_code.update")


@router.post("/{feature}/reset", response_model=FeatureCodeMutated)
async def reset_feature_code(
    feature: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> FeatureCodeMutated:
    """Standart kod va `enabled=true` ga qaytaradi."""
    defaults = await _load_defaults(session)
    if feature not in defaults:
        raise ApiError(404, "not_found", "Bunday funksiya kodi yo'q")
    return await _change(session, user, ami, feature, code=defaults[feature], enabled=True,
                         action="feature_code.reset")
