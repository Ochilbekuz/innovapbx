"""Ovozli pochta bildirishnomalari (m1c-contract.md §2) — API ichidagi fon
vazifa (`main.py` lifespan): har `vm_notify_interval_s` soniyada spool'dagi
INBOX xabarlarini ko'rib, yangi xabar uchun e-mail (SMTP, stdlib `smtplib`,
`asyncio.to_thread`) va/yoki Telegram (`sendAudio`/`sendMessage`, httpx)
yuboradi.

Bir xabar bir kanalga BIR MARTA: avval `voicemail_notifications` ga qator
«egallanadi» (`insert ... on conflict do nothing`, darhol commit), keyin
yuboriladi, keyin `sent`/`failed`. API qayta ishga tushsa ham, bir nechta
worker bo'lsa ham takror yo'q (unique kalit). `failed` qator
`vm_notify_max_attempts` gacha qayta urinadi. Yuborish o'rtasida jarayon
o'lsa qator `pending` qoladi va QAYTA YUBORILMAYDI (kamida-bir-marta emas,
ko'pi-bilan-bir-marta — takror xat yomonroq deb tanlandi)."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import NotifySettings, Tenant, VoicemailBox
from app.services import voicemail as vm
from app.services.crypto import decrypt_secret

log = logging.getLogger("innova.vm_notify")

_HTTP_TIMEOUT_S = 15.0
_SMTP_TIMEOUT_S = 15.0


class NotifyError(RuntimeError):
    """Yuborish xatosi — sababi matnda (`/settings/notify/test` 502 `notify_failed`)."""


@dataclass(frozen=True)
class NotifyConfig:
    smtp_host: str | None
    smtp_port: int
    smtp_tls: str
    smtp_user: str | None
    smtp_password: str | None
    from_email: str | None
    telegram_token: str | None
    telegram_api_base: str


@dataclass(frozen=True)
class PendingMessage:
    tenant_id: str
    box_id: str
    mailbox: str
    msg_id: str
    callerid: str
    duration_s: int
    received_at: str
    wav: Path | None
    email: str | None
    email_notify: bool
    telegram_notify: bool
    telegram_chat_id: str | None
    attach_audio: bool


# ------------------------------------------------------------ sof qismlar
def telegram_caption(msg: PendingMessage) -> str:
    return (f"Yangi ovozli xabar — quti {msg.mailbox}\n"
            f"Kimdan: {msg.callerid or 'noma`lum'}\n"
            f"Davomiyligi: {msg.duration_s} s\n"
            f"Vaqt: {msg.received_at}")


def build_email(cfg: NotifyConfig, msg: PendingMessage, *, to: str | None = None) -> EmailMessage:
    em = EmailMessage()
    em["From"] = cfg.from_email or ""
    em["To"] = to or msg.email or ""
    em["Subject"] = f"Yangi ovozli xabar: {msg.callerid or 'noma`lum'} -> {msg.mailbox}"
    em.set_content(telegram_caption(msg) + "\n")
    if msg.attach_audio and msg.wav is not None and msg.wav.is_file():
        em.add_attachment(msg.wav.read_bytes(), maintype="audio", subtype="wav",
                          filename=f"{msg.mailbox}-{msg.wav.name}")
    return em


def channels_for(cfg: NotifyConfig, msg: PendingMessage) -> list[str]:
    """Kanal faqat quti sozlamasi HAM tizim sozlamasi tayyor bo'lsa — aks holda
    urinish «yoqib» yuborilmaydi (sozlama keyin to'ldirilsa xabar baribir boradi)."""
    channels = []
    if msg.email_notify and msg.email and cfg.smtp_host and cfg.from_email:
        channels.append("email")
    if msg.telegram_notify and msg.telegram_chat_id and cfg.telegram_token:
        channels.append("telegram")
    return channels


# ------------------------------------------------------------ yuborish adapterlari
def send_email_sync(cfg: NotifyConfig, message: EmailMessage) -> None:
    if not cfg.smtp_host:
        raise NotifyError("SMTP server sozlanmagan")
    if cfg.smtp_tls == "tls":
        client = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=_SMTP_TIMEOUT_S,
                                  context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=_SMTP_TIMEOUT_S)
    with client as smtp:
        if cfg.smtp_tls == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if cfg.smtp_user:
            smtp.login(cfg.smtp_user, cfg.smtp_password or "")
        smtp.send_message(message)


async def send_telegram(cfg: NotifyConfig, chat_id: str, caption: str, audio: Path | None, *,
                        transport: httpx.AsyncBaseTransport | None = None) -> None:
    if not cfg.telegram_token:
        raise NotifyError("Telegram bot token sozlanmagan")
    base = f"{cfg.telegram_api_base.rstrip('/')}/bot{cfg.telegram_token}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S, transport=transport) as client:
        if audio is not None:
            resp = await client.post(f"{base}/sendAudio", data={"chat_id": chat_id, "caption": caption},
                                     files={"audio": (audio.name, audio.read_bytes(), "audio/wav")})
        else:
            resp = await client.post(f"{base}/sendMessage", json={"chat_id": chat_id, "text": caption})
    if resp.status_code != 200:
        try:
            reason = resp.json().get("description", "")
        except ValueError:
            reason = resp.text[:200]
        raise NotifyError(f"Telegram {resp.status_code}: {reason}")


