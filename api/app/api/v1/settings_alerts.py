"""M2c §4 — `GET/PATCH /settings/alerts`, `POST /settings/alerts/test`.
`system_settings.telegram` JSONB; bot token — mavjud `/settings/notify`
(`NotifySettings.telegram_token_enc`, `vm_notify.load_config`), bu yerda
QAYTA SO'RALMAYDI (m2c-contract.md §4)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import AlertLog, SystemSettings, User
from app.schemas_security import AlertSettingsOut, AlertTestResult, UpdateAlertSettingsPayload
from app.services import vm_notify
from app.services.alerts import alert_text, load_alert_config, tenant_language
from app.services.audit import record_audit
from app.api.v1.settings import get_settings_row
from app.services.security_config import check_chat_ids, check_int, parse_alerts

router = APIRouter(prefix="/settings/alerts", tags=["settings"])


async def _settings_out(session: AsyncSession, row: SystemSettings) -> AlertSettingsOut:
    cfg = parse_alerts(row.telegram)
    notify_cfg = await vm_notify.load_config(session, str(row.tenant_id))
    return AlertSettingsOut(chat_ids=list(cfg.chat_ids), dedup_s=cfg.dedup_s, events=cfg.events,
                            has_telegram_token=bool(notify_cfg.telegram_token), updated_at=row.updated_at)


@router.get("", response_model=AlertSettingsOut)
async def get_alert_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> AlertSettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    return await _settings_out(session, row)


def _unknown_event(events: dict) -> str | None:
    bad = next((k for k in events if k not in parse_alerts(None).events), None)
    return f"Noma'lum hodisa turi: {bad}" if bad is not None else None


# Maydon -> tekshiruvchi (xato matni yoki None). Birinchi xato 422 bo'ladi.
_ALERT_CHECKS = {
    "chat_ids": check_chat_ids,
    "dedup_s": lambda v: check_int("telegram.dedup_s", v),
    "events": _unknown_event,
}


def _validate_alert_changes(changes: dict) -> None:
    for field_name, check in _ALERT_CHECKS.items():
        err = check(changes[field_name]) if field_name in changes else None
        if err:
            raise ApiError(422, "bad_value", err, field=field_name)


@router.patch("", response_model=AlertSettingsOut)
async def update_alert_settings(
    payload: UpdateAlertSettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> AlertSettingsOut:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    check_not_stale(row.updated_at, payload.updated_at)

    changes = {f: getattr(payload, f) for f in payload.model_fields_set if f != "updated_at"}
    _validate_alert_changes(changes)
    if "events" in changes:
        # Qisman PATCH — faqat berilgan kalitlar o'zgaradi, qolganlari saqlanadi.
        changes["events"] = {**(row.telegram.get("events") or {}), **changes["events"]}

    if changes:
        row.telegram = {**row.telegram, **changes}
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="settings_alerts.update",
                        entity="alert_settings", entity_id=tenant_id, diff=changes)
    await session.commit()
    await session.refresh(row)
    return await _settings_out(session, row)


@router.post("/test", response_model=AlertTestResult)
async def test_alert_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> AlertTestResult:
    tenant_id = str(user.tenant_id)
    cfg = await load_alert_config(session, tenant_id)
    notify_cfg = await vm_notify.load_config(session, tenant_id)
    if not notify_cfg.telegram_token:
        raise ApiError(422, "no_token", "Telegram bot token sozlanmagan (/settings/notify)")
    if not cfg.chat_ids:
        raise ApiError(422, "no_chat", "Hech qanday Telegram chat ID sozlanmagan")

    text = alert_text(await tenant_language(session, tenant_id), "test")
    sent, error = 0, None
    for chat_id in cfg.chat_ids:
        try:
            await vm_notify.send_telegram(notify_cfg, chat_id, text, None)
            sent += 1
        except vm_notify.NotifyError as exc:
            error = str(exc)[:500]

    status = "sent" if sent and not error else "failed"
    session.add(AlertLog(tenant_id=tenant_id, kind="test", key="", body=text, status=status, error=error,
                        sent_at=datetime.now(timezone.utc) if status == "sent" else None))
    await session.commit()
    if error:
        raise ApiError(502, "notify_failed", f"Telegram xabari yuborilmadi: {error}"[:500],
                       details={"reason": error})
    return AlertTestResult(sent=sent)
