"""M4a §0 — `GET /prov/<token>/<fayl>`: apparat config'ni o'zi oladi (HTTP Basic'siz). Himoya qatlamlari tartibi:

  1. IP bloklanganmi (`prov_guard`: 10 daq / 20 xato → 30 daq) → 403 `rate_limited`;
  2. token hech bir tenant'ga mos emas → 404 `bad_token`;
  3. IP tenant'ning `allowed_networks` ida emas → 403 `network_denied`;
  4. fayl nomi: noma'lum → 404 `not_found`; Grandstream `cfg<mac>` (xml'siz) → 404 `legacy_binary`;
     umumiy `y0000000000xx.cfg` → 200 (SIRSIZ);
  5. MAC ro'yxatda yo'q → 404 `unknown_mac` + `discovered_devices`; bor → 200 (sirli config), apparat ko'rinishi yangilanadi.

`bad_token`/`network_denied`/`unknown_mac` — xato hisobiga kiradi (`not_found`/`legacy_binary` — kirmaydi: apparatlar
firmware'ga qarab bir nechta nomni ketma-ket so'raydi). Har so'rov `provision_requests` ga (token `***`, sir yo'q).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lookups import get_tenant_code
from app.db.models import Device, DiscoveredDevice, Extension, ProvisionRequest, SystemSettings
from app.services import devices as svc
from app.services import prov_catalog as catalog
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.prov_guard import FailureGuard, guard as default_guard
from app.services.prov_render import CommonCtx, content_type, render, render_yealink_common
from app.services.prov_settings import ProvSettings, ip_allowed

COUNTED_REASONS = {"bad_token", "network_denied", "unknown_mac"}
MAX_DISCOVERED = 500
_TEXT_LIMIT = 300


@dataclass(frozen=True)
class ProvResult:
    status: int
    reason: str
    body: bytes = b""
    content_type: str = "text/plain"


@dataclass
class ProvRequest:
    token: str
    filename: str
    ip: str | None
    user_agent: str | None
    host: str | None
    tenant_id: str | None = None
    mac: str | None = None
    vendor: str | None = None
    path_prefix: str = "/prov"  # M5b QR: "/prov/qr"

    @property
    def masked_path(self) -> str:
        return f"{self.path_prefix}/***/{self.filename}"[:_TEXT_LIMIT]


_DENIED = {"rate_limited": 403, "network_denied": 403}


def _fail(reason: str) -> ProvResult:
    return ProvResult(_DENIED.get(reason, 404), reason, b"Not Found" if reason not in _DENIED else b"Forbidden")


async def _tenant_by_token(session: AsyncSession, token: str) -> SystemSettings | None:
    if not ProvSettings(prov_token=token).has_valid_token():
        return None
    return (await session.execute(select(SystemSettings).where(
        SystemSettings.provisioning["prov_token"].astext == token))).scalar_one_or_none()


async def _log(session: AsyncSession, req: ProvRequest, result: ProvResult) -> None:
    session.add(ProvisionRequest(tenant_id=req.tenant_id, ip=req.ip, mac=req.mac, vendor=req.vendor,
                                 path=req.masked_path, status_code=result.status, reason=result.reason,
                                 user_agent=(req.user_agent or "")[:_TEXT_LIMIT] or None))


async def _alert_block(session: AsyncSession, req: ProvRequest, guard: FailureGuard) -> None:
    """Yangi blok → alert: tenant ma'lum bo'lsa — unga, aks holda (noto'g'ri token) barcha tenant'larga."""
    tenant_ids = [req.tenant_id] if req.tenant_id else list(
        (await session.execute(select(SystemSettings.tenant_id))).scalars())
    for tenant_id in tenant_ids:
        text = alert_text(await tenant_language(session, str(tenant_id)), "prov_bruteforce", ip=req.ip,
                          failures=guard.limit, window_min=int(guard.window_s // 60))
        await raise_alert(session, str(tenant_id), "prov_bruteforce", f"prov:{req.ip}", text)


async def _finish(session: AsyncSession, req: ProvRequest, result: ProvResult, guard: FailureGuard) -> ProvResult:
    await _log(session, req, result)
    if result.reason in COUNTED_REASONS and req.ip and guard.record_failure(req.ip):
        await _alert_block(session, req, guard)
    await session.commit()
    return result


async def _remember_discovered(session: AsyncSession, req: ProvRequest, ua: catalog.UaInfo) -> None:
    """Ro'yxatda yo'q MAC → «Topilgan qurilmalar» (vendor/model UA'dan). Jadval cheklangan (`MAX_DISCOVERED`)."""
    existing = await session.get(DiscoveredDevice, (req.tenant_id, req.mac))
    if existing is None and (await session.execute(select(func.count()).select_from(DiscoveredDevice).where(
            DiscoveredDevice.tenant_id == req.tenant_id))).scalar_one() >= MAX_DISCOVERED:
        return
    same_vendor = ua.vendor == req.vendor
    values = {"tenant_id": req.tenant_id, "mac": req.mac, "vendor": req.vendor, "ip": req.ip,
              "model": ua.model if same_vendor else None, "firmware": ua.firmware if same_vendor else None,
              "user_agent": (req.user_agent or "")[:_TEXT_LIMIT] or None}
    stmt = insert(DiscoveredDevice).values(**values)
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["tenant_id", "mac"],
        set_={"requests": DiscoveredDevice.requests + 1, "last_seen_at": func.now(), "ip": stmt.excluded.ip,
              "user_agent": stmt.excluded.user_agent,
              "vendor": func.coalesce(stmt.excluded.vendor, DiscoveredDevice.vendor),
              "model": func.coalesce(stmt.excluded.model, DiscoveredDevice.model),
              "firmware": func.coalesce(stmt.excluded.firmware, DiscoveredDevice.firmware)}))