async def deliver(cfg: NotifyConfig, msg: PendingMessage, channel: str) -> None:
    try:
        if channel == "telegram":
            audio = msg.wav if msg.attach_audio and msg.wav is not None and msg.wav.is_file() else None
            await send_telegram(cfg, msg.telegram_chat_id or "", telegram_caption(msg), audio)
        else:
            await asyncio.to_thread(send_email_sync, cfg, build_email(cfg, msg))
    except NotifyError:
        raise
    except Exception as exc:  # noqa: BLE001 — tarmoq/SMTP xatosi sabab matni bilan
        raise NotifyError(f"{type(exc).__name__}: {exc}") from exc


async def send_test(cfg: NotifyConfig, channel: str, to: str) -> None:
    probe = PendingMessage(tenant_id="", box_id="", mailbox="test", msg_id="", callerid="Innova PBX",
                           duration_s=0, received_at="-", wav=None, email=to, email_notify=True,
                           telegram_notify=True, telegram_chat_id=to, attach_audio=False)
    await deliver(cfg, probe, channel)


# ------------------------------------------------------------ DB (nosof)
async def load_config(session: AsyncSession, tenant_id: str) -> NotifyConfig:
    row = await session.get(NotifySettings, tenant_id)
    if row is None:
        return NotifyConfig(None, 587, "starttls", None, None, None, None, "https://api.telegram.org")
    return NotifyConfig(
        smtp_host=row.smtp_host, smtp_port=row.smtp_port, smtp_tls=row.smtp_tls, smtp_user=row.smtp_user,
        smtp_password=await decrypt_secret(session, row.smtp_password_enc) if row.smtp_password_enc else None,
        from_email=row.from_email,
        telegram_token=await decrypt_secret(session, row.telegram_token_enc) if row.telegram_token_enc else None,
        telegram_api_base=row.telegram_api_base,
    )


def _inbox_messages(box: VoicemailBox, tenant_code: str) -> list[PendingMessage]:
    folder = vm.box_dir(tenant_code, box.mailbox)
    items = [i for i in vm.list_messages(folder) if i["folder"] == "inbox" and i["msg_id"]]
    return [
        PendingMessage(
            tenant_id=str(box.tenant_id), box_id=str(box.id), mailbox=box.mailbox, msg_id=i["msg_id"],
            callerid=i["callerid"], duration_s=i["duration_s"], received_at=i["received_at"],
            wav=folder / f"{i['id']}.wav", email=box.email, email_notify=box.email_notify,
            telegram_notify=box.telegram_notify, telegram_chat_id=box.telegram_chat_id,
            attach_audio=box.attach_audio,
        )
        for i in items
    ]


_CLAIM_SQL = text("""
insert into voicemail_notifications (tenant_id, box_id, msg_id, channel, status, attempts)
values (:tenant_id, :box_id, :msg_id, :channel, 'pending', 1)
on conflict (box_id, msg_id, channel) do update
  set status = 'pending', attempts = voicemail_notifications.attempts + 1
  where voicemail_notifications.status = 'failed' and voicemail_notifications.attempts < :max_attempts
returning id
""")
_FINISH_SQL = text("update voicemail_notifications set status = :status, error = :error where id = :id")


async def _claim(session: AsyncSession, msg: PendingMessage, channel: str) -> int | None:
    row = (await session.execute(_CLAIM_SQL, {
        "tenant_id": msg.tenant_id, "box_id": msg.box_id, "msg_id": msg.msg_id, "channel": channel,
        "max_attempts": settings.vm_notify_max_attempts,
    })).first()
    await session.commit()
    return row[0] if row else None


async def _notify_message(session: AsyncSession, cfg: NotifyConfig, msg: PendingMessage) -> None:
    for channel in channels_for(cfg, msg):
        claim_id = await _claim(session, msg, channel)
        if claim_id is None:
            continue
        error = None
        try:
            await deliver(cfg, msg, channel)
        except NotifyError as exc:
            error = str(exc)[:500]
            log.warning("vm_notify %s %s/%s: %s", channel, msg.mailbox, msg.msg_id, error)
        await session.execute(_FINISH_SQL, {"status": "failed" if error else "sent", "error": error, "id": claim_id})
        await session.commit()


async def scan_once(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        rows = (await session.execute(
            select(VoicemailBox, Tenant.code).join(Tenant, Tenant.id == VoicemailBox.tenant_id)
            .where(VoicemailBox.email_notify | VoicemailBox.telegram_notify)
        )).all()
        configs: dict[str, NotifyConfig] = {}
        for box, code in rows:
            tenant_id = str(box.tenant_id)
            if tenant_id not in configs:
                configs[tenant_id] = await load_config(session, tenant_id)
            for msg in _inbox_messages(box, code):
                await _notify_message(session, configs[tenant_id], msg)


async def run_forever(session_factory: async_sessionmaker, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            await scan_once(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
            log.exception("vm_notify skanida xato")
        await asyncio.sleep(interval_s)
