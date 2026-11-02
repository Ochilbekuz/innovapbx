"""M2c §1 (sozlamalar) + §3 (toll-fraud, bloklangan ichki raqamlar, hodisalar).
SIP hujum himoyasi (§2: `/security/bans`, `/security/stats`) BOSHQA agent ishi —
bu faylda YO'Q (`GET /security/events` — ikkalasi UCHUN UMUMIY jadval/endpoint,
`kind` ro'yxatida sip_guard kindlari ham bor, shu sabab filtr parametrsiz
ikkalasining hodisalari ham chiqadi)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import Extension, SecurityEvent, SystemSettings, User
from app.schemas_security import (
    SecurityEventList,
    SecurityEventOut,
    SecuritySettingsMutated,
    SecuritySettingsOut,
    SipGuardOut,
    TollBlockList,
    TollBlockOut,
    TollFraudOut,
    TollUnblockItem,
    TollUnblockResult,
    UpdateSecuritySettingsPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.api.v1.settings import get_settings_row
from app.services.security_config import SipGuardConfig, TollFraudConfig, check_int, check_nets, parse_sip_guard, parse_toll_fraud

router = APIRouter(prefix="/security", tags=["security"])


def _sip_guard_out(cfg: SipGuardConfig) -> SipGuardOut:
    return SipGuardOut(enabled=cfg.enabled, max_failures=cfg.max_failures, window_s=cfg.window_s,
                        ban_s=cfg.ban_s, trusted_nets=list(cfg.trusted_nets),
                       trust_lan=cfg.trust_lan)


def _toll_fraud_out(cfg: TollFraudConfig) -> TollFraudOut:
    return TollFraudOut(enabled=cfg.enabled, max_concurrent_outbound=cfg.max_concurrent_outbound,
                         ext_max_per_hour=cfg.ext_max_per_hour,
                         ext_international_per_day=cfg.ext_international_per_day)


def _settings_out(row: SystemSettings) -> SecuritySettingsOut:
    return SecuritySettingsOut(
        sip_guard=_sip_guard_out(parse_sip_guard(row.sip_guard)),
        toll_fraud=_toll_fraud_out(parse_toll_fraud(row.toll_fraud)),
        updated_at=row.updated_at,
    )


def _sub_changes(item, fields: tuple[str, ...]) -> dict:
    return {f: getattr(item, f) for f in item.model_fields_set if f in fields}


def _validate_int_fields(prefix: str, changes: dict, fields: tuple[str, ...]) -> None:
    for f in fields:
        if f in changes:
            err = check_int(f"{prefix}.{f}", changes[f])
            if err:
                raise ApiError(422, "bad_value", err, field=f"{prefix}.{f}")


_SIP_GUARD_INT_FIELDS = ("max_failures", "window_s", "ban_s")
_TOLL_FRAUD_INT_FIELDS = ("max_concurrent_outbound", "ext_max_per_hour", "ext_international_per_day")


def _validate_sip_guard_changes(changes: dict) -> None:
    _validate_int_fields("sip_guard", changes, _SIP_GUARD_INT_FIELDS)
    if "trusted_nets" in changes:
        err = check_nets(changes["trusted_nets"])
        if err:
            raise ApiError(422, "bad_value", err, field="sip_guard.trusted_nets")


def _validate_toll_fraud_changes(changes: dict) -> None:
    _validate_int_fields("toll_fraud", changes, _TOLL_FRAUD_INT_FIELDS)


@router.get("/settings", response_model=SecuritySettingsOut)
async def get_security_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> SecuritySettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    return _settings_out(row)


@router.patch("/settings", response_model=SecuritySettingsMutated)
async def update_security_settings(
    payload: UpdateSecuritySettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> SecuritySettingsMutated:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    check_not_stale(row.updated_at, payload.updated_at)

    diff: dict = {}
    recompile = False
    if payload.sip_guard is not None:
        changes = _sub_changes(payload.sip_guard, _SIP_GUARD_INT_FIELDS + ("enabled", "trusted_nets", "trust_lan"))
        _validate_sip_guard_changes(changes)
        if changes:
            row.sip_guard = {**row.sip_guard, **changes}
            diff["sip_guard"] = changes
    if payload.toll_fraud is not None:
        changes = _sub_changes(payload.toll_fraud, _TOLL_FRAUD_INT_FIELDS + ("enabled",))
        _validate_toll_fraud_changes(changes)
        if changes:
            row.toll_fraud = {**row.toll_fraud, **changes}
            diff["toll_fraud"] = changes
            recompile = "max_concurrent_outbound" in changes

    await session.flush()
    await session.refresh(row)  # updated_at — DB triggeri yangilaydi (extensions.py bilan BIR XIL qolip)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="security.settings",
                        entity="security_settings", entity_id=tenant_id, diff=diff)
    if recompile:
        apply_result = (await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)).to_dict()
    else:
        apply_result = {"status": "unchanged", "revision": None,
                        "message": "Dialplan qayta kompilyatsiya qilinmadi — bir vaqtdagi chiquvchi limit o'zgarmadi"}
    await session.commit()
    return SecuritySettingsMutated(item=_settings_out(row), apply=apply_result)


def _toll_block_out(ext: Extension) -> TollBlockOut:
    return TollBlockOut(extension_id=str(ext.id), number=ext.number, name=ext.name,
                        blocked_at=ext.toll_blocked_at, reason=ext.toll_block_reason)


@router.get("/toll-blocks", response_model=TollBlockList)
async def list_toll_blocks(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> TollBlockList:
    rows = (await session.execute(
        select(Extension).where(Extension.tenant_id == user.tenant_id, Extension.toll_blocked_at.is_not(None))
        .order_by(Extension.toll_blocked_at.desc())
    )).scalars().all()
    return TollBlockList(items=[_toll_block_out(r) for r in rows])


@router.post("/toll-blocks/{extension_id}/unblock", response_model=TollUnblockResult)
async def unblock_toll(
    extension_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> TollUnblockResult:
    tenant_id = str(user.tenant_id)
    ext = (await session.execute(
        select(Extension).where(Extension.id == extension_id, Extension.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if ext is None:
        raise ApiError(404, "not_found", "Ichki raqam topilmadi")
    if ext.toll_blocked_at is None:
        raise ApiError(409, "not_blocked", "Bu ichki raqam bloklanmagan")

    now = datetime.now(timezone.utc)
    diff = {"toll_blocked_at": {"from": ext.toll_blocked_at.isoformat(), "to": None}}
    ext.toll_blocked_at = None
    ext.toll_block_reason = None
    ext.toll_unblocked_at = now
    session.add(SecurityEvent(tenant_id=tenant_id, kind="toll_unblocked", extension_id=ext.id,
                              details={"number": ext.number}))
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="security.toll_unblock",
                        entity="extension", entity_id=ext.id, diff=diff)
    await session.commit()
    return TollUnblockResult(item=TollUnblockItem(extension_id=str(ext.id), number=ext.number))


@router.get("/events", response_model=SecurityEventList)
async def list_security_events(
    limit: int = Query(default=100, ge=1, le=500), kind: str | None = None,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> SecurityEventList:
    stmt = (
        select(SecurityEvent, Extension.number)
        .outerjoin(Extension, Extension.id == SecurityEvent.extension_id)
        .where(SecurityEvent.tenant_id == user.tenant_id)
        .order_by(SecurityEvent.at.desc())
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(SecurityEvent.kind == kind)
    rows = (await session.execute(stmt)).all()
    return SecurityEventList(items=[
        SecurityEventOut(id=ev.id, at=ev.at, kind=ev.kind, ip=str(ev.ip) if ev.ip else None,
                         extension=number, details=ev.details, transport=ev.transport)
        for ev, number in rows
    ])
