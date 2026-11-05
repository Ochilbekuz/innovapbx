"""Kutish musiqasi (MOH) — Asterisk tomoniga yetkazish (m1b-contract.md
bo'lim 8). `sounds` docker hajmi (`settings.sounds_dir`) API va Asterisk
konteynerlarida UMUMIY — har audio fayl `{sounds_dir}/{tenant_code}/{audio_id}.wav`
da yotadi (`app/api/v1/audio.py`). Har MOH sinfi uchun shu papka ICHIDA
alohida kichik papka yaratamiz (`.../moh/{moh_id}/`) va u ichiga sinf
fayllariga TARTIB bilan nomlangan simvolik havolalar qo'yamiz — Asterisk
`mode=files` shu papkani alfavit tartibida o'qiydi (`sort=random` bo'lmasa).

`dialplan` hajmi (`settings.dialplan_dir`) ham umumiy — generatsiya qilingan
`musiconhold_innova.conf` shu yerga yoziladi, `asterisk/etc-asterisk/musiconhold.conf`
uni `#include` qiladi (extensions.conf'dagi andoza bilan BIR XIL)."""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import MohClass
from app.services.apply import AmiLike
from app.services.atomic_write import atomic_write

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MohFileSnapshot:
    audio_file_id: str
    position: int


@dataclass(frozen=True)
class MohClassSnapshot:
    id: str
    shuffle: bool
    files: tuple[MohFileSnapshot, ...]
    is_default: bool = False


def asterisk_class_name(tenant_code: str, moh_id: str) -> str:
    """Asterisk'dagi sinf nomi — `alembic/sql/0007_moh_musicclass.sql`
    `asterisk_queues.musicclass` BILAN AYNAN BIR XIL formula. Ikkisidan
    birini o'zgartirsang — ikkinchisini albatta yangila (aks holda navbat
    "noto'g'ri" (mavjud bo'lmagan) MOH sinfiga ishora qiladi)."""
    return f"{tenant_code}-moh-{moh_id}"


def moh_class_dir(tenant_code: str, moh_id: str) -> Path:
    return Path(settings.sounds_dir) / tenant_code / "moh" / moh_id


def _audio_wav_path(tenant_code: str, audio_file_id: str) -> Path:
    return Path(settings.sounds_dir) / tenant_code / f"{audio_file_id}.wav"


def _wanted_links(tenant_code: str, moh: MohClassSnapshot) -> dict[str, Path]:
    return {
        f"{f.position:04d}_{f.audio_file_id}.wav": _audio_wav_path(tenant_code, f.audio_file_id)
        for f in moh.files
    }


def sync_moh_class_files(tenant_code: str, moh: MohClassSnapshot) -> None:
    """Sinf papkasini `moh.files` ro'yxatiga mos holga keltiradi — eskirgan
    havolalarni o'chiradi, yetishmaganlarini yaratadi. IDEMPOTENT: o'zgarish
    bo'lmasa diskka tegmaydi."""
    directory = moh_class_dir(tenant_code, moh.id)
    directory.mkdir(parents=True, exist_ok=True)
    wanted = _wanted_links(tenant_code, moh)
    for existing in directory.iterdir():
        if existing.name not in wanted:
            existing.unlink(missing_ok=True)
    for link_name, target in wanted.items():
        link_path = directory / link_name
        if link_path.is_symlink() and os.readlink(link_path) == str(target):
            continue
        link_path.unlink(missing_ok=True)
        link_path.symlink_to(target)


def remove_moh_class_dir(tenant_code: str, moh_id: str) -> None:
    """Sinf o'chirilganda uning havolalar papkasini tozalaydi — aks holda
    `sounds` hajmida yetim (hech qanday `[...]` bo'limga ishora qilmaydigan)
    simvolik havolalar abadiy qolib ketardi."""
    shutil.rmtree(moh_class_dir(tenant_code, moh_id), ignore_errors=True)


def _class_body_lines(tenant_code: str, moh: MohClassSnapshot) -> list[str]:
    lines = ["mode=files", f"directory={moh_class_dir(tenant_code, moh.id)}"]
    if moh.shuffle:
        lines.append("sort=random")
    return lines


def build_musiconhold_conf(tenant_code: str, classes: list[MohClassSnapshot]) -> str:
    """Sof funksiya: DB/disk'ga tegmaydi — faqat matn quradi (dialplan
    compiler.py bilan BIR XIL qolip: query alohida, qurish sof).

    "Asosiy qilish" (`moh_classes.is_default`) — `is_default=true` sinf uchun
    ODDIY `[{tenant}-moh-{id}]` bo'limidan TASHQARI `[default](+)` ham
    yoziladi: `(+)` — `musiconhold.conf`dagi statik `[default]` (ishga tushish
    zahirasi, `make_moh_fallback.py`) bo'limini KENGAYTIRADI, `res_musiconhold`
    o'zgaruvchilarni tartib bilan o'qigani uchun keyingi `directory=` g'olib.
    Oddiy takroriy `[default]` YARAMAYDI — Asterisk 22 ikkala sinfni ham
    ro'yxatga oladi va qidiruvda BIRINCHISINI (fallback) topadi (jonli
    tekshirilgan, 2026-11-05). Natija: navbat (`moh_class_id IS NULL`), park
    va oddiy kanal hold BIR JOYDAN tanlangan sinfni eshitadi."""
    lines = [
        "; Innova PBX — API avtomatik generatsiya qiladi (qo'lda tahrirlanmasin).",
        f"; tenant={tenant_code}",
    ]
    # Bo'sh asosiy sinf (masalan migratsiyadagi «default», 0 fayl) zahira ohangni
    # o'chirib qo'ymasin — Asterisk 0 faylli sinfni umuman yuklamaydi.
    default_moh = next((m for m in classes if m.is_default and m.files), None)
    for moh in classes:
        lines += ["", f"[{asterisk_class_name(tenant_code, moh.id)}]", *_class_body_lines(tenant_code, moh)]
    if default_moh is not None:
        lines += ["", "[default](+)", *_class_body_lines(tenant_code, default_moh)]
    return "\n".join(lines) + "\n"


