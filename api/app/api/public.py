"""M3b §4 — ochiq API `/api/public/v1/*` (`Authorization: Bearer ipk_...`).

Xatolar: kalit yo'q/bekor/muddati o'tgan → 401 `invalid_api_key`; scope yo'q → 403 `insufficient_scope`;
kalitga 120 so'rov/daq → 429 `rate_limited`. `last_used_at` — ko'pi bilan daqiqada bir yoziladi.
Yozuv: kalit (`recordings:read`) YOKI imzoli havola (`?exp=&sig=`, §1) — eskirgan/buzilgan → 403.
"""
from __future__ import annotations

import base64
import binascii
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session
from app.api.v1.calls import _parse_dt
from app.api.v1.extensions import _bulk_extension_out
from app.api.v1.recordings import audio_response, not_found
from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import ApiKey, ApiOriginateRequest, Cdr, Extension, Tenant
from app.schemas import CallOut
from app.schemas_integrations import OriginateAccepted, OriginatePayload, PublicExtensionOut
from app.services import api_keys, originate, recordings
from app.services.audit import record_audit
from app.services.cdr_grouping import call_out_from_group, calls_from_rows, group_by_linkedid, trunk_names
from app.services.number_normalize import normalize_number
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/api/public/v1", tags=["public"])
_limiter = SlidingWindowLimiter()
MAX_LIMIT = 200


@dataclass(frozen=True)
class KeyContext:
    key_id: str
    prefix: str
    tenant_id: str
    tenant_code: str


# ------------------------------------------------------------ autentifikatsiya
def _invalid() -> ApiError:
    return ApiError(401, "invalid_api_key", "API kalit yaroqsiz, bekor qilingan yoki muddati o'tgan")


def bearer_key(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


async def _usable_key(session: AsyncSession, plaintext: str | None, now: datetime) -> ApiKey:
    prefix = api_keys.parse_prefix(plaintext or "")
    row = None
    if prefix is not None:
        row = (await session.execute(select(ApiKey).where(ApiKey.prefix == prefix))).scalar_one_or_none()
    if row is None or not api_keys.key_matches(plaintext, row.key_hash) or not api_keys.key_usable(row, now):
        raise _invalid()
    return row


async def authenticate(session: AsyncSession, plaintext: str | None, scope: str) -> KeyContext:
    now = datetime.now(timezone.utc)
    row = await _usable_key(session, plaintext, now)
    if not _limiter.allow(f"apikey:{row.id}", limit=settings.api_key_rate_limit_per_min, window_s=60):
        raise ApiError(429, "rate_limited", "Juda ko'p so'rov — birozdan keyin qayta urining")
    if not api_keys.has_scope(list(row.scopes or []), scope):
        raise ApiError(403, "insufficient_scope", f"Kalitda `{scope}` ruxsati yo'q", details={"required": scope})
    if api_keys.should_touch(row.last_used_at, now):
        row.last_used_at = now
        await session.commit()
    code = (await session.execute(select(Tenant.code).where(Tenant.id == row.tenant_id))).scalar_one()
    return KeyContext(key_id=str(row.id), prefix=row.prefix, tenant_id=str(row.tenant_id), tenant_code=code)


def require_scope(scope: str):
    async def dependency(request: Request, session: AsyncSession = Depends(get_session)) -> KeyContext:
        return await authenticate(session, bearer_key(request), scope)
    return dependency


# ------------------------------------------------------------ qo'ng'iroqlar
def encode_cursor(started_at: datetime, uniqueid: str) -> str:
    return base64.urlsafe_b64encode(f"{started_at.isoformat()}|{uniqueid}".encode()).decode().rstrip("=")


def decode_cursor(raw: str) -> tuple[datetime, str]:
    try:
        text = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        started, uniqueid = text.split("|", 1)
        return datetime.fromisoformat(started), uniqueid
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ApiError(422, "bad_cursor", "Kursor yaroqsiz", field="cursor") from exc


def _call_keys_query(code: str, *, from_: str | None, to: str | None, number: str | None, cursor: str | None,
                     limit: int):
    """Mantiqiy qo'ng'iroq kaliti (`uniqueid`, eng erta `calldate`) — kursor shu juftlikda (barqaror tartib)."""
    rows = select(Cdr.uniqueid.label("uid"), func.min(Cdr.calldate).label("started")).where(Cdr.accountcode == code)
    if from_:
        rows = rows.where(Cdr.calldate >= _parse_dt(from_))
    if to:
        rows = rows.where(Cdr.calldate <= _parse_dt(to))
    if number:
        digits = normalize_number(number)
        rows = rows.where(or_(Cdr.src == digits, Cdr.dst == digits, Cdr.userfield == digits))
    keys = rows.group_by(Cdr.uniqueid).subquery()
    stmt = select(keys.c.uid, keys.c.started)
    if cursor:
        started, uid = decode_cursor(cursor)
        stmt = stmt.where(tuple_(keys.c.started, keys.c.uid) < tuple_(started, uid))
    return stmt.order_by(keys.c.started.desc(), keys.c.uid.desc()).limit(limit)


async def _calls_for_keys(session: AsyncSession, key: KeyContext, uids: list[str]) -> list[CallOut]:
    rows = (await session.execute(select(Cdr).where(Cdr.accountcode == key.tenant_code, Cdr.uniqueid.in_(uids))
                                  .order_by(Cdr.calldate.desc()))).scalars().all()
    by_uid = {c.uniqueid: c for c in calls_from_rows(list(rows), await trunk_names(session, key.tenant_id))}
    return [by_uid[u] for u in uids if u in by_uid]


@router.get("/calls")
async def public_calls(
    from_: str | None = Query(default=None, alias="from"), to: str | None = None, number: str | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT), cursor: str | None = None,
    session: AsyncSession = Depends(get_session), key: KeyContext = Depends(require_scope("calls:read")),
) -> dict:
    keys = (await session.execute(_call_keys_query(key.tenant_code, from_=from_, to=to, number=number,
                                                   cursor=cursor, limit=limit))).all()
    calls = await _calls_for_keys(session, key, [k.uid for k in keys])
    await recordings.attach_recordings(session, key.tenant_id, calls)
    next_cursor = encode_cursor(keys[-1].started, keys[-1].uid) if len(keys) == limit else None
    return {"items": calls, "next_cursor": next_cursor}


