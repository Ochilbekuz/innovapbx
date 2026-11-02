"""Bildirishnoma sozlamalari (SMTP + Telegram bot) — m1c-contract.md §2.
`GET/PATCH /settings/notify` (javob — `NotifySettings` obyekti, ikkalasida
bir xil), `POST /settings/notify/test` -> 200 yoki 502 `notify_failed`.

SMTP parol va Telegram token `crypto.encrypt_secret` bilan shifrlanadi va
hech qachon qaytarilmaydi (`has_*`). PATCH'da berilmagan maydon o'zgarmaydi;
parol/token uchun `""` — o'chirish. Audit'da parol/token `***`
(`audit._SECRET_MARKERS`). Asterisk'ga hech narsa yetkazilmaydi — fon vazifa
(`vm_notify`) har skanda sozlamani bazadan o'qiydi."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import NotifySettings, User
from app.schemas_voicemail import NotifySettingsOut, NotifyTestPayload, NotifyTestResult, UpdateNotifySettingsPayload
from app.services import vm_notify
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret

router = APIRouter(prefix="/settings/notify", tags=["settings"])

# `null` — tozalash (faqat bo'sh bo'la oladigan ustunlar); qolganlari uchun e'tiborsiz.
_NULLABLE_FIELDS = ("smtp_host", "smtp_user", "from_email")
_REQUIRED_FIELDS = ("smtp_port", "smtp_tls", "telegram_api_base")
_SECRET_FIELDS = {"smtp_password": "smtp_password_enc", "telegram_token": "telegram_token_enc"}
_DEFAULTS = SimpleNamespace(smtp_host=None, smtp_port=587, smtp_tls="starttls", smtp_user=None, smtp_password_enc=None,
                            from_email=None, telegram_token_enc=None, telegram_api_base="https://api.telegram.org")


def _plain_changes(payload: UpdateNotifySettingsPayload) -> dict:
    given = payload.model_fields_set
    changes = {f: getattr(payload, f) for f in _NULLABLE_FIELDS if f in given}
    changes |= {f: getattr(payload, f) for f in _REQUIRED_FIELDS if getattr(payload, f) is not None}
    return changes


def _out(row: NotifySettings | None) -> NotifySettingsOut:
    src = row or _DEFAULTS
    return NotifySettingsOut(
        smtp_host=src.smtp_host, smtp_port=src.smtp_port, smtp_tls=src.smtp_tls, smtp_user=src.smtp_user,
        has_smtp_password=bool(src.smtp_password_enc), from_email=src.from_email,
        has_telegram_token=bool(src.telegram_token_enc), telegram_api_base=src.telegram_api_base,
        updated_at=row.updated_at if row else None,
    )


@router.get("", response_model=NotifySettingsOut)
async def get_notify_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> NotifySettingsOut:
    return _out(await session.get(NotifySettings, str(user.tenant_id)))


async def _apply_secrets(session: AsyncSession, row: NotifySettings, payload: UpdateNotifySettingsPayload,
                         diff: dict) -> None:
    for field, column in _SECRET_FIELDS.items():
        value = getattr(payload, field)
        if value is None:
            continue
        setattr(row, column, await encrypt_secret(session, value) if value else None)
        diff[field] = value  # record_audit -> "***"


@router.patch("", response_model=NotifySettingsOut)
async def update_notify_settings(
    payload: UpdateNotifySettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> NotifySettingsOut:
    tenant_id = str(user.tenant_id)
    row = await session.get(NotifySettings, tenant_id)
    if row is None:
        row = NotifySettings(tenant_id=tenant_id, smtp_port=587, smtp_tls="starttls",
                             telegram_api_base="https://api.telegram.org")
        session.add(row)
    elif payload.updated_at is not None:
        check_not_stale(row.updated_at, payload.updated_at)

    diff = _plain_changes(payload)
    for field, value in diff.items():
        setattr(row, field, value)
    await _apply_secrets(session, row, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="notify_settings.update",
                       entity="notify_settings", entity_id=tenant_id, diff=diff)
    await session.commit()
    await session.refresh(row)
    return _out(row)


@router.post("/test", response_model=NotifyTestResult)
async def test_notify(
    payload: NotifyTestPayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> NotifyTestResult:
    cfg = await vm_notify.load_config(session, str(user.tenant_id))
    try:
        await vm_notify.send_test(cfg, payload.channel, payload.to)
    except vm_notify.NotifyError as exc:
        raise ApiError(502, "notify_failed", f"Bildirishnoma yuborilmadi: {exc}"[:500],
                       details={"reason": str(exc)[:500]}) from exc
    return NotifyTestResult(ok=True)