def write_musiconhold_file(text_content: str) -> None:
    """Atomik yozish — `app/services/atomic_write.py` (DRY, `apply.py`
    `write_dialplan_file` BILAN BIR XIL qolip, ikkisi ham `dialplan`
    umumiy hajmiga yozadi)."""
    atomic_write(settings.dialplan_dir, settings.musiconhold_filename, text_content, tmp_prefix=".tmp-moh-")


async def load_tenant_moh_classes(session: AsyncSession, tenant_id: str) -> list[MohClassSnapshot]:
    """Nosof qadam — snapshot.py'dagi `build_snapshot` bilan BIR XIL rol:
    DB so'rovi shu yerda, pure builder'ga esa faqat dataclass boriladi."""
    rows = (await session.execute(
        select(MohClass).where(MohClass.tenant_id == tenant_id)
        .options(selectinload(MohClass.files))
        .order_by(MohClass.name)
    )).scalars().all()
    return [
        MohClassSnapshot(
            id=str(m.id), shuffle=m.shuffle, is_default=m.is_default,
            files=tuple(
                MohFileSnapshot(audio_file_id=str(f.audio_file_id), position=f.position) for f in m.files
            ),
        )
        for m in rows
    ]


def _has_playable_file(tenant_code: str, moh: MohClassSnapshot) -> bool:
    playable = any(target.exists() for target in _wanted_links(tenant_code, moh).values())
    if moh.files and not playable:
        log.warning("MOH sinf %s: DB'dagi %d fayldan birortasi diskda yo'q — sinf bo'sh", moh.id, len(moh.files))
    return playable


async def _reload_and_verify_moh(ami: AmiLike, tenant_code: str, classes: list[MohClassSnapshot]) -> None:
    await ami.ensure_connected()
    reload_resp = await ami.action("Command", Command="moh reload")
    if str(reload_resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"moh reload rad etildi: {reload_resp.get('Message', '')}")
    show_resp = await ami.action("Command", Command="moh show classes")
    output = (show_resp.get("Output", "") or "").lower()
    # Haqiqiy Asterisk xatti-harakati (2026-10-28, m1b-proof.sh orqali
    # topilgan): `res_musiconhold` 0 fayli bo'lgan sinfni `moh show
    # classes`da UMUMAN ko'rsatmaydi (sinfni butunlay tashlab yuboradi) —
    # bu kutilgan holat, SINXRONIZATSIYA XATOSI emas. Shu sabab faqat
    # diskda KAMIDA bitta ijro etiladigan fayli bor sinflar tekshiriladi:
    # DB'da fayl bor-u, wav diskdan yo'qolgan sinf (m4b-proof.sh, 2026-10-29:
    # shunday holat zaxirasidan tiklash butun tiklashni `failed` qilardi)
    # ham Asterisk uchun bo'sh — ogohlantirish, xato emas.
    missing = [
        moh.id for moh in classes
        if _has_playable_file(tenant_code, moh) and asterisk_class_name(tenant_code, moh.id).lower() not in output
    ]
    if missing:
        raise RuntimeError(f"tekshiruv muvaffaqiyatsiz: MOH sinf(lar) ko'rinmadi: {missing}")


async def apply_moh(session: AsyncSession, *, tenant_id: str, tenant_code: str, ami: AmiLike) -> None:
    """MOH sinflarini Asterisk'ga yetkazadi (m1b-contract.md bo'lim 8) —
    `app/api/v1/moh_classes.py`ning HAR UCH yozuvchi endpoint'idan (create/
    update/delete) `apply_config()`dan TASHQARI alohida chaqiriladi: navbat
    `musicclass`si realtime SQL orqali olinadi (`asterisk_queues` view,
    reload shart emas), shu sabab dialplan qo'llanishiga (barcha boshqa
    entity turlari uchun) bog'lab qo'yish keraksiz keng ta'sir doirasi
    (har qanday chiquvchi marshrut/trunk CRUD'ini MOH'ga bog'lab qo'yish)
    yaratardi."""
    classes = await load_tenant_moh_classes(session, tenant_id)
    for moh in classes:
        sync_moh_class_files(tenant_code, moh)
    write_musiconhold_file(build_musiconhold_conf(tenant_code, classes))
    await _reload_and_verify_moh(ami, tenant_code, classes)
