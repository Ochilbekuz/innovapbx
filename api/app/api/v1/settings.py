"""SIP/tarmoq sozlamalari — m1b-contract.md bo'lim 4 (S32) + m1c-contract.md bo'lim 3 (TLS).

Asterisk'ga yetkazish `app/services/sip_transport.py` da: `apply=true` bo'lsa transport/rtp
fayllari qayta yoziladi va RTP oralig'i darhol (`module reload`) qo'llanadi; transport
maydonlari (TLS port/sertifikat ham) o'zgarsa `restart_required`. `POST /settings/sip/restart`
faol qo'ng'iroq bo'lsa 409 `active_calls`, aks holda fayllarni bazadan qayta yozib Asterisk'ni
haqiqatan qayta ishga tushiradi va yangi transport(lar) yuklanganini tekshiradi.

TLS sertifikat holati bazada SAQLANMAYDI — diskdan o'qiladi (`tls_cert.read_cert_metadata`,
`_tls_out` orqali, GET va ikkala POST javobida BIR XIL)."""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.errors import ApiError
from app.db.models import SystemSettings, User
from app.schemas import (
    DetectedNetworkOut,
    RestartResult,
    SelfSignedCertPayload,
    SipSettingsMutated,
    SipSettingsOut,
    SipTlsOut,
    TlsCertificateOut,
    UpdateSipSettingsItem,
    UpdateSipSettingsPayload,
)
from app.services.audit import record_audit
from app.services.live_status import active_channels_count
from app.services.network_detect import detect_local_ips, detect_public_ip
from app.services.sip_transport import apply_sip_config, current_sip_config, needs_restart, restart_and_verify
from app.services.tls_cert import (
    BadCertificateError,
    CertMetadata,
    generate_self_signed,
    read_cert_metadata,
    validate_certificate,
    write_certificate,
)
from app.services.tls_cert import extract_metadata as extract_cert_metadata

router = APIRouter(prefix="/settings", tags=["settings"])

async def get_settings_row(session: AsyncSession, tenant_id: str) -> SystemSettings:
    row = await session.get(SystemSettings, tenant_id)
    if row is None:
        raise ApiError(404, "not_found", "Sozlamalar topilmadi")
    return row


def _settings_out(row: SystemSettings) -> SipSettingsOut:
    # asyncpg CIDR[] ustunini `ipaddress.IPv4Network`/`IPv6Network` obyektlari
    # sifatida qaytaradi, `str` emas — schema `list[str]` kutadi (GET
    # /settings/sip jonli muhitda 500 bergan regressiya, 2026-10-28).
    local_nets = [str(net) for net in row.local_nets]
    return SipSettingsOut(
        external_ip=str(row.external_ip) if row.external_ip else None, external_host=row.external_host, local_nets=local_nets,
        sip_udp_port=row.sip_udp_port, sip_tls_port=row.sip_tls_port, rtp_start=row.rtp_start,
        rtp_end=row.rtp_end, codecs=list(row.codecs),
        detected=DetectedNetworkOut(public_ip=detect_public_ip(), local_ips=detect_local_ips()),
        restart_required=row.restart_required, updated_at=row.updated_at,
    )


def _validate_cidr_list(values: list[str]) -> None:
    for value in values:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ApiError(422, "bad_cidr", f"Noto'g'ri tarmoq: {value}", field="local_nets") from exc


def _validate_port(value: int, field: str) -> None:
    if not (1 <= value <= 65535):
        raise ApiError(422, "bad_port", "Port 1-65535 oralig'ida bo'lishi kerak", field=field)


def _validate_rtp_range(start: int, end: int) -> None:
    if end - start < 100:
        raise ApiError(422, "rtp_range", "RTP oralig'i kamida 100 port bo'lishi kerak", field="rtp_end")


def _validate_no_port_collision(udp: int, tls: int | None, rtp_start: int, rtp_end: int) -> None:
    for name, port in (("sip_udp_port", udp), ("sip_tls_port", tls)):
        if port is not None and rtp_start <= port <= rtp_end:
            raise ApiError(422, "rtp_range", f"{name} RTP oralig'i bilan to'qnashadi", field=name)


# Bodyda aniq `null` — tozalash (ixtiyoriy maydonlar); berilmagan maydon — o'zgarmaydi.
_NULLABLE = frozenset({"external_ip", "external_host", "sip_tls_port"})


def _changes(item: UpdateSipSettingsItem) -> dict:
    return {f: getattr(item, f) for f in item.model_fields_set
            if getattr(item, f) is not None or f in _NULLABLE}


def _validate_ip(value: str | None) -> None:
    if value is None:
        return
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ApiError(422, "bad_ip", f"Noto'g'ri IP manzil: {value}", field="external_ip") from exc


