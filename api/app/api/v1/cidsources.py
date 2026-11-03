"""M9 B2 — CID Lookup manbalari (m9-freepbx-gaps-contract.md Bo'lak B2). CRUD +
jonli sinov (`/test`); haqiqiy qidiruv dialplan uchun `app/api/internal_cidlookup.py`da
(`app/services/cid_lookup.py` — ikkalasi BIR XIL dispetcherni chaqiradi, dryer)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.api.v1.integrations import check_webhook_url
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import CidLookupSource, InboundRoute, User
from app.schemas import (
    CidSourceOut,
    CidSourceTestPayload,
    CidSourceTestResult,
    CidSourceUsageRef,
    CreateCidSourcePayload,
    UpdateCidSourcePayload,
)
from app.services.audit import record_audit
from app.services.cid_lookup import test_lookup

router = APIRouter(prefix="/cid-sources", tags=["cid-sources"])

_NAME_TAKEN = ApiError(409, "name_taken", "Shu nomli CID Lookup manbai allaqachon mavjud", field="name")


async def _used_by(session: AsyncSession, tenant_id: str, source_id: str) -> list[CidSourceUsageRef]:
    rows = (await session.execute(
        select(InboundRoute.id, InboundRoute.name).where(
            InboundRoute.tenant_id == tenant_id, InboundRoute.cid_lookup_source_id == source_id)
    )).all()
    return [CidSourceUsageRef(id=str(r.id), name=r.name) for r in rows]


async def _source_out(session: AsyncSession, tenant_id: str, source: CidLookupSource) -> CidSourceOut:
    return CidSourceOut(
        id=str(source.id), name=source.name, kind=source.kind, http_url=source.http_url,
        http_json_path=source.http_json_path, timeout_ms=source.timeout_ms, cache_ttl_s=source.cache_ttl_s,
        enabled=source.enabled, used_by=await _used_by(session, tenant_id, str(source.id)),
        updated_at=source.updated_at,
    )


async def _get_source_or_404(session: AsyncSession, tenant_id: str, source_id: str) -> CidLookupSource:
    return await get_tenant_scoped_or_404(
        session, CidLookupSource, tenant_id, source_id, not_found_message="CID Lookup manbai topilmadi",
    )


async def _validate_http_url(kind: str, http_url: str | None) -> str | None:
    """`kind == "http"` bo'lsa URL majburiy va SSRF tekshiruvidan o'tadi (`{number}`
    shabloni — host qismiga tegmaydi, `check_webhook_url` baribir ishlaydi)."""
    if kind != "http":
        return None
    if not http_url:
        raise ApiError(422, "required", "http manbai uchun http_url majburiy", field="http_url")
    return await check_webhook_url(http_url, field="http_url")


@router.get("")
async def list_cid_sources(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(CidLookupSource).where(CidLookupSource.tenant_id == user.tenant_id).order_by(CidLookupSource.name)
    )).scalars().all()
    return {"items": [await _source_out(session, str(user.tenant_id), s) for s in items]}


@router.post("", response_model=CidSourceOut, status_code=201)
async def create_cid_source(
    payload: CreateCidSourcePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> CidSourceOut:
    tenant_id = str(user.tenant_id)
    http_url = await _validate_http_url(payload.kind, payload.http_url)

    source = CidLookupSource(
        tenant_id=tenant_id, name=payload.name, kind=payload.kind, http_url=http_url,
        http_json_path=payload.http_json_path, timeout_ms=payload.timeout_ms, cache_ttl_s=payload.cache_ttl_s,
        enabled=payload.enabled,
    )
    session.add(source)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="cid_source.create",
                        entity="cid_source", entity_id=str(source.id), diff={"name": payload.name,
                                                                              "kind": payload.kind})
    await session.commit()
    source = await _get_source_or_404(session, tenant_id, str(source.id))
    return await _source_out(session, tenant_id, source)


@router.patch("/{source_id}", response_model=CidSourceOut)
async def update_cid_source(
    source_id: str, payload: UpdateCidSourcePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> CidSourceOut:
    tenant_id = str(user.tenant_id)
    source = await _get_source_or_404(session, tenant_id, source_id)
    check_not_stale(source.updated_at, payload.updated_at)

    diff = await _apply_cid_source_patch(source, payload)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="cid_source.update",
                        entity="cid_source", entity_id=str(source.id), diff=diff)
    await session.commit()
    source = await _get_source_or_404(session, tenant_id, source_id)
    return await _source_out(session, tenant_id, source)


async def _apply_cid_source_patch(source: CidLookupSource, payload: UpdateCidSourcePayload) -> dict:
    """Berilgan maydonlarni yozadi, `diff`ni qaytaradi (CRAP pasaytirish — asosiy
    funksiyadan ajratilgan)."""
    diff: dict = {}
    new_kind = payload.kind if payload.kind is not None else source.kind
    new_http_url = payload.http_url if payload.http_url is not None else source.http_url
    if payload.kind is not None or payload.http_url is not None:
        new_http_url = await _validate_http_url(new_kind, new_http_url)
    for field, value in (("name", payload.name), ("kind", payload.kind), ("http_url", new_http_url),
                          ("http_json_path", payload.http_json_path), ("timeout_ms", payload.timeout_ms),
                          ("cache_ttl_s", payload.cache_ttl_s), ("enabled", payload.enabled)):
        if value is not None and value != getattr(source, field):
            setattr(source, field, value)
            diff[field] = value
    return diff


@router.delete("/{source_id}", status_code=204, response_model=None)
async def delete_cid_source(
    source_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    source = await _get_source_or_404(session, tenant_id, source_id)
    used_by = await _used_by(session, tenant_id, source_id)
    if used_by:
        raise ApiError(409, "in_use", f"«{source.name}» hali kiruvchi marshrut(lar)da ishlatilmoqda",
                        details={"usages": [u.model_dump() for u in used_by]})

    await session.delete(source)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="cid_source.delete",
                        entity="cid_source", entity_id=str(source_id))
    await session.commit()


@router.post("/{source_id}/test", response_model=CidSourceTestResult)
async def test_cid_source(
    source_id: str, payload: CidSourceTestPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> CidSourceTestResult:
    tenant_id = str(user.tenant_id)
    source = await _get_source_or_404(session, tenant_id, source_id)
    name, ms, error = await test_lookup(session, tenant_id, source, payload.number)
    return CidSourceTestResult(name=name, ms=ms, error=error)