async def _device(session: AsyncSession, tenant_id: str, mac: str) -> Device | None:
    return (await session.execute(select(Device).where(
        Device.tenant_id == tenant_id, Device.mac == mac, Device.kind == "ip_phone"))).scalar_one_or_none()


async def _serve_device(session: AsyncSession, req: ProvRequest, row: SystemSettings, device: Device,
                        ua: catalog.UaInfo) -> ProvResult:
    ext = await session.get(Extension, device.extension_id)
    tp = await svc.load_tenant_prov(session, row, await get_tenant_code(session, req.tenant_id), req.host)
    keys = (await svc.keys_by_device(session, [str(device.id)]))[str(device.id)]
    password = (await svc.sip_passwords(session, [str(ext.id)])).get(str(ext.id), "")
    ctx = svc.device_ctx(device, ext, keys, tp, password)
    _, body = render(device.vendor, device.model or "", ctx)
    device.config_hash = svc.config_hash(device.vendor, device.model or "", ctx, tp)
    device.provisioned_at = device.last_seen_at = func.now()
    device.last_ip, device.user_agent = req.ip, (req.user_agent or "")[:_TEXT_LIMIT] or None
    if ua.vendor == device.vendor and ua.firmware:
        device.firmware = ua.firmware
    return ProvResult(200, "ok", body, content_type(device.vendor))


async def _serve_file(session: AsyncSession, req: ProvRequest, row: SystemSettings) -> ProvResult:
    cfg = ProvSettings.from_raw(row.provisioning)
    parsed = catalog.parse_filename(req.filename)
    ua = catalog.parse_user_agent(req.user_agent)
    req.mac = parsed.mac or ua.mac
    req.vendor = catalog.guess_vendor(parsed.kind, ua)
    if parsed.kind == "common":
        return ProvResult(200, "ok", render_yealink_common(CommonCtx(cfg.language, cfg.timezone, cfg.ntp_server)))
    if parsed.kind in ("unknown", "legacy_binary"):
        return _fail("not_found" if parsed.kind == "unknown" else "legacy_binary")
    device = await _device(session, req.tenant_id, req.mac)
    if device is None:
        await _remember_discovered(session, req, ua)
        return _fail("unknown_mac")
    req.vendor = device.vendor
    if not device.enabled or device.vendor not in catalog.file_vendors(parsed.kind):
        return _fail("not_found")
    return await _serve_device(session, req, row, device, ua)


async def serve(session: AsyncSession, req: ProvRequest, guard: FailureGuard = default_guard) -> ProvResult:
    if req.ip and guard.is_blocked(req.ip):
        return await _finish(session, req, _fail("rate_limited"), guard)
    row = await _tenant_by_token(session, req.token)
    if row is None:
        return await _finish(session, req, _fail("bad_token"), guard)
    req.tenant_id = str(row.tenant_id)
    if not ip_allowed(req.ip, ProvSettings.from_raw(row.provisioning).allowed_networks):
        return await _finish(session, req, _fail("network_denied"), guard)
    return await _finish(session, req, await _serve_file(session, req, row), guard)