def _validate_sip_update(changes: dict, row: SystemSettings) -> None:
    def merged(field: str):
        return changes[field] if field in changes else getattr(row, field)

    _validate_ip(changes.get("external_ip"))
    if "local_nets" in changes:
        _validate_cidr_list(changes["local_nets"])
    udp, tls = merged("sip_udp_port"), merged("sip_tls_port")
    rtp_start, rtp_end = merged("rtp_start"), merged("rtp_end")
    _validate_port(udp, "sip_udp_port")
    if tls is not None:
        _validate_port(tls, "sip_tls_port")
    _validate_port(rtp_start, "rtp_start")
    _validate_port(rtp_end, "rtp_end")
    _validate_rtp_range(rtp_start, rtp_end)
    _validate_no_port_collision(udp, tls, rtp_start, rtp_end)


async def _push_or_502(coro, code: str, what: str) -> None:
    try:
        await coro
    except Exception as exc:  # noqa: BLE001 — aniq xabar bilan 502 (moh_classes.py bilan bir xil qolip)
        raise ApiError(502, code, f"{what}: {exc}"[:500]) from exc


@router.get("/sip", response_model=SipSettingsOut)
async def get_sip_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> SipSettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    return _settings_out(row)


@router.patch("/sip", response_model=SipSettingsMutated)
async def update_sip_settings(
    payload: UpdateSipSettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> SipSettingsMutated:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    diff = _changes(payload.item)
    _validate_sip_update(diff, row)

    before = current_sip_config(row)
    for field, value in diff.items():
        setattr(row, field, value)
    await session.flush()
    after = current_sip_config(row)
    row.restart_required = row.restart_required or needs_restart(before, after)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="update",
                        entity="sip_settings", entity_id=tenant_id, diff=diff)
    await session.commit()
    if payload.apply:
        await _push_or_502(apply_sip_config(ami, after, reload_rtp=True), "sip_apply_failed",
                           "SIP/RTP sozlamalari Asterisk'ga yetkazilmadi")
    status = "restart_required" if row.restart_required else "applied"
    message = None if payload.apply else "apply=false — faqat saqlandi, qo'llanmadi"
    return SipSettingsMutated(item=_settings_out(row), apply={"status": status, "revision": None, "message": message})


def _cert_out(meta: CertMetadata) -> TlsCertificateOut:
    return TlsCertificateOut(subject=meta.subject, issuer=meta.issuer, not_after=meta.not_after,
                             self_signed=meta.self_signed, fingerprint_sha256=meta.fingerprint_sha256)


def _tls_out(row: SystemSettings) -> SipTlsOut:
    """Sertifikat holati bazada EMAS — har doim diskdan (`read_cert_metadata`) —
    GET va ikkala POST javobi BIR XIL joydan o'qiydi (yagona haqiqat manbai)."""
    meta = read_cert_metadata()
    return SipTlsOut(enabled=row.sip_tls_port is not None and meta is not None,
                     port=row.sip_tls_port, certificate=_cert_out(meta) if meta else None,
                     restart_required=row.restart_required)


def _install_certificate(cert_pem: bytes, key_pem: bytes, chain_pem: bytes | None) -> CertMetadata:
    try:
        cert = validate_certificate(cert_pem, key_pem, chain_pem)
    except BadCertificateError as exc:
        raise ApiError(422, "bad_certificate", "Sertifikat yoki kalit yaroqsiz",
                        details={"reason": exc.reason}) from exc
    write_certificate(cert_pem, key_pem, chain_pem)
    return extract_cert_metadata(cert)


@router.get("/sip/tls", response_model=SipTlsOut)
async def get_sip_tls(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> SipTlsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    return _tls_out(row)


@router.post("/sip/tls/certificate", response_model=SipTlsOut)
async def upload_sip_tls_certificate(
    cert: UploadFile = File(...), key: UploadFile = File(...), chain: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> SipTlsOut:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    chain_pem = await chain.read() if chain is not None else None
    meta = _install_certificate(await cert.read(), await key.read(), chain_pem)

    row.restart_required = True
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="update",
                        entity="sip_tls_certificate", entity_id=tenant_id,
                        diff={"subject": meta.subject, "fingerprint_sha256": meta.fingerprint_sha256})
    await session.commit()
    return _tls_out(row)


@router.post("/sip/tls/self-signed", response_model=SipTlsOut)
async def create_self_signed_sip_tls_certificate(
    payload: SelfSignedCertPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> SipTlsOut:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    cert_pem, key_pem = generate_self_signed(payload.common_name)
    write_certificate(cert_pem, key_pem)

    row.restart_required = True
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="create",
                        entity="sip_tls_certificate", entity_id=tenant_id,
                        diff={"common_name": payload.common_name, "self_signed": True})
    await session.commit()
    return _tls_out(row)


@router.post("/sip/restart", response_model=RestartResult)
async def restart_sip(
    force: bool = False, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> RestartResult:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)

    count = await active_channels_count(ami)
    if count and not force:
        raise ApiError(409, "active_calls", "Faol chaqiruvlar mavjud", details={"count": count})

    await _push_or_502(restart_and_verify(ami, current_sip_config(row)), "restart_failed",
                       "Asterisk qayta ishga tushirilmadi")
    row.restart_required = False
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="restart",
                        entity="sip_settings", entity_id=tenant_id, diff={"forced": force})
    await session.commit()
    return RestartResult(ok=True, message=None)
