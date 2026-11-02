"""M4a §3 — `/devices` (admin): telefon apparatlari, dastur tugmalari, topilgan apparatlar, modellar, jurnal.

Sir (SIP/admin paroli) hech qaysi javobda yo'q: `/devices/{id}/config` — `***` bilan (reveal YO'Q).
Statik yo'llar (`/discovered`, `/models`, `/requests`) `/{device_id}` dan OLDIN e'lon qilinadi.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import Device, DiscoveredDevice, Extension, ProvisionRequest, User
from app.schemas_devices import (
    AssignDiscoveredPayload,
    CreateDevicePayload,
    DeviceConfigOut,
    DeviceItem,
    DeviceList,
    DiscoveredList,
    PhoneModelList,
    PhoneModelOut,
    ProvisionRequestList,
    PutKeysPayload,
    ResyncResult,
    UpdateDevicePayload,
    Vendor,
)
from app.services import device_views as views
from app.services import devices as svc
from app.services import prov_catalog
from app.services.ami import AmiError
from app.services.audit import record_audit

router = APIRouter(prefix="/devices", tags=["devices"])
REQUESTS_LIMIT = 200


def _tenant(user: User) -> str:
    return str(user.tenant_id)


async def _audit(session: AsyncSession, user: User, action: str, entity_id: str, diff: dict[str, Any] | None = None,
                 entity: str = "device") -> None:
    await record_audit(session, tenant_id=_tenant(user), user_id=str(user.id), action=action, entity=entity,
                       entity_id=entity_id, diff=diff)


async def _device_or_404(session: AsyncSession, user: User, device_id: str) -> Device:
    device = await get_tenant_scoped_or_404(session, Device, _tenant(user), device_id,
                                            not_found_message="Apparat topilmadi")
    if device.kind != "ip_phone":
        raise ApiError(404, "not_found", "Apparat topilmadi")
    return device


async def _extension_or_422(session: AsyncSession, user: User, extension_id: str) -> Extension:
    try:
        return await get_tenant_scoped_or_404(session, Extension, _tenant(user), extension_id,
                                              not_found_message="Ichki raqam topilmadi", field="extension_id")
    except ApiError as exc:
        raise ApiError(422, "unknown_extension", exc.message, field="extension_id") from exc


async def _drop_discovered(session: AsyncSession, tenant_id: str, mac: str) -> None:
    await session.execute(delete(DiscoveredDevice).where(DiscoveredDevice.tenant_id == tenant_id,
                                                         DiscoveredDevice.mac == mac))


async def _create(session: AsyncSession, user: User, payload: CreateDevicePayload) -> Device:
    """Yagona yaratish yo'li (`POST /devices` va `assign`): validatsiya → saqlash → topilganlardan o'chirish."""
    tenant_id = _tenant(user)
    mac = svc.normalize_mac_or_422(payload.mac)
    model = svc.model_or_422(payload.vendor, payload.model)
    ext = await _extension_or_422(session, user, payload.extension_id)
    await svc.ensure_mac_free(session, tenant_id, mac)
    await svc.ensure_extension_accepts(session, ext)
    keys = await svc.validate_keys(session, tenant_id, payload.keys, model.keys)
    device = Device(tenant_id=tenant_id, extension_id=str(ext.id), kind="ip_phone", vendor=model.vendor,
                    model=model.model, mac=mac, label=payload.label, notes=payload.notes, enabled=payload.enabled)
    session.add(device)
    await session.flush()
    await svc.replace_keys(session, str(device.id), keys)
    await _drop_discovered(session, tenant_id, mac)
    await _audit(session, user, "device.create", str(device.id), {
        "mac": mac, "vendor": model.vendor, "model": model.model, "extension": ext.number,
        "label": payload.label, "keys": len(keys)})
    await session.commit()
    await session.refresh(device)
    return device


# ------------------------------------------------------------------ ro'yxat / yaratish
@router.get("", response_model=DeviceList)
async def list_devices(extension_id: str | None = None, vendor: Vendor | None = None, q: str | None = None,
                       session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
                       ami=Depends(get_ami)) -> DeviceList:
    if extension_id:
        await _extension_or_422(session, user, extension_id)
    pairs = await views.device_pairs(session, _tenant(user), extension_id=extension_id, vendor=vendor, q=q)
    return DeviceList(items=await views.device_views(session, ami, _tenant(user), pairs))


@router.post("", response_model=DeviceItem, status_code=201)
async def create_device(payload: CreateDevicePayload, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access), ami=Depends(get_ami)) -> DeviceItem:
    device = await _create(session, user, payload)
    return DeviceItem(item=await views.device_view(session, ami, _tenant(user), device))


# ------------------------------------------------------------------ statik yo'llar
@router.get("/models", response_model=PhoneModelList)
async def list_models(_user: User = Depends(require_access)) -> PhoneModelList:
    return PhoneModelList(items=[PhoneModelOut(vendor=m.vendor, model=m.model, keys=m.keys, family=m.family)
                                 for m in prov_catalog.MODELS])


@router.get("/discovered", response_model=DiscoveredList)
async def list_discovered(session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> DiscoveredList:
    rows = await session.execute(select(DiscoveredDevice).where(DiscoveredDevice.tenant_id == _tenant(user))
                                 .order_by(DiscoveredDevice.last_seen_at.desc()))
    return DiscoveredList(items=[views.discovered_out(row) for row in rows.scalars()])


async def _discovered_or_404(session: AsyncSession, user: User, raw_mac: str) -> DiscoveredDevice:
    mac = prov_catalog.try_mac(raw_mac)
    row = await session.get(DiscoveredDevice, (_tenant(user), mac)) if mac else None
    if row is None:
        raise ApiError(404, "not_found", "Topilgan apparat yo'q")
    return row


@router.post("/discovered/{mac}/assign", response_model=DeviceItem, status_code=201)
async def assign_discovered(mac: str, payload: AssignDiscoveredPayload, session: AsyncSession = Depends(get_session),
                            user: User = Depends(require_access), ami=Depends(get_ami)) -> DeviceItem:
    row = await _discovered_or_404(session, user, mac)
    vendor = payload.vendor or row.vendor
    if vendor is None:
        raise ApiError(422, "unsupported_model", "Vendor aniqlanmadi — `vendor` va `model` ni kiriting", field="vendor")
    create = CreateDevicePayload(mac=views.mac_text(row.mac), vendor=vendor, model=payload.model or row.model or "?",
                                 extension_id=payload.extension_id, label=payload.label)
    device = await _create(session, user, create)
    return DeviceItem(item=await views.device_view(session, ami, _tenant(user), device))


@router.delete("/discovered/{mac}", status_code=204)
async def dismiss_discovered(mac: str, session: AsyncSession = Depends(get_session),
                             user: User = Depends(require_access)) -> Response:
    row = await _discovered_or_404(session, user, mac)
    await session.delete(row)
    await _audit(session, user, "discovered_device.delete", views.mac_text(row.mac), entity="discovered_device")
    await session.commit()
    return Response(status_code=204)


@router.get("/requests", response_model=ProvisionRequestList)
async def list_requests(mac: str | None = None, ip: str | None = None,
                        limit: int = Query(default=REQUESTS_LIMIT, ge=1, le=REQUESTS_LIMIT),
                        session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> ProvisionRequestList:
    query = select(ProvisionRequest).where(ProvisionRequest.tenant_id == _tenant(user))
    if mac:
        query = query.where(ProvisionRequest.mac == svc.normalize_mac_or_422(mac))
    if ip:
        query = query.where(func.host(ProvisionRequest.ip) == ip.strip())
    rows = await session.execute(query.order_by(ProvisionRequest.id.desc()).limit(limit))
    return ProvisionRequestList(items=[views.request_out(row) for row in rows.scalars()])


# ------------------------------------------------------------------ bitta apparat
@router.get("/{device_id}", response_model=DeviceItem)
async def get_device(device_id: str, session: AsyncSession = Depends(get_session),
                     user: User = Depends(require_access), ami=Depends(get_ami)) -> DeviceItem:
    device = await _device_or_404(session, user, device_id)
    return DeviceItem(item=await views.device_view(session, ami, _tenant(user), device))


async def _mac_change(session: AsyncSession, user: User, device: Device, payload: UpdateDevicePayload) -> dict:
    if payload.mac is None:
        return {}
    mac = svc.normalize_mac_or_422(payload.mac)
    await svc.ensure_mac_free(session, _tenant(user), mac, exclude_id=str(device.id))
    return {"mac": mac}


async def _model_change(session: AsyncSession, device: Device, payload: UpdateDevicePayload) -> dict:
    """Model almashsa — mavjud tugmalar yangi modelga sig'adimi (aks holda 422 `key_out_of_range`)."""
    if not payload.model_fields_set & {"vendor", "model"}:
        return {}
    model = svc.model_or_422(payload.vendor or device.vendor, payload.model or device.model)
    svc.check_key_shape((await svc.keys_by_device(session, [str(device.id)]))[str(device.id)], model.keys)
    return {"vendor": model.vendor, "model": model.model}


