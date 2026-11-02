"""M5b §2 — mobil softfonni (Linphone) QR orqali sozlash.

QR'da parol YO'Q — faqat bir martalik havola `<public_base_url>/prov/qr/<token>/linphone.xml`.
Token: `secrets.token_urlsafe(32)`; bazada faqat SHA-256 xeshi; TTL 15 daq; birinchi muvaffaqiyatli
olishdan 60 s o'tib yaroqsiz (Linphone bir necha marta qayta so'rashi mumkin); ichki raqamga bitta token
(yangisi eskisini almashtiradi — PK `extension_id`).
`GET` — M4a `/prov` himoyasi (`prov_guard` rate-limit, `provision_requests` jurnali, token `***`).
`allowed_networks` QO'LLANMAYDI: telefon odatda mobil internetda (havola o'zi — 15 daq'lik sir)."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.lookups import get_tenant_code
from app.db.models import Extension, QrProvisionToken, SystemSettings
from app.services import devices as svc
from app.services.audit import record_audit
from app.services.prov_guard import FailureGuard, guard as default_guard
from app.services.prov_serve import ProvRequest, ProvResult, _fail, _finish

TOKEN_TTL = timedelta(minutes=15)
REUSE_GRACE = timedelta(seconds=60)
REG_EXPIRES = 600
QR_FILENAME = "linphone.xml"
_TOKEN_MIN_LEN = 40  # token_urlsafe(32) → 43 belgi


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def public_base(row: SystemSettings) -> str:
    base = str((row.integrations or {}).get("public_base_url") or "").rstrip("/")
    if not base:
        raise ApiError(409, "public_host_not_configured",
                       "Tashqi manzil sozlanmagan: Sozlamalar → Integratsiyalar → «Tashqi manzil»")
    return base


@dataclass(frozen=True)
class QrIssued:
    url: str
    expires_at: datetime
    transport: str


async def issue_token(session: AsyncSession, ext: Extension, *, user_id: str,
                      now: datetime | None = None) -> QrIssued:
    if ext.webrtc:
        raise ApiError(409, "extension_webrtc_only", "Bu ichki raqam faqat brauzer (WebRTC) uchun")
    row = await session.get(SystemSettings, ext.tenant_id)
    if row is None:
        raise ApiError(404, "not_found", "Sozlamalar topilmadi")
    base = public_base(row)
    token = secrets.token_urlsafe(32)
    expires_at = (now or datetime.now(timezone.utc)) + TOKEN_TTL
    values = {"extension_id": str(ext.id), "tenant_id": str(ext.tenant_id), "token_hash": token_hash(token),
              "expires_at": expires_at, "first_used_at": None, "created_by": user_id}
    stmt = insert(QrProvisionToken).values(**values)
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["extension_id"],
        set_={k: stmt.excluded[k] for k in ("token_hash", "expires_at", "first_used_at", "created_by")}))
    await record_audit(session, tenant_id=str(ext.tenant_id), user_id=user_id, action="extension.qr_provisioning",
                       entity="extension", entity_id=str(ext.id), diff={"qr_provisioning": "issued", "expires_at": expires_at.isoformat()})
    await session.commit()
    transport = svc.ProvSettings.from_raw(row.provisioning).sip_transport
    return QrIssued(url=f"{base}/prov/qr/{token}/{QR_FILENAME}", expires_at=expires_at, transport=transport)


def token_usable(row: QrProvisionToken, now: datetime) -> bool:
    if row.expires_at <= now:
        return False
    return row.first_used_at is None or now - row.first_used_at <= REUSE_GRACE


@dataclass(frozen=True)
class LinphoneCtx:
    username: str
    password: str
    host: str
    port: int
    transport: str
    display_name: str


def render_linphone(ctx: LinphoneCtx) -> bytes:
    def e(value: object) -> str:
        return escape(str(value))

    identity = f"sip:{ctx.username}@{ctx.host}"
    proxy = f"<sip:{ctx.host}:{ctx.port};transport={ctx.transport}>"
    display = f'"{ctx.display_name}" ' if ctx.display_name else ""
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config xmlns="http://www.linphone.org/xsds/lpconfig.xsd">\n'
        '  <section name="proxy_0" overwrite="true">\n'
        f'    <entry name="reg_proxy" overwrite="true">{e(proxy)}</entry>\n'
        f'    <entry name="reg_route" overwrite="true">{e(proxy)}</entry>\n'
        f'    <entry name="reg_identity" overwrite="true">{e(display + "<" + identity + ">")}</entry>\n'
        f'    <entry name="reg_expires" overwrite="true">{REG_EXPIRES}</entry>\n'
        '    <entry name="reg_sendregister" overwrite="true">1</entry>\n'
        '    <entry name="publish" overwrite="true">0</entry>\n'
        '  </section>\n'
        '  <section name="auth_info_0" overwrite="true">\n'
        f'    <entry name="username" overwrite="true">{e(ctx.username)}</entry>\n'
        f'    <entry name="userid" overwrite="true">{e(ctx.username)}</entry>\n'
        f'    <entry name="passwd" overwrite="true">{e(ctx.password)}</entry>\n'
        f'    <entry name="domain" overwrite="true">{e(ctx.host)}</entry>\n'
        '  </section>\n'
        '</config>\n'
    )
    return body.encode()


async def _lookup(session: AsyncSession, token: str) -> QrProvisionToken | None:
    if len(token) < _TOKEN_MIN_LEN:
        return None
    return (await session.execute(select(QrProvisionToken).where(
        QrProvisionToken.token_hash == token_hash(token)).with_for_update())).scalar_one_or_none()


async def _render_for(session: AsyncSession, qr: QrProvisionToken, request_host: str | None) -> bytes | None:
    ext = await session.get(Extension, qr.extension_id)
    row = await session.get(SystemSettings, qr.tenant_id)
    if ext is None or row is None or ext.webrtc:
        return None
    tenant_code = await get_tenant_code(session, qr.tenant_id)
    tp = await svc.load_tenant_prov(session, row, tenant_code, request_host)
    password = (await svc.sip_passwords(session, [str(ext.id)])).get(str(ext.id), "")
    return render_linphone(LinphoneCtx(
        username=svc.endpoint_id(tenant_code, ext), password=password, host=tp.server_host,
        port=tp.server_port, transport=tp.cfg.sip_transport, display_name=ext.name or ext.number))


async def serve_qr(session: AsyncSession, req: ProvRequest, guard: FailureGuard = default_guard,
                   now: datetime | None = None) -> ProvResult:
    if req.ip and guard.is_blocked(req.ip):
        return await _finish(session, req, _fail("rate_limited"), guard)
    now = now or datetime.now(timezone.utc)
    qr = await _lookup(session, req.token)
    if qr is None or not token_usable(qr, now):
        return await _finish(session, req, _fail("bad_token"), guard)
    req.tenant_id = str(qr.tenant_id)
    body = await _render_for(session, qr, req.host)
    if body is None:
        return await _finish(session, req, _fail("not_found"), guard)
    if qr.first_used_at is None:
        qr.first_used_at = now
        await record_audit(session, tenant_id=str(qr.tenant_id), user_id=None, action="extension.qr_used",
                           entity="extension", entity_id=str(qr.extension_id), diff={"qr_provisioning": "used", "ip": req.ip})
    return await _finish(session, req, ProvResult(200, "ok", body, "application/xml"), guard)


async def purge_expired(session: AsyncSession, now: datetime | None = None) -> int:
    cutoff = now or datetime.now(timezone.utc)
    result = await session.execute(delete(QrProvisionToken).where(QrProvisionToken.expires_at < cutoff))
    return result.rowcount or 0
