"""Trunklar — m0-contract.md «Trunklar (S06)» + m1b-contract.md bo'lim 1
(register-rejim kengaytmasi). `ip` rejim — M0'dagidek realtime (PJSIP
identify view'dan darhol, reload shart emas). `register` rejim — `ps_registrations`/
`ps_auths` realtime qatorlari yangi obyekt sifatida faqat `pjsip reload`dan
keyin ko'rinadi, shuning uchun create/update'da reload yuboriladi. Ikkala
holatda ham dialplan qayta kompilyatsiya shart emas (compiler.py snapshot'ida
trunk endpoint nomidan tashqari narsa ishtirok etmaydi)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import Trunk, User
from app.schemas import (
    CreateTrunkPayload,
    TrunkHealthOut,
    TrunkMutated,
    TrunkOut,
    TrunkTestResult,
    UpdateTrunkPayload,
)
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret
from app.services.live_status import reload_pjsip, test_trunk_endpoint
from app.services.trunk_health import compute_trunk_health, trunk_endpoint_id
from app.services.usages import usages_for_trunk

router = APIRouter(prefix="/trunks", tags=["trunks"])

_REALTIME_APPLY = {"status": "realtime", "revision": None, "message": None}
_REGISTER_RELOAD_APPLY = {"status": "realtime", "revision": None,
                           "message": "pjsip reload yuborildi (registratsiya)"}


async def _trunk_out(session: AsyncSession, ami, trunk: Trunk) -> TrunkOut:
    health = await compute_trunk_health(session, ami, trunk)
    health_out = TrunkHealthOut(state=health.state, rtt_ms=health.rtt_ms, checked_at=health.checked_at,
                                 registration=health.registration, reason=health.reason)
    return TrunkOut(
        id=str(trunk.id), name=trunk.name, host=trunk.host, port=trunk.port,
        match=[str(m) for m in trunk.match_ips], codecs=list(trunk.codecs),
        max_channels=trunk.max_channels, enabled=trunk.enabled, health=health_out,
        updated_at=trunk.updated_at, auth_mode=trunk.auth_mode, username=trunk.username,
        from_domain=trunk.from_domain, outbound_callerid=trunk.outbound_callerid,
        has_password=trunk.password_enc is not None,
    )


def _validate_trunk_mode_fields(
    auth_mode: str, host: str, username: str | None, password: str | None, match: list[str] | None = None,
) -> None:
    """422 `password_required` (register + parolsiz), 422 `bad_host`
    (bo'sh/yaroqsiz host), 422 `bad_match` (`ip` rejim `match` talab qiladi —
    DB `ip_needs_match` cheklovi bilan mos, m0-contract.md bo'lim «Trunklar»)."""
    if not host or not host.strip():
        raise ApiError(422, "bad_host", "Host bo'sh bo'lmasin", field="host")
    if auth_mode == "register" and (not username or not password):
        raise ApiError(422, "password_required",
                        "Registratsiya rejimida username/parol SHART", field="password")
    if auth_mode == "ip" and match is not None and not match:
        raise ApiError(422, "bad_match", "IP rejimida kamida bitta `match` IP/CIDR SHART", field="match")


@router.get("")
async def list_trunks(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin), ami=Depends(get_ami),
) -> dict:
    items = (await session.execute(
        select(Trunk).where(Trunk.tenant_id == user.tenant_id).order_by(Trunk.name)
    )).scalars().all()
    return {"items": [await _trunk_out(session, ami, t) for t in items]}


@router.post("", response_model=TrunkMutated, status_code=201)
async def create_trunk(
    payload: CreateTrunkPayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> TrunkMutated:
    _validate_trunk_mode_fields(payload.auth_mode, payload.host, payload.username, payload.password, payload.match)
    password_enc = await encrypt_secret(session, payload.password) if payload.password else None
    trunk = Trunk(
        tenant_id=user.tenant_id, name=payload.name, auth_mode=payload.auth_mode, host=payload.host,
        port=payload.port, match_ips=payload.match, codecs=payload.codecs, max_channels=payload.max_channels,
        enabled=payload.enabled, username=payload.username, password_enc=password_enc,
        from_domain=payload.from_domain, outbound_callerid=payload.outbound_callerid,
    )
    session.add(trunk)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "name_taken", "Bu nom band", field="name") from exc

    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="trunk.create", entity="trunk", entity_id=str(trunk.id),
                        diff={"name": payload.name, "host": payload.host, "auth_mode": payload.auth_mode,
                              "password": payload.password})
    await session.commit()
    apply_result = _REALTIME_APPLY
    if trunk.auth_mode == "register":
        await reload_pjsip(ami)
        apply_result = _REGISTER_RELOAD_APPLY
    return TrunkMutated(item=await _trunk_out(session, ami, trunk), apply=apply_result)


async def _get_trunk_or_404(session: AsyncSession, tenant_id: str, trunk_id: str) -> Trunk:
    return await get_tenant_scoped_or_404(
        session, Trunk, tenant_id, trunk_id, not_found_message="Trunk topilmadi",
    )


