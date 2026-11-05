"""M4a §3 — `/devices` javob ko'rinishlari: holat (joriy render hashi + jonli PJSIP contact), maskalangan config."""
from __future__ import annotations

import ipaddress

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.settings import get_settings_row
from app.core.lookups import get_tenant_code_and_timezone
from app.db.models import Device, DeviceKey, DiscoveredDevice, Extension, ProvisionRequest
from app.schemas_devices import (
    DeviceConfigOut,
    DeviceExtensionOut,
    DeviceKeyOut,
    DeviceOut,
    DiscoveredOut,
    ProvisionRequestOut,
)
from app.services import devices as svc
from app.services import prov_catalog
from app.services.prov_render import content_type


def mac_text(value) -> str:
    return str(value).replace(":", "").lower()


def ip_text(value) -> str | None:
    return None if value is None else str(ipaddress.ip_interface(str(value)).ip)


async def tenant_prov(session: AsyncSession, tenant_id: str, request_host: str | None = None) -> svc.TenantProv:
    row = await get_settings_row(session, tenant_id)
    code, timezone = await get_tenant_code_and_timezone(session, tenant_id)
    return await svc.load_tenant_prov(session, row, code, request_host, timezone)


def _device_out(device: Device, ext: Extension, keys: list[DeviceKey], status: str, registered: bool) -> DeviceOut:
    return DeviceOut(
        id=str(device.id), mac=mac_text(device.mac), vendor=device.vendor, model=device.model or "",
        label=device.label, extension=DeviceExtensionOut(id=str(ext.id), number=ext.number, name=ext.name),
        enabled=device.enabled, status=status, provisioned_at=device.provisioned_at,
        last_seen_at=device.last_seen_at, last_ip=ip_text(device.last_ip), firmware=device.firmware,
        user_agent=device.user_agent, registered=registered, keys_count=len(keys),
        keys=[DeviceKeyOut(idx=k.idx, type=k.type, value=k.value, label=k.label) for k in keys],
        notes=device.notes, created_at=device.created_at, updated_at=device.updated_at,
    )


async def device_views(session: AsyncSession, ami, tenant_id: str,
                       pairs: list[tuple[Device, Extension]]) -> list[DeviceOut]:
    if not pairs:
        return []
    tp = await tenant_prov(session, tenant_id)
    keys = await svc.keys_by_device(session, [str(d.id) for d, _ in pairs])
    passwords = await svc.sip_passwords(session, sorted({str(e.id) for _, e in pairs}))
    hosts = await svc.contact_hosts(ami, sorted({svc.endpoint_id(tp.tenant_code, e) for _, e in pairs}))
    out = []
    for device, ext in pairs:
        dkeys = keys[str(device.id)]
        ctx = svc.device_ctx(device, ext, dkeys, tp, passwords.get(str(ext.id), ""))
        registered = svc.is_registered(device, hosts.get(svc.endpoint_id(tp.tenant_code, ext)))
        status = svc.device_status(device, svc.config_hash(device.vendor, device.model or "", ctx, tp), registered)
        out.append(_device_out(device, ext, dkeys, status, registered))
    return out


async def device_view(session: AsyncSession, ami, tenant_id: str, device: Device) -> DeviceOut:
    ext = await session.get(Extension, device.extension_id)
    return (await device_views(session, ami, tenant_id, [(device, ext)]))[0]


async def config_view(session: AsyncSession, tenant_id: str, device: Device, request_host: str | None) -> DeviceConfigOut:
    """Admin ko'rinishi — sirlar `***` (render `masked(ctx)` dan; haqiqiy parol umuman o'qilmaydi)."""
    tp = await tenant_prov(session, tenant_id, request_host)
    ext = await session.get(Extension, device.extension_id)
    keys = (await svc.keys_by_device(session, [str(device.id)]))[str(device.id)]
    ctx = svc.device_ctx(device, ext, keys, tp, password="")
    filename, content = svc.masked_config(device.vendor, device.model or "", ctx)
    return DeviceConfigOut(filename=filename, content_type=content_type(device.vendor), content=content)


async def is_device_registered(session: AsyncSession, ami, tenant_id: str, device: Device) -> tuple[bool, str]:
    ext = await session.get(Extension, device.extension_id)
    endpoint = svc.endpoint_id(await get_tenant_code(session, tenant_id), ext)
    hosts = await svc.contact_hosts(ami, [endpoint])
    return svc.is_registered(device, hosts.get(endpoint)), endpoint


def discovered_out(row: DiscoveredDevice) -> DiscoveredOut:
    return DiscoveredOut(
        mac=mac_text(row.mac), vendor=row.vendor, model=row.model, ip=ip_text(row.ip), user_agent=row.user_agent,
        firmware=row.firmware, first_seen_at=row.first_seen_at, last_seen_at=row.last_seen_at,
        requests=row.requests, supported=prov_catalog.find_model(row.vendor, row.model) is not None,
    )


def request_out(row: ProvisionRequest) -> ProvisionRequestOut:
    return ProvisionRequestOut(
        id=row.id, at=row.at, ip=ip_text(row.ip), mac=None if row.mac is None else mac_text(row.mac),
        vendor=row.vendor, path=row.path, status_code=row.status_code, reason=row.reason, user_agent=row.user_agent,
    )


async def device_pairs(session: AsyncSession, tenant_id: str, *, extension_id: str | None = None,
                       vendor: str | None = None, q: str | None = None) -> list[tuple[Device, Extension]]:
    query = (select(Device, Extension).join(Extension, Extension.id == Device.extension_id)
             .where(Device.tenant_id == tenant_id, Device.kind == "ip_phone"))
    if extension_id:
        query = query.where(Device.extension_id == extension_id)
    if vendor:
        query = query.where(Device.vendor == vendor)
    if q and q.strip():
        query = query.where(_search(q.strip()))
    rows = await session.execute(query.order_by(Extension.number, Device.created_at))
    return [(device, ext) for device, ext in rows.all()]


def _search(term: str):
    like = f"%{term.lower()}%"
    mac_like = f"%{term.lower().replace(':', '').replace('-', '')}%"
    return or_(func.lower(Device.label).like(like), func.lower(Device.model).like(like),
               Extension.number.like(f"%{term}%"), func.lower(Extension.name).like(like),
               func.replace(cast(Device.mac, Text), ":", "").like(mac_like))