async def _extension_change(session: AsyncSession, user: User, device: Device, payload: UpdateDevicePayload) -> dict:
    if payload.extension_id is None:
        return {}
    ext = await _extension_or_422(session, user, payload.extension_id)
    await svc.ensure_extension_accepts(session, ext, exclude_id=str(device.id))
    return {"extension_id": str(ext.id)}


def _plain_changes(payload: UpdateDevicePayload) -> dict:
    changes = {name: getattr(payload, name) for name in ("label", "notes") if name in payload.model_fields_set}
    if payload.enabled is not None:
        changes["enabled"] = payload.enabled
    return changes


async def _apply_update(session: AsyncSession, user: User, device: Device, payload: UpdateDevicePayload) -> dict:
    changes: dict[str, Any] = {
        **await _mac_change(session, user, device, payload), **await _model_change(session, device, payload),
        **await _extension_change(session, user, device, payload), **_plain_changes(payload)}
    for name, value in changes.items():
        setattr(device, name, value)
    return changes


@router.patch("/{device_id}", response_model=DeviceItem)
async def update_device(device_id: str, payload: UpdateDevicePayload, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access), ami=Depends(get_ami)) -> DeviceItem:
    device = await _device_or_404(session, user, device_id)
    check_not_stale(device.updated_at, payload.updated_at)
    changes = await _apply_update(session, user, device, payload)
    if changes:
        await session.flush()
        await _audit(session, user, "device.update", str(device.id), changes)
        await session.commit()
        await session.refresh(device)
    return DeviceItem(item=await views.device_view(session, ami, _tenant(user), device))


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> Response:
    device = await _device_or_404(session, user, device_id)
    await session.delete(device)
    await _audit(session, user, "device.delete", str(device.id), {"mac": views.mac_text(device.mac)})
    await session.commit()
    return Response(status_code=204)


