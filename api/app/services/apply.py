"""Qo'llash jarayoni — architecture.md 30-51-qatorlar, 6 qadam:
tranzaksiyada yozish -> compile (sof funksiya) -> sha256 solishtirish ->
atomik fayl yozish -> AMI `dialplan reload` + tekshiruv -> xato bo'lsa oldingi
holatga qaytarish. Chaqiruvchi (router) allaqachon bitta DB tranzaksiya
ichida bo'lishi kerak — entity yozuvi va `config_revisions` birga commit
bo'ladi (faqat FAYL/AMI holati "orqaga qaytariladi", DB yozuvi emas)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import ConfigRevision
from app.db.session import lock_tenant
from app.services.atomic_write import atomic_write
from app.services.compiler import CompileError, compile_dialplan, dialplan_sha256
from app.services.parking import ensure_parking_lot
from app.services.snapshot import build_snapshot


class AmiLike(Protocol):
    async def ensure_connected(self) -> None: ...
    async def action(self, action: str, **fields: object) -> dict: ...
    async def action_list(self, action: str, **fields: object) -> list[dict]: ...


@dataclass(frozen=True)
class ApplyResult:
    status: str
    revision: int | None
    message: str | None

    def to_dict(self) -> dict:
        return {"status": self.status, "revision": self.revision, "message": self.message}


def write_dialplan_file(text_content: str) -> None:
    """Atomik yozish — `app/services/atomic_write.py` (DRY, `moh.py`
    `write_musiconhold_file` BILAN BIR XIL qolip)."""
    atomic_write(settings.dialplan_dir, settings.dialplan_filename, text_content, tmp_prefix=".tmp-dialplan-")


async def _last_revision(session: AsyncSession, tenant_id: str, status: str) -> ConfigRevision | None:
    res = await session.execute(
        select(ConfigRevision)
        .where(ConfigRevision.tenant_id == tenant_id, ConfigRevision.status == status)
        .order_by(ConfigRevision.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _reload_and_verify(ami: AmiLike, tenant_code: str) -> None:
    await ami.ensure_connected()
    reload_resp = await ami.action("Command", Command="dialplan reload")
    if str(reload_resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"dialplan reload rad etildi: {reload_resp.get('Message', '')}")
    show_resp = await ami.action("Command", Command=f"dialplan show {tenant_code}-from-trunk")
    output = show_resp.get("Output", "") or ""
    # DIQQAT: Asterisk 22'da kontekst topilmasa "There is no existence of
    # '<ctx>' context" deb yozadi — "No such context" EMAS (eski/boshqa
    # versiya iborasi). Faqat shu bitta iborani tekshirish tekshiruvni
    # amalda doim "muvaffaqiyatli" qilib qo'ygan edi — haqiqiy chaqiruv bilan
    # sinovda topilgan (fayl ruxsatlari xatosi tufayli kontekst umuman
    # yuklanmagan bo'lsa ham `apply` "applied" deb qaytargan). Shu sabab
    # ikkala ibora (eski va yangi) HAMDA bo'sh javob tekshiriladi.
    lowered = output.lower()
    old_wording = "no such context" in lowered
    new_wording = "is no existence" in lowered
    empty = not lowered.strip()
    # Har bir shart alohida qatorda — coverage.py ko'p qatorli bitta ifodani
    # faqat birinchi qatorga bog'laydi (mutator shu sabab qolgan qatorlarni
    # "uncovered" deb ko'rsatgan edi, aslida ular sinovda ishlatilgan).
    if old_wording or new_wording or empty:
        raise RuntimeError("tekshiruv muvaffaqiyatsiz: kontekst topilmadi")


async def restore_revision(
    session: AsyncSession, *, tenant_id: str, tenant_code: str, user_id: str | None, ami: AmiLike,
    target: ConfigRevision,
) -> ApplyResult:
    """Avval qo'llangan reviziyani qayta tiklaydi — m1b-contract.md bo'lim 7.
    Joriy bazadagi obyektlardan QAYTA KOMPILYATSIYA qilinMAYDI, balki o'sha
    reviziyaning saqlangan dialplan matni to'g'ridan-to'g'ri yoziladi — shu
    sabab chaqiruvchi natijani doim `drift=true` bilan qaytarishi SHART
    (bazadagi obyektlar reviziya yaratilgandan beri o'zgargan bo'lishi
    mumkin, bu "tiklash" ularni qayta yozmaydi, faqat eski dialplan matnini
    qayta faollashtiradi)."""
    current = await _last_revision(session, tenant_id, "applied")
    revision = ConfigRevision(
        tenant_id=tenant_id, user_id=user_id, status="compiled",
        dialplan_sha256=target.dialplan_sha256, dialplan=target.dialplan,
    )
    session.add(revision)
    await session.flush()
    try:
        write_dialplan_file(target.dialplan)
        await _reload_and_verify(ami, tenant_code)
        revision.status = "applied"
        await session.flush()
        return ApplyResult(status="applied", revision=revision.id, message=None)
    except Exception as exc:  # noqa: BLE001 — tiklash xatosi boshqariladi, qayta ko'tarilmaydi
        revision.status = "rolled_back"
        revision.error = str(exc)[:500]
        await session.flush()
        fallback_text = current.dialplan if current else "; Innova PBX — bo'sh.\n"
        try:
            write_dialplan_file(fallback_text)
            await _reload_and_verify(ami, tenant_code)
        except Exception:  # noqa: BLE001, S110 — eng yomon holatda ham javob qaytarishi kerak
            pass
        return ApplyResult(
            status="rolled_back",
            revision=current.id if current else None,
            message=f"Tiklashda xato, oldingi holatga qaytarildi: {exc}"[:500],
        )


async def apply_config(
    session: AsyncSession, *, tenant_id: str, user_id: str | None, ami: AmiLike,
) -> ApplyResult:
    await lock_tenant(session, tenant_id)
    snapshot = await build_snapshot(session, tenant_id)
    try:
        new_text = compile_dialplan(snapshot)
    except CompileError as exc:
        # `exc.code`/`exc.details` — m1a-contract.md: halqa uchun 422 `loop`
        # + `details.path`; umumiy xatolar uchun sukut `compile_error`.
        raise ApiError(422, exc.code, str(exc), details=exc.details or None) from exc

    new_sha = dialplan_sha256(new_text)
    last_good = await _last_revision(session, tenant_id, "applied")
    if last_good is not None and last_good.dialplan_sha256 == new_sha:
        return ApplyResult(status="unchanged", revision=last_good.id, message=None)

    revision = ConfigRevision(
        tenant_id=tenant_id, user_id=user_id, status="compiled",
        dialplan_sha256=new_sha, dialplan=new_text,
    )
    session.add(revision)
    await session.flush()

    try:
        # M2a §3: park lot dialplan'dan OLDIN (`Park(<code>-park)` unga tayanadi); idempotent.
        await ensure_parking_lot(ami, snapshot.tenant_code, snapshot.parking)
        write_dialplan_file(new_text)
        await _reload_and_verify(ami, snapshot.tenant_code)
        revision.status = "applied"
        await session.flush()
        return ApplyResult(status="applied", revision=revision.id, message=None)
    except Exception as exc:  # noqa: BLE001 — qo'llash xatosi boshqariladi, qayta ko'tarilmaydi
        revision.status = "rolled_back"
        revision.error = str(exc)[:500]
        await session.flush()
        fallback_text = last_good.dialplan if last_good else "; Innova PBX — bo'sh.\n"
        try:
            write_dialplan_file(fallback_text)
            await _reload_and_verify(ami, snapshot.tenant_code)
        except Exception:  # noqa: BLE001, S110 — eng yomon holatda ham javob qaytarishi kerak
            pass
        return ApplyResult(
            status="rolled_back",
            revision=last_good.id if last_good else None,
            message=f"Qo'llashda xato, oldingi holatga qaytarildi: {exc}"[:500],
        )
