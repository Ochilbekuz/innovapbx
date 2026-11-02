"""M5b — Follow Me va QR orqali sozlash endpointlari (m5b-contract.md).

Admin: `/extensions/{id}/follow-me`, `/extensions/{id}/qr-provisioning`.
Operator: `/me/follow-me`, `/me/qr-provisioning` — faqat o'z raqami (`_require_own_extension`, yo'q bo'lsa 409).
Mantiq `services/follow_me.py` va `services/qr_provisioning.py` da — ikki yo'l BITTA funksiyadan."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_access
from app.api.v1.extensions import _get_extension_or_404
from app.api.v1.me import _require_own_extension
from app.core.optimistic import check_not_stale
from app.db.models import Extension, User
from app.schemas_follow_me import FollowMe, FollowMeOut, FollowMePayload, QrProvisioningOut
from app.services.follow_me import save_follow_me
from app.services.qr_provisioning import issue_token

router = APIRouter(tags=["follow-me"])


def _out(ext: Extension) -> FollowMeOut:
    return FollowMeOut(extension_id=str(ext.id), number=ext.number,
                       follow_me=FollowMe.model_validate(ext.follow_me or {}), updated_at=ext.updated_at)


async def _put(session: AsyncSession, ext: Extension, payload: FollowMePayload, user: User) -> FollowMeOut:
    if payload.updated_at is not None:
        check_not_stale(ext.updated_at, payload.updated_at)
    await save_follow_me(session, ext, FollowMe.model_validate(payload.model_dump(exclude={"updated_at"})),
                         user_id=str(user.id))
    return _out(ext)


async def _qr(session: AsyncSession, ext: Extension, user: User) -> QrProvisioningOut:
    issued = await issue_token(session, ext, user_id=str(user.id))
    return QrProvisioningOut(url=issued.url, expires_at=issued.expires_at, transport=issued.transport)


@router.get("/extensions/{ext_id}/follow-me", response_model=FollowMeOut)
async def get_follow_me(ext_id: str, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> FollowMeOut:
    return _out(await _get_extension_or_404(session, str(user.tenant_id), ext_id))


@router.put("/extensions/{ext_id}/follow-me", response_model=FollowMeOut)
async def put_follow_me(ext_id: str, payload: FollowMePayload, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> FollowMeOut:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    return await _put(session, ext, payload, user)


@router.post("/extensions/{ext_id}/qr-provisioning", response_model=QrProvisioningOut)
async def create_qr(ext_id: str, session: AsyncSession = Depends(get_session),
                    user: User = Depends(require_access)) -> QrProvisioningOut:
    return await _qr(session, await _get_extension_or_404(session, str(user.tenant_id), ext_id), user)


@router.get("/me/follow-me", response_model=FollowMeOut)
async def get_my_follow_me(user: User = Depends(get_current_user)) -> FollowMeOut:
    return _out(_require_own_extension(user))


@router.put("/me/follow-me", response_model=FollowMeOut)
async def put_my_follow_me(payload: FollowMePayload, session: AsyncSession = Depends(get_session),
                           user: User = Depends(get_current_user)) -> FollowMeOut:
    return await _put(session, _require_own_extension(user), payload, user)


@router.post("/me/qr-provisioning", response_model=QrProvisioningOut)
async def create_my_qr(session: AsyncSession = Depends(get_session),
                       user: User = Depends(get_current_user)) -> QrProvisioningOut:
    return await _qr(session, _require_own_extension(user), user)