@router.get("/calls/{linkedid}")
async def public_call(linkedid: str, session: AsyncSession = Depends(get_session),
                      key: KeyContext = Depends(require_scope("calls:read"))) -> dict:
    rows = (await session.execute(select(Cdr).where(
        Cdr.accountcode == key.tenant_code, or_(Cdr.linkedid == linkedid, Cdr.uniqueid == linkedid),
    ).order_by(Cdr.calldate.desc()))).scalars().all()
    if not rows:
        raise ApiError(404, "not_found", "Qo'ng'iroq topilmadi")
    call = call_out_from_group(group_by_linkedid(list(rows))[0], await trunk_names(session, key.tenant_id))
    call.linkedid = linkedid
    await recordings.attach_recordings(session, key.tenant_id, [call])
    return {"item": call}


# ------------------------------------------------------------ yozuv
def link_is_valid(recording_id: str, exp: int, sig: str) -> bool:
    return recordings.verify_link(recording_id, exp, sig, now_unix=int(time.time()),
                                  secret_key=settings.require_secret_key())


@router.get("/recordings/{recording_id}")
async def public_recording(request: Request, recording_id: str, exp: int | None = None, sig: str | None = None,
                           session: AsyncSession = Depends(get_session)) -> FileResponse:
    if exp is not None or sig is not None:
        if exp is None or not sig or not link_is_valid(recording_id, exp, sig):
            raise ApiError(403, "invalid_signature", "Havola eskirgan yoki buzilgan")
        tenant_id = await _recording_tenant(session, recording_id)
    else:
        tenant_id = (await authenticate(session, bearer_key(request), "recordings:read")).tenant_id
    rec = await recordings.get_active(session, tenant_id, recording_id) if tenant_id else None
    if rec is None:
        raise not_found()
    return audio_response(rec)


async def _recording_tenant(session: AsyncSession, recording_id: str) -> str | None:
    """Imzo tekshirilgandan KEYIN — imzo `id`ga bog'langan, shuning uchun tenant yozuvdan olinadi."""
    from app.db.models import CallRecording

    try:
        rid = str(uuid.UUID(recording_id))
    except ValueError:
        return None
    rec = await session.get(CallRecording, rid)
    return str(rec.tenant_id) if rec is not None else None


