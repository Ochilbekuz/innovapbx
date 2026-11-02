"""extension, voicemail, trunk yozuvchilari. Sirlar FAQAT shu yerda ochiq
ko'rinadi (payload) va darhol `encrypt_secret()`/bcrypt'ga beriladi — hech
qayerga (warning/log/natija) yozilmaydi."""
from __future__ import annotations

import secrets

from sqlalchemy import select

from app.core.security import generate_sip_secret, hash_password
from app.db.models import Extension, Trunk, VoicemailBox
from app.schemas_follow_me import follow_me_default
from app.services.crypto import encrypt_secret
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import SkipItem, WriteCtx, clamp, matches, pick, unique_name
from app.services.fpbx.writers.media import add_audio
from app.services.fpbx.writers.refs import extension_id, resolve_target

_RECORDING = frozenset({"always", "never", "on_demand"})
_TRANSPORTS = frozenset({"udp", "tcp", "tls"})
_FORWARD = r"[0-9]{2,15}"
_EMAIL = r"[^@\s]+@[^@\s]+\.[^@\s]+"


def _sip_secret(ctx: WriteCtx, entry: Entry) -> str:
    """`rotate_weak_secrets=true` va zaif sir -> yangi tasodifiy (CSV'da faqat belgi)."""
    secret = entry.payload.get("secret_plain")
    if secret and ctx.rotate_weak and entry.weak_secret:
        ctx.rotated.append(entry.source_ref)
        return generate_sip_secret()
    return secret or generate_sip_secret()


def _forward(ctx: WriteCtx, entry: Entry, value: str | None) -> str | None:
    if value is None or matches(_FORWARD, value):
        return value
    ctx.warn(entry.source_ref, "forward_invalid", "Yo'naltirish raqami Innova formatiga mos emas — o'chirildi")
    return None


async def write_extension(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    number = p.get("number") or entry.number
    name = p.get("name") or entry.name
    optional = {"codecs": p["codecs"]} if p.get("codecs") else {}  # yo'q bo'lsa — ustun standarti
    ext = Extension(
        **optional, tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry),
        number=number, name=name, sip_password_enc=await encrypt_secret(ctx.session, _sip_secret(ctx, entry)),
        max_contacts=clamp(p.get("max_contacts"), 1, 10, 3), outbound_callerid=p.get("outbound_callerid"),
        ring_seconds=clamp(p.get("ringtimer"), 5, 120, 25), recording=pick(p.get("recording"), _RECORDING, "on_demand"),
        recording_out=pick(p.get("recording_out"), _RECORDING, "on_demand"),
        dnd=bool(p.get("dnd")), forward_always=_forward(ctx, entry, p.get("forward_always")),
        forward_busy=_forward(ctx, entry, p.get("forward_busy")),
        no_answer_target_id=await resolve_target(ctx, p.get("no_answer_target_id"), source_ref=entry.source_ref),
        follow_me=p.get("follow_me") or follow_me_default(),
    )
    ctx.session.add(ext)
    await ctx.session.flush()
    ctx.ext_ids[number] = str(ext.id)
    return str(ext.id)


async def _box_owner(ctx: WriteCtx, entry: Entry, mailbox: str) -> str | None:
    """Qutining egasi (ichki raqam); egasining qutisi allaqachon bo'lsa — egasiz quti."""
    owner = await extension_id(ctx, mailbox)
    if owner is None:
        return None
    taken = (await ctx.session.execute(
        select(VoicemailBox.id).where(VoicemailBox.extension_id == owner).limit(1)
    )).first()
    if taken is None:
        return owner
    ctx.warn(entry.source_ref, "voicemail_owner_taken", f"{mailbox} raqamining qutisi bor — egasiz quti yaratildi")
    return None


async def _greeting(ctx: WriteCtx, entry: Entry, relpath: str | None) -> str | None:
    if not relpath:
        return None
    try:
        return await add_audio(ctx, name=f"Pochta salomlashuvi {entry.payload['mailbox']}",
                               language="uz", relpath=relpath)
    except SkipItem as exc:
        ctx.warn(entry.source_ref, exc.code, exc.message)
        return None


async def write_voicemail(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    mailbox = p["mailbox"]
    target_id = ctx.target_for(entry)
    owner = await _box_owner(ctx, entry, mailbox)
    email = p.get("email") if matches(_EMAIL, p.get("email")) else None
    box = VoicemailBox(
        tenant_id=ctx.tenant_id, target_id=target_id, extension_id=owner, mailbox=mailbox,
        pin_hash=hash_password(p.get("pin_plain") or f"{secrets.randbelow(10**6):06d}"),
        email=email, email_notify=bool(p.get("email_notify")) and email is not None,
        attach_audio=bool(p.get("attach_audio")),
        greeting_audio_id=await _greeting(ctx, entry, p.get("greeting_source_relpath")),
    )
    ctx.session.add(box)
    await ctx.session.flush()
    if owner is not None:
        ext = await ctx.session.get(Extension, owner)
        if ext.no_answer_target_id is None:  # voicemail_boxes.py::create_box bilan bir xil
            ext.no_answer_target_id = target_id
    return str(box.id)


def _check_trunk(entry: Entry) -> None:
    p = entry.payload
    if p.get("auth_mode") == "ip" and not p.get("match_ips"):
        raise SkipItem("trunk_match_missing", "IP trunk uchun manzil (match) yo'q")
    if p.get("auth_mode") == "register" and not (p.get("username") and p.get("secret_plain")):
        raise SkipItem("trunk_auth_missing", "Registratsiya trunki uchun login/parol yo'q")


def trunk_host(p: dict) -> str:
    """Innova trunk `host`ni majburiy qiladi (trunks API `bad_host`); FreePBX IP trunkida
    `sip_server` bo'sh bo'lishi mumkin — u holda birinchi `match` manzili (niqobsiz)."""
    host = (p.get("host") or "").strip()
    if host or p.get("auth_mode") != "ip":
        return host
    return next((m.split("/", 1)[0].strip() for m in p.get("match_ips") or [] if m.strip()), "")


async def write_trunk(ctx: WriteCtx, entry: Entry) -> str:
    """Trunk siri provayderniki — `rotate_weak_secrets` unga TEGMAYDI (faqat ichki raqamlar)."""
    _check_trunk(entry)
    p = entry.payload
    secret = p.get("secret_plain")
    optional = {k: p[k] for k in ("codecs", "max_channels") if p.get(k)}
    trunk = Trunk(
        tenant_id=ctx.tenant_id, name=await unique_name(ctx, Trunk, p.get("name") or entry.name),
        auth_mode=p["auth_mode"], host=trunk_host(p), port=clamp(p.get("port"), 1, 65535, 5060),
        transport=pick(p.get("transport"), _TRANSPORTS, "udp"), username=p.get("username"),
        password_enc=await encrypt_secret(ctx.session, secret) if secret else None,
        from_domain=p.get("from_domain"), match_ips=list(p.get("match_ips") or []),
        outbound_callerid=p.get("outbound_callerid"), enabled=bool(p.get("enabled", True)), **optional,
    )
    ctx.session.add(trunk)
    await ctx.session.flush()
    return str(trunk.id)
