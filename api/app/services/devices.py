"""M4a §0/§3 — apparatlar domeni: validatsiya, render konteksti (sir bazadan), holat, check-sync NOTIFY.

Lug'at:
  * **TenantProv** — tenant'ning provizioning sozlamalari + hal qilingan SIP server hosti/porti + admin paroli
    (bir so'rov ichida bir marta yuklanadi).
  * **kanonik hash** — `config_hash` hisobida server hosti so'rov `Host` sarlavhasidan olingan bo'lsa `""` qo'yiladi:
    admin ro'yxati (Host'siz) va apparat so'rovi bir xil hash beradi.
  * **holat** — `never` (hech so'ramagan) → `stale_config` (oxirgi berilgan hash ≠ joriy) → `registered` (onlayn
    PJSIP contact'i apparatning oxirgi IP'sidan) → `provisioned`.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import Device, DeviceKey, Extension, SystemSettings
from app.services import prov_catalog
from app.services.ami import AmiError
from app.services.crypto import decrypt_secret
from app.services.dialplan_features import PARK_FIRST_SLOT, PARK_LAST_SLOT
from app.services.live_status import endpoint_contact_hosts
from app.services.prov_render import CommonCtx, DeviceCtx, KeySpec, masked, render
from app.services.prov_settings import ProvSettings

CHECK_SYNC_OPTION = "innova-check-sync"  # asterisk/etc-asterisk/pjsip_notify.conf
_SPEED_DIAL_RE = re.compile(r"^[0-9*#+]{1,32}$")
_VALUELESS_KEYS = {"line", "dnd", "none"}


# ------------------------------------------------------------------ tenant konteksti
@dataclass(frozen=True)
class TenantProv:
    cfg: ProvSettings
    tenant_code: str
    server_host: str
    host_from_request: bool
    server_port: int
    admin_password: str | None


def _host_only(value: str | None) -> str:
    """`pbx.uz:8711` / `[::1]:80` / `10.0.0.5` → host qismi (port/qavslarsiz)."""
    text_value = (value or "").strip()
    if not text_value:
        return ""
    return urlsplit(f"//{text_value}").hostname or ""


def resolve_server_host(configured: str | None, public_base_url: str | None,
                        request_host: str | None) -> tuple[str, bool]:
    """§1: `sip_server_host` → `integrations.public_base_url` hosti → so'rov `Host` sarlavhasi.
    Ikkinchi qiymat — host so'rovdan olindimi (kanonik hash uchun)."""
    if configured:
        return configured, False
    base_host = urlsplit(public_base_url or "").hostname
    if base_host:
        return base_host, False
    return _host_only(request_host), True


def server_port(row: SystemSettings, transport: str) -> int:
    return int((row.sip_tls_port if transport == "tls" else row.sip_udp_port) or 5060)


async def load_tenant_prov(session: AsyncSession, row: SystemSettings, tenant_code: str,
                           request_host: str | None = None) -> TenantProv:
    cfg = ProvSettings.from_raw(row.provisioning)
    host, from_request = resolve_server_host(cfg.sip_server_host, (row.integrations or {}).get("public_base_url"),
                                             request_host)
    admin_password = await decrypt_secret(session, cfg.admin_password_enc) if cfg.admin_password_enc else None
    return TenantProv(cfg=cfg, tenant_code=tenant_code, server_host=host, host_from_request=from_request,
                      server_port=server_port(row, cfg.sip_transport), admin_password=admin_password)


async def sip_passwords(session: AsyncSession, ext_ids: list[str]) -> dict[str, str]:
    """Bir so'rovda bir nechta ichki raqam SIP paroli (faqat render uchun, javobga chiqmaydi)."""
    if not ext_ids:
        return {}
    rows = await session.execute(
        text("select id::text, pgp_sym_decrypt(decode(sip_password_enc, 'base64'), :key) from extensions "
             "where id = any(cast(:ids as uuid[]))"),
        {"ids": list(ext_ids), "key": settings.require_db_key()})
    return {ext_id: secret or "" for ext_id, secret in rows.all()}


def endpoint_id(tenant_code: str, ext: Extension) -> str:
    return f"{tenant_code}-{ext.number}"