# ------------------------------------------------------------ ichki raqamlar
@router.get("/extensions")
async def public_extensions(session: AsyncSession = Depends(get_session), ami=Depends(get_ami),
                            key: KeyContext = Depends(require_scope("extensions:read"))) -> dict:
    items = (await session.execute(select(Extension).where(Extension.tenant_id == key.tenant_id)
                                   .order_by(Extension.number))).scalars().all()
    out = await _bulk_extension_out(ami, list(items))
    return {"items": [PublicExtensionOut(number=e.number, name=e.name, enabled=e.enabled, status=e.status)
                      for e in out]}


# ------------------------------------------------------------ originate
def _validated(payload: OriginatePayload) -> tuple[str, str | None]:
    try:
        to = originate.validate_to(payload.to)
    except originate.InvalidNumber as exc:
        raise ApiError(422, "invalid_number", "`to` faqat [0-9+*#], ko'pi bilan 32 belgi", field="to") from exc
    try:
        external_id = originate.validate_external_id(payload.external_id)
    except originate.InvalidExternalId as exc:
        raise ApiError(422, "invalid_external_id", "`external_id`: [A-Za-z0-9_.:-], ≤ 64", field="external_id") from exc
    return to, external_id


async def _enabled_extension(session: AsyncSession, tenant_id: str, number: str) -> Extension:
    ext = (await session.execute(select(Extension).where(
        Extension.tenant_id == tenant_id, Extension.number == number))).scalar_one_or_none()
    if ext is None or not ext.enabled:
        raise ApiError(422, "unknown_extension", "Ichki raqam topilmadi yoki o'chirilgan", field="extension")
    return ext


@dataclass(frozen=True)
class OriginateOrder:
    """Tekshirilgan buyurtma: `request_id` = AMI `ChannelId` = qo'ng'iroq `linkedid` (chaqiruvchi beradi —
    CRM bog'lanishi originate'dan OLDIN yozilsin)."""
    tenant_id: str
    tenant_code: str
    extension: str
    to: str
    request_id: str
    external_id: str | None = None
    api_key_id: str | None = None


async def place_originate(session: AsyncSession, ami, order: OriginateOrder, *, action: str, audit: dict) -> None:
    """So'rov qatori + audit → commit → AMI Originate. AMI xatosi → 502 `originate_failed`."""
    session.add(ApiOriginateRequest(id=order.request_id, tenant_id=order.tenant_id, api_key_id=order.api_key_id,
                                    extension=order.extension, to_number=order.to, external_id=order.external_id))
    await record_audit(session, tenant_id=order.tenant_id, user_id=None, action=action, entity="call",
                       entity_id=order.request_id, diff={"extension": order.extension, "to": order.to,
                                                         "external_id": order.external_id, **audit})
    await session.commit()
    fields = originate.originate_fields(order.tenant_code, order.extension, order.to, request_id=order.request_id,
                                        external_id=order.external_id)
    try:
        resp = await ami.action("Originate", **fields)
    except Exception as exc:  # noqa: BLE001 — AMI uzilgan
        raise ApiError(502, "originate_failed", f"Asterisk bilan aloqa yo'q: {type(exc).__name__}") from exc
    if (resp or {}).get("Response") != "Success":
        raise ApiError(502, "originate_failed", str((resp or {}).get("Message") or "Originate rad etildi")[:300])


@router.post("/calls/originate", status_code=202, response_model=OriginateAccepted)
async def public_originate(payload: OriginatePayload, session: AsyncSession = Depends(get_session),
                           ami=Depends(get_ami), key: KeyContext = Depends(require_scope("calls:originate"))):
    to, external_id = _validated(payload)
    ext = await _enabled_extension(session, key.tenant_id, payload.extension)
    order = OriginateOrder(tenant_id=key.tenant_id, tenant_code=key.tenant_code, extension=ext.number, to=to,
                           request_id=str(uuid.uuid4()), external_id=external_id, api_key_id=key.key_id)
    await place_originate(session, ami, order, action="api.originate", audit={"api_key": key.prefix})
    return JSONResponse(status_code=202, content={"request_id": order.request_id})
