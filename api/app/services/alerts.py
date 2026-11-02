"""M2c §4 — ogohlantirish navbati. Hodisa joyida FAQAT `raise_alert` chaqiriladi:
u chaqiruvchining tranzaksiyasida `alert_log` qatorini yozadi (commit — chaqiruvchida).
Yuborish — `alert_dispatch` fon vazifasi (`pending` → `sent`/`failed`), shu fayl davomida.

Matnda sir (token, parol) BO'LMASIN — `alert_log.text` admin'ga ko'rinadi."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AlertLog, SystemSettings, Tenant
from app.services import vm_notify
from app.services.security_config import AlertConfig, parse_alerts

log = logging.getLogger("innova.alert_dispatch")

# M2c §4 — matnlar tenant tilida (uz/ru/en). `toll_blocked` ikki xil sabab
# uchun ALOHIDA kalit (`toll_blocked_<reason>`) — `alert_text()` tanlaydi.
# Boshqa fon vazifalari (sip_guard, trunk_monitor — bu sessiyada MENIKI EMAS)
# ham shu funksiyani ishlatadi (`ip_banned`, `trunk_down`, `trunk_up` shu
# sabab allaqachon shu yerda, garchi ularni HECH KIM hali chaqirmasa ham).
_TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "ip_banned": "🚫 SIP hujum: {ip} bloklandi ({failures} urinish / {window_s} s)",
        "toll_blocked_per_hour": "☎️ Toll-fraud: {number} chiquvchi bloklandi (soatiga {limit} limiti)",
        "toll_blocked_international_per_day":
            "☎️ Toll-fraud: {number} chiquvchi bloklandi (kuniga {limit} xalqaro limiti)",
        "concurrent_limit": "⛔ Bir vaqtdagi chiquvchi limit ({limit}) to'ldi: {number}",
        "trunk_down": "⚠️ Trunk «{name}» ishlamayapti: {reason}",
        "trunk_up": "✅ Trunk «{name}» tiklandi",
        "webhook_disabled": "🔌 Integratsiya «{name}» o'chirildi: {reason}",
        "recording_error": "💾 Yozuvlar diski xatosi: {error}",
        "prov_bruteforce": "🔐 Provizioning: {ip} 30 daqiqaga bloklandi ({failures} xato so'rov / {window_min} daq)",
        "backup_failed": "💾 Zaxira xato: {detail}",
        "backup_stale": "💾 Muvaffaqiyatli zaxira {days} kundan beri yo'q",
        "test": "✅ Innova PBX — sinov xabari",
    },
    "ru": {
        "ip_banned": "🚫 SIP-атака: {ip} заблокирован ({failures} попыток / {window_s} с)",
        "toll_blocked_per_hour": "☎️ Toll-fraud: исходящие {number} заблокированы (лимит {limit}/час)",
        "toll_blocked_international_per_day":
            "☎️ Toll-fraud: исходящие {number} заблокированы (лимит {limit} межд. звонков/сутки)",
        "concurrent_limit": "⛔ Достигнут лимит одновременных исходящих ({limit}): {number}",
        "trunk_down": "⚠️ Транк «{name}» не работает: {reason}",
        "trunk_up": "✅ Транк «{name}» восстановлен",
        "webhook_disabled": "🔌 Интеграция «{name}» отключена: {reason}",
        "recording_error": "💾 Ошибка диска записей: {error}",
        "prov_bruteforce": "🔐 Провижининг: {ip} заблокирован на 30 минут ({failures} ошибочных запросов / {window_min} мин)",
        "backup_failed": "💾 Ошибка резервной копии: {detail}",
        "backup_stale": "💾 Нет успешной резервной копии {days} дн.",
        "test": "✅ Innova PBX — тестовое сообщение",
    },
    "en": {
        "ip_banned": "🚫 SIP attack: {ip} banned ({failures} attempts / {window_s} s)",
        "toll_blocked_per_hour": "☎️ Toll-fraud: outbound from {number} blocked (limit {limit}/hour)",
        "toll_blocked_international_per_day":
            "☎️ Toll-fraud: outbound from {number} blocked (limit {limit} intl calls/day)",
        "concurrent_limit": "⛔ Concurrent outbound limit ({limit}) reached: {number}",
        "trunk_down": "⚠️ Trunk «{name}» is down: {reason}",
        "trunk_up": "✅ Trunk «{name}» is back up",
        "webhook_disabled": "🔌 Integration «{name}» disabled: {reason}",
        "recording_error": "💾 Recordings disk error: {error}",
        "prov_bruteforce": "🔐 Provisioning: {ip} blocked for 30 minutes ({failures} failed requests / {window_min} min)",
        "backup_failed": "💾 Backup error: {detail}",
        "backup_stale": "💾 No successful backup for {days} days",
        "test": "✅ Innova PBX — test message",
    },
}


def alert_text(language: str | None, kind: str, **params: object) -> str:
    """Tenant tilida (bo'lmasa `uz`) qisqa ogohlantirish matni. `kind="toll_blocked"`
    uchun `reason` parametri ("per_hour"/"international_per_day") shart."""
    lang = language if language in _TEXTS else "uz"
    key = f"toll_blocked_{params.get('reason', 'per_hour')}" if kind == "toll_blocked" else kind
    template = _TEXTS[lang].get(key) or _TEXTS["uz"][key]
    return template.format(**params)


async def load_alert_config(session: AsyncSession, tenant_id: str) -> AlertConfig:
    row = await session.get(SystemSettings, tenant_id)
    return parse_alerts(row.telegram if row else None)


async def tenant_language(session: AsyncSession, tenant_id: str) -> str:
    """Tizim o'zi (ext/trunk/sip_guard) ko'targan ogohlantirish — foydalanuvchi
    kontekstisiz, shu sabab `User.language`ga tayanib bo'lmaydi — tenant tili."""
    tenant = await session.get(Tenant, tenant_id)
    return tenant.language if tenant else "uz"


async def _is_duplicate(session: AsyncSession, tenant_id: str, kind: str, key: str, dedup_s: int) -> bool:
    if dedup_s <= 0:
        return False
    since = datetime.now(timezone.utc) - timedelta(seconds=dedup_s)
    row = (await session.execute(
        select(AlertLog.id).where(
            AlertLog.tenant_id == tenant_id, AlertLog.kind == kind, AlertLog.key == key,
            AlertLog.status.in_(("pending", "sent")), AlertLog.at >= since,
        ).limit(1)
    )).first()
    return row is not None


def initial_status(cfg: AlertConfig, kind: str, duplicate: bool) -> str:
    """Sof qoida: o'chiq tur → `disabled`; dedup oynasida → `suppressed`; aks holda `pending`."""
    if kind != "test" and not cfg.events.get(kind, False):
        return "disabled"
    return "suppressed" if duplicate else "pending"


async def raise_alert(session: AsyncSession, tenant_id: str, kind: str, key: str, text: str) -> AlertLog:
    cfg = await load_alert_config(session, tenant_id)
    duplicate = await _is_duplicate(session, tenant_id, kind, key, cfg.dedup_s)
    row = AlertLog(tenant_id=tenant_id, kind=kind, key=key, body=text, status=initial_status(cfg, kind, duplicate))
    session.add(row)
    await session.flush()
    return row


# ------------------------------------------------------------ fon vazifa (dispatch)
def _safe_error(exc: Exception, token: str) -> str:
    """Xato matni `alert_log.error`ga (admin ko'radi) — bot token hech qachon ochiq emas."""
    text = str(exc) if isinstance(exc, vm_notify.NotifyError) else f"{type(exc).__name__}: {exc}"
    return text.replace(token, "***")[:500]


async def _send_pending(session: AsyncSession, row: AlertLog) -> None:
    """Bitta `pending` qatorni yuboradi -> `sent`/`failed`. Token yoki chat
    yo'q bo'lsa Telegram'ga umuman murojaat qilinmaydi (m2c-contract.md §4)."""
    cfg = await load_alert_config(session, row.tenant_id)
    notify_cfg = await vm_notify.load_config(session, row.tenant_id)
    if not notify_cfg.telegram_token:
        row.status, row.error = "failed", "no_token"
    elif not cfg.chat_ids:
        row.status, row.error = "failed", "no_chat"
    else:
        error: str | None = None
        for chat_id in cfg.chat_ids:
            try:
                await vm_notify.send_telegram(notify_cfg, chat_id, row.body, None)
            except Exception as exc:  # noqa: BLE001 — httpx tarmoq xatosi ham: qator `pending`da qolsa navbatni to'sadi
                error = _safe_error(exc, notify_cfg.telegram_token)
                log.warning("alert_dispatch tenant=%s kind=%s chat=%s: %s", row.tenant_id, row.kind, chat_id, error)
        row.status = "failed" if error else "sent"
        row.error = error
        if error is None:
            row.sent_at = datetime.now(timezone.utc)
    await session.commit()


async def dispatch_once(session_factory: async_sessionmaker) -> None:
    """Navbatdagi barcha `pending` qatorlarni ketma-ket yuboradi — har biri
    BITTA qisqa tranzaksiyada (`FOR UPDATE SKIP LOCKED`, bir nechta worker
    xavfsiz, `vm_notify._claim` BILAN BIR XIL g'oya)."""
    while True:
        async with session_factory() as session:
            row = (await session.execute(
                select(AlertLog).where(AlertLog.status == "pending")
                .order_by(AlertLog.id).with_for_update(skip_locked=True).limit(1)
            )).scalar_one_or_none()
            if row is None:
                return
            await _send_pending(session, row)


async def run_forever(session_factory: async_sessionmaker, interval_s: float) -> None:
    while True:
        try:
            await dispatch_once(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
            log.exception("alert_dispatch aylanishida xato")
        await asyncio.sleep(interval_s)