def device_ctx(device: Device, ext: Extension, keys: list[DeviceKey], tp: TenantProv, password: str) -> DeviceCtx:
    cfg = tp.cfg
    return DeviceCtx(
        mac=str(device.mac).replace(":", ""), number=ext.number, display_name=ext.callerid_name or ext.name,
        sip_user=endpoint_id(tp.tenant_code, ext), password=password, server_host=tp.server_host,
        server_port=tp.server_port, transport=cfg.sip_transport, admin_password=tp.admin_password,
        label=device.label or "", common=CommonCtx(cfg.language, cfg.timezone, cfg.ntp_server),
        keys=tuple(KeySpec(k.idx, k.type, k.value, k.label) for k in sorted(keys, key=lambda k: k.idx)),
        extra=cfg.extra.get(device.vendor or "", ""),
    )


def config_hash(vendor: str, model: str, ctx: DeviceCtx, tp: TenantProv) -> str:
    canonical = replace(ctx, server_host="") if tp.host_from_request else ctx
    return hashlib.sha256(render(vendor, model, canonical)[1]).hexdigest()


def masked_config(vendor: str, model: str, ctx: DeviceCtx) -> tuple[str, str]:
    filename, body = render(vendor, model, masked(ctx))
    return filename, body.decode()


def device_status(device: Device, current_hash: str, registered: bool) -> str:
    if device.provisioned_at is None or not device.config_hash:
        return "never"
    if device.config_hash != current_hash:
        return "stale_config"
    return "registered" if registered else "provisioned"


def is_registered(device: Device, hosts: set[str] | None) -> bool:
    if not hosts or device.last_ip is None:
        return False
    return str(ipaddress.ip_interface(str(device.last_ip)).ip) in hosts


# ------------------------------------------------------------------ validatsiya
def normalize_mac_or_422(raw: str) -> str:
    try:
        return prov_catalog.normalize_mac(raw)
    except prov_catalog.InvalidMac as exc:
        raise ApiError(422, "invalid_mac", "MAC manzil 12 ta hex belgi bo'lishi kerak", field="mac") from exc


def model_or_422(vendor: str | None, model: str | None) -> prov_catalog.PhoneModel:
    found = prov_catalog.find_model(vendor, model)
    if found is None:
        raise ApiError(422, "unsupported_model", "Bu vendor/model qo'llab-quvvatlanmaydi (GET /devices/models)",
                       field="model")
    return found


async def ensure_mac_free(session: AsyncSession, tenant_id: str, mac: str, exclude_id: str | None = None) -> None:
    query = select(Device.id).where(Device.tenant_id == tenant_id, Device.mac == mac)
    if exclude_id:
        query = query.where(Device.id != exclude_id)
    if (await session.execute(query)).first():
        raise ApiError(409, "mac_taken", "Bu MAC manzilli apparat allaqachon ro'yxatda", field="mac")


async def ensure_extension_accepts(session: AsyncSession, ext: Extension, exclude_id: str | None = None) -> None:
    """§0: `webrtc=true` raqamga ip_phone yo'q; bir raqamdagi apparatlar soni ≤ `max_contacts`."""
    if ext.webrtc:
        raise ApiError(422, "extension_webrtc", "WebRTC ichki raqamiga IP telefon biriktirib bo'lmaydi",
                       field="extension_id")
    query = select(func.count()).select_from(Device).where(Device.extension_id == ext.id)
    if exclude_id:
        query = query.where(Device.id != exclude_id)
    if (await session.execute(query)).scalar_one() >= ext.max_contacts:
        raise ApiError(422, "max_contacts", f"Bu raqamga ko'pi bilan {ext.max_contacts} ta apparat biriktiriladi",
                       field="extension_id", details={"max_contacts": ext.max_contacts})


def _key_error(code: str, message: str, index: int, attr: str) -> ApiError:
    return ApiError(422, code, message, field=f"keys.{index}.{attr}")