@router.put("/{device_id}/keys", response_model=DeviceItem)
async def put_keys(device_id: str, payload: PutKeysPayload, session: AsyncSession = Depends(get_session),
                   user: User = Depends(require_access), ami=Depends(get_ami)) -> DeviceItem:
    device = await _device_or_404(session, user, device_id)
    if payload.updated_at is not None:
        check_not_stale(device.updated_at, payload.updated_at)
    model = svc.model_or_422(device.vendor, device.model)
    keys = await svc.validate_keys(session, _tenant(user), payload.keys, model.keys)
    await svc.replace_keys(session, str(device.id), keys)
    device.updated_at = func.now()
    await session.flush()
    await _audit(session, user, "device.keys", str(device.id),
                 {"op": "keys", "keys": [f"{k.idx}:{k.type}:{k.value}" for k in keys]})
    await session.commit()
    await session.refresh(device)
    return DeviceItem(item=await views.device_view(session, ami, _tenant(user), device))


@router.post("/{device_id}/resync", response_model=ResyncResult)
async def resync_device(device_id: str, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access), ami=Depends(get_ami)) -> ResyncResult:
    device = await _device_or_404(session, user, device_id)
    registered, endpoint = await views.is_device_registered(session, ami, _tenant(user), device)
    if not registered:
        raise ApiError(409, "not_registered", "Apparat ro'yxatdan o'tmagan — NOTIFY yuborib bo'lmaydi")
    try:
        await svc.send_check_sync(ami, endpoint)
    except (AmiError, OSError, ConnectionError, TimeoutError) as exc:
        raise ApiError(502, "ami_error", "Asterisk bilan bog'lanib bo'lmadi") from exc
    await _audit(session, user, "device.resync", str(device.id), {"op": "resync", "endpoint": endpoint})
    await session.commit()
    return ResyncResult(ok=True, endpoint=endpoint)


@router.get("/{device_id}/config", response_model=DeviceConfigOut)
async def view_config(device_id: str, request: Request, session: AsyncSession = Depends(get_session),
                      user: User = Depends(require_access)) -> DeviceConfigOut:
    device = await _device_or_404(session, user, device_id)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return await views.config_view(session, _tenant(user), device, host)