def _pending_trunk_mode(trunk: Trunk, payload: UpdateTrunkPayload) -> tuple[str, str, str | None, list[str]]:
    """Payload'da berilmagan maydonlar uchun joriy trunk qiymati — rejim tekshiruvi
    (`_validate_trunk_mode_fields`) YANGI holatga qarshi ishlashi uchun (pure)."""
    new_auth_mode = payload.auth_mode if payload.auth_mode is not None else trunk.auth_mode
    new_host = payload.host if payload.host is not None else trunk.host
    new_username = payload.username if payload.username is not None else trunk.username
    new_match = payload.match if payload.match is not None else [str(m) for m in trunk.match_ips]
    return new_auth_mode, new_host, new_username, new_match


_TRUNK_DIFF_FIELDS = ("name", "host", "port", "match", "codecs", "max_channels", "enabled",
                      "auth_mode", "username", "from_domain", "outbound_callerid")


def _diff_trunk_fields(trunk: Trunk, payload: UpdateTrunkPayload) -> dict:
    """Faqat payload'da BERILGAN va joriy qiymatdan FARQLI maydonlar audit diff'ga
    tushadi; o'zgargan maydon shu yerda `trunk` obyektiga ham yoziladi (bitta joy, pure)."""
    diff: dict = {}
    for field in _TRUNK_DIFF_FIELDS:
        value = getattr(payload, field)
        if value is None:
            continue
        column = "match_ips" if field == "match" else field
        current = getattr(trunk, column)
        current_cmp = [str(x) for x in current] if field == "match" else current
        if current_cmp != value:
            diff[field] = value
            setattr(trunk, column, value)
    return diff


async def _apply_trunk_password(session: AsyncSession, trunk: Trunk, payload: UpdateTrunkPayload) -> dict:
    """Parol — shifrlash (nosof) kerak bo'lgani uchun `_diff_trunk_fields`dan alohida."""
    if payload.password is None:
        return {}
    trunk.password_enc = await encrypt_secret(session, payload.password) if payload.password else None
    return {"password": payload.password}


def _needs_register_reload(trunk: Trunk, diff: dict) -> bool:
    """`register` rejimida registratsiyaga ta'sir qiluvchi maydon o'zgarsa —
    `ps_registrations`/`ps_auths` yangi qatori faqat reload'dan keyin ko'rinadi."""
    return trunk.auth_mode == "register" and not diff.keys().isdisjoint(
        {"auth_mode", "username", "password", "host", "port"})


async def _trunk_apply_result(ami, trunk: Trunk, diff: dict) -> dict:
    if not _needs_register_reload(trunk, diff):
        return _REALTIME_APPLY
    await reload_pjsip(ami)
    return _REGISTER_RELOAD_APPLY


@router.patch("/{trunk_id}", response_model=TrunkMutated)
async def update_trunk(
    trunk_id: str, payload: UpdateTrunkPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> TrunkMutated:
    trunk = await _get_trunk_or_404(session, str(user.tenant_id), trunk_id)
    check_not_stale(trunk.updated_at, payload.updated_at)

    new_auth_mode, new_host, new_username, new_match = _pending_trunk_mode(trunk, payload)
    has_password = bool(payload.password) or (trunk.password_enc is not None and payload.password is None)
    _validate_trunk_mode_fields(new_auth_mode, new_host, new_username,
                                 "x" if has_password else None, new_match)

    diff = _diff_trunk_fields(trunk, payload)
    diff.update(await _apply_trunk_password(session, trunk, payload))

    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="trunk.update", entity="trunk", entity_id=str(trunk.id), diff=diff)
    await session.commit()
    apply_result = await _trunk_apply_result(ami, trunk, diff)
    return TrunkMutated(item=await _trunk_out(session, ami, trunk), apply=apply_result)


@router.delete("/{trunk_id}", status_code=204, response_model=None)
async def delete_trunk(
    trunk_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> None:
    trunk = await _get_trunk_or_404(session, str(user.tenant_id), trunk_id)
    usages = await usages_for_trunk(session, str(user.tenant_id), trunk_id)
    if usages:
        raise ApiError(409, "in_use", "Trunk ishlatilmoqda — avval bog'liq marshrutlarni o'chiring",
                        details={"usages": usages})
    await session.delete(trunk)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="trunk.delete", entity="trunk", entity_id=str(trunk_id))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "in_use", "Trunk ishlatilmoqda — avval bog'liq marshrutlarni o'chiring",
                        details={"usages": usages}) from exc


@router.post("/{trunk_id}/test", response_model=TrunkTestResult)
async def test_trunk(
    trunk_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> TrunkTestResult:
    trunk = await _get_trunk_or_404(session, str(user.tenant_id), trunk_id)
    endpoint_id = await trunk_endpoint_id(session, trunk)
    result = await test_trunk_endpoint(ami, endpoint_id)
    return TrunkTestResult(**result)