def check_key_shape(keys: list, max_keys: int) -> None:
    """Sof qism: tugma raqami modeldagi tugmalar sonidan oshmaydi, takrorlanmaydi; qiymat turiga mos."""
    seen: set[int] = set()
    for index, key in enumerate(keys):
        if key.idx > max_keys:
            raise _key_error("key_out_of_range", f"Bu modelda {max_keys} ta dastur tugmasi bor", index, "idx")
        if key.idx in seen:
            raise _key_error("duplicate_key", f"{key.idx}-tugma takrorlangan", index, "idx")
        seen.add(key.idx)
        _check_key_value(key, index)


def _check_key_value(key, index: int) -> None:
    if key.type == "park" and not (key.value.isdigit() and PARK_FIRST_SLOT <= int(key.value) <= PARK_LAST_SLOT):
        raise _key_error("invalid_park_slot", f"Park sloti {PARK_FIRST_SLOT}–{PARK_LAST_SLOT}", index, "value")
    if key.type == "speed_dial" and not _SPEED_DIAL_RE.fullmatch(key.value):
        raise _key_error("invalid_key_value", "Tez terish raqami: 0-9 * # +", index, "value")


async def validate_keys(session: AsyncSession, tenant_id: str, keys: list, max_keys: int) -> list[DeviceKey]:
    """Tugmalar ro'yxati → `DeviceKey` (device_id keyin qo'yiladi). `blf` — MAVJUD ichki raqam (422 aks holda)."""
    check_key_shape(keys, max_keys)
    blf_numbers = {key.value for key in keys if key.type == "blf"}
    known: set[str] = set()
    if blf_numbers:
        rows = await session.execute(select(Extension.number).where(
            Extension.tenant_id == tenant_id, Extension.number.in_(blf_numbers)))
        known = set(rows.scalars())
    for index, key in enumerate(keys):
        if key.type == "blf" and key.value not in known:
            raise _key_error("unknown_extension", f"Ichki raqam topilmadi: {key.value}", index, "value")
    return [DeviceKey(idx=k.idx, type=k.type, value="" if k.type in _VALUELESS_KEYS else k.value, label=k.label)
            for k in keys]


async def replace_keys(session: AsyncSession, device_id: str, keys: list[DeviceKey]) -> None:
    await session.execute(delete(DeviceKey).where(DeviceKey.device_id == device_id))
    for key in keys:
        key.device_id = device_id
        session.add(key)


async def keys_by_device(session: AsyncSession, device_ids: list[str]) -> dict[str, list[DeviceKey]]:
    result: dict[str, list[DeviceKey]] = {device_id: [] for device_id in device_ids}
    if device_ids:
        rows = await session.execute(select(DeviceKey).where(DeviceKey.device_id.in_(device_ids))
                                     .order_by(DeviceKey.idx))
        for key in rows.scalars():
            result[key.device_id].append(key)
    return result


# ------------------------------------------------------------------ AMI
async def contact_hosts(ami, endpoint_ids: list[str]) -> dict[str, set[str]]:
    return await endpoint_contact_hosts(ami, endpoint_ids) or {}


async def send_check_sync(ami, endpoint: str) -> None:
    """`PJSIPNotify Endpoint=<id> Option=innova-check-sync` → endpoint'ning barcha contact'lariga NOTIFY."""
    await ami.ensure_connected()
    resp = await ami.action("PJSIPNotify", Endpoint=endpoint, Option=CHECK_SYNC_OPTION)
    if str(resp.get("Response", "")).lower() != "success":
        raise AmiError(resp.get("Message", "PJSIPNotify rad etildi"))


async def notify_extension_devices(session: AsyncSession, ami, ext: Extension, tenant_code: str) -> bool:
    """Sir almashtirilganda (`rotate-secret`): raqamda apparat bo'lsa check-sync NOTIFY. Xato — jim (`False`):
    sir almashtirish baribir muvaffaqiyatli, apparat keyingi davriy tekshiruvda yangi config'ni oladi."""
    count = (await session.execute(select(func.count()).select_from(Device).where(
        Device.extension_id == ext.id, Device.enabled.is_(True)))).scalar_one()
    if not count:
        return False
    try:
        await send_check_sync(ami, endpoint_id(tenant_code, ext))
    except (AmiError, OSError, ConnectionError, TimeoutError):
        return False
    return True
