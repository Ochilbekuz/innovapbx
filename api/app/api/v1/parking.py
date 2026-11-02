"""Park qilingan qo'ng'iroqlar (S26, faqat ko'rish) — m2a-contract.md §3. Manba: AMI `ParkedCalls`."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.lookups import get_tenant_code
from app.db.models import User
from app.schemas_features import ParkingStatusOut
from app.services.parking import parking_status

router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("", response_model=ParkingStatusOut)
async def get_parking(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin), ami=Depends(get_ami),
) -> ParkingStatusOut:
    code = await get_tenant_code(session, str(user.tenant_id))
    return ParkingStatusOut(**await parking_status(ami, code))
