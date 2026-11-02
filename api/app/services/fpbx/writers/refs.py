"""`$ref` hal qilish (m5a-contract.md §0 bog'liqlik tartibi). Tartib:
1) shu apply'da yaratilgan (`ctx.targets`/`ctx.entities`);
2) avvalgi import izi (`migration_items` -> haqiqiy obyekt hali bormi);
3) raqam bo'yicha mavjud Innova obyekti — `skip`/`conflict` elementlari shu yo'l
   bilan QO'LDA yaratilgan obyektga ulanadi (proof §7: qo'lda 101).
Topilmagan/qo'llab-quvvatlanmagan manzil -> tenantning `hangup` maqsadi + ogohlantirish."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import (
    Announcement,
    AudioFile,
    CallTarget,
    Conference,
    DialNumber,
    Extension,
    Ivr,
    MigrationItem,
    Queue,
    RingGroup,
    TimeCondition,
    TimeGroup,
    Trunk,
    VoicemailBox,
)
from app.services.fpbx.writers.context import WriteCtx, WriteError, lookup_id
from app.services.target_resolution import create_target

SATELLITE_MODELS: dict[str, Any] = {
    "extension": Extension, "voicemail": VoicemailBox, "ring_group": RingGroup, "queue": Queue,
    "conference": Conference, "announcement": Announcement, "ivr": Ivr, "time_condition": TimeCondition,
}
ENTITY_MODELS: dict[str, Any] = {"audio": AudioFile, "time_group": TimeGroup, "trunk": Trunk}

# kind -> (target_id ustuni, raqam ustuni) — "raqam bo'yicha" topish (3-qadam).
_BY_NUMBER: dict[str, tuple[Any, Any]] = {
    "extension": (Extension.target_id, Extension.number),
    "voicemail": (VoicemailBox.target_id, VoicemailBox.mailbox),
    "ring_group": (DialNumber.target_id, DialNumber.number),
    "queue": (DialNumber.target_id, DialNumber.number),
    "conference": (DialNumber.target_id, DialNumber.number),
}
_BUILTIN_LABELS = {"hangup": "Uzish", "busy": "Band"}


def split_ref(key: str) -> tuple[str, str]:
    kind, _, source_ref = key.partition(":")
    return kind, source_ref


def bare_key(source_ref: str) -> str:
    """`users:101` -> `101`; `voicemail.conf:default/105` -> `105`."""
    return source_ref.rsplit(":", 1)[-1].rsplit("/", 1)[-1]


async def migrated_id(ctx: WriteCtx, kind: str, source_ref: str) -> str | None:
    row = (await ctx.session.execute(
        select(MigrationItem.innova_id).where(
            MigrationItem.tenant_id == ctx.tenant_id, MigrationItem.kind == kind,
            MigrationItem.source_ref == source_ref,
        ).limit(1)
    )).first()
    return str(row[0]) if row is not None and row[0] is not None else None


async def builtin_target(ctx: WriteCtx, kind: str) -> str:
    """Tenantning tayyor `hangup`/`busy` maqsadi (bootstrap yaratadi); yo'q bo'lsa — ochiladi."""
    if kind not in ctx.builtin:
        row = (await ctx.session.execute(
            select(CallTarget.id).where(CallTarget.tenant_id == ctx.tenant_id, CallTarget.kind == kind)
            .order_by(CallTarget.created_at).limit(1)
        )).first()
        if row is None:
            target = await create_target(ctx.session, ctx.tenant_id, kind, _BUILTIN_LABELS[kind])
            ctx.builtin[kind] = str(target.id)
        else:
            ctx.builtin[kind] = str(row[0])
    return ctx.builtin[kind]


async def _target_by_number(ctx: WriteCtx, kind: str, source_ref: str) -> str | None:
    columns = _BY_NUMBER.get(kind)
    if columns is None:
        return None
    target_col, number_col = columns
    row = (await ctx.session.execute(
        select(target_col).where(number_col.class_.tenant_id == ctx.tenant_id,
                                 number_col == bare_key(source_ref)).limit(1)
    )).first()
    return str(row[0]) if row is not None else None


async def existing_target(ctx: WriteCtx, key: str) -> str | None:
    kind, source_ref = split_ref(key)
    model = SATELLITE_MODELS.get(kind)
    if model is None:
        return None
    innova_id = await migrated_id(ctx, kind, source_ref)
    if innova_id is not None:
        row = await ctx.session.get(model, innova_id)
        if row is not None:
            return str(row.target_id)
    return await _target_by_number(ctx, kind, source_ref)


async def _unresolved(ctx: WriteCtx, source_ref: str, code: str, message: str) -> str:
    ctx.warn(source_ref, code, message)
    return await builtin_target(ctx, "hangup")


async def resolve_target(ctx: WriteCtx, value: dict | None, *, source_ref: str) -> str | None:
    """`None` -> `None` (ixtiyoriy maydon); aks holda doim call_target id."""
    if value is None:
        return None
    key = value.get("$ref")
    if key is not None:
        found = ctx.targets.get(key) or await existing_target(ctx, key)
        return found or await _unresolved(ctx, source_ref, "ref_unresolved", f"Manzil topilmadi ({key}) — uziladi")
    kind = value.get("kind")
    if kind == "external":
        return await _unresolved(ctx, source_ref, "external_dest_unsupported",
                                 "Tashqi raqamga yo'naltirish qo'llab-quvvatlanmaydi — uziladi")
    if kind in _BUILTIN_LABELS:
        return await builtin_target(ctx, kind)
    return await _unresolved(ctx, source_ref, "dest_unsupported", f"Noma'lum manzil turi: {kind}")


async def required_target(ctx: WriteCtx, value: dict | None, *, source_ref: str) -> str:
    """NOT NULL maqsad ustunlari (`timeout_target_id` va h.k.) — bo'sh bo'lsa `hangup`."""
    return await resolve_target(ctx, value, source_ref=source_ref) or await builtin_target(ctx, "hangup")


async def resolve_entity(ctx: WriteCtx, value: dict | None) -> str | None:
    """audio/time_group/trunk `$ref` -> entity id (call_target EMAS)."""
    key = (value or {}).get("$ref")
    if key is None:
        return None
    if key in ctx.entities:
        return ctx.entities[key]
    kind, source_ref = split_ref(key)
    innova_id = await migrated_id(ctx, kind, source_ref)
    model = ENTITY_MODELS.get(kind)
    if innova_id is None or model is None:
        return None
    return innova_id if await ctx.session.get(model, innova_id) is not None else None


async def extension_id(ctx: WriteCtx, number: str | None) -> str | None:
    """A'zo/qutining egasi — shu apply'da yaratilgan YOKI mavjud (qo'lda) ichki raqam."""
    return await lookup_id(ctx, ctx.ext_ids, Extension.number, number)


async def fallback_audio(ctx: WriteCtx, source_ref: str) -> str:
    """IVR salomlashuvi/e'lon audiosi NOT NULL — manba audiosi bo'lmasa tizim ovozi."""
    row = (await ctx.session.execute(
        select(AudioFile.id).where(AudioFile.tenant_id == ctx.tenant_id)
        .order_by((AudioFile.source == "system").desc(), AudioFile.created_at).limit(1)
    )).first()
    if row is None:
        raise WriteError("audio_missing", f"{source_ref}: audio topilmadi va tizim ovozi yo'q")
    ctx.warn(source_ref, "audio_fallback", "Manba audiosi topilmadi — tizim ovozi qo'yildi")
    return str(row[0])
