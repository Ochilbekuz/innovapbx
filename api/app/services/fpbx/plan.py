"""M5a — `analyze()` orkestratori (m5a-contract.md §0-§1): to'plam ildiz papkasini
(`bundle_dir`, `bundle.py` tomonidan allaqachon ochilgan/tasdiqlangan) o'qiydi,
barcha `kind` mapperlarini bog'liqlik tartibida chaqiradi, Innova DB'ga qarshi
to'qnashuvni tekshiradi va "JIM YO'QOLISH YO'Q" kafolatini beradi: har bir
`.tsv` qatori — yo bitta `Entry` (`items`), yo bitta `ignored[]` yozuvi.

SOF/DETERMINISTIK: DB faqat to'qnashuv UCHUN O'QILADI (yozilmaydi) — `apply`
bosqichi (hali yo'q, 2-muhandis) `analyze()`ni QAYTA chaqirib, `payload`ni
yangilaydi (shu sabab bu funksiya ikkinchi marta chaqirilsa ham bir xil natija
berishi SHART)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Blacklist, DialNumber, Extension, FeatureCode, MigrationItem
from app.services.fpbx import astdb as astdb_mod
from app.services.fpbx import bundle as bundle_mod
from app.services.fpbx import dest as dest_mod
from app.services.fpbx.mappers import Ctx, Entry, warning
from app.services.fpbx.mappers import announcement as announcement_mod
from app.services.fpbx.mappers import audio as audio_mod
from app.services.fpbx.mappers import blacklist as blacklist_mod
from app.services.fpbx.mappers import conference as conference_mod
from app.services.fpbx.mappers import extension as extension_mod
from app.services.fpbx.mappers import feature_code as feature_code_mod
from app.services.fpbx.mappers import inbound_route as inbound_route_mod
from app.services.fpbx.mappers import ivr as ivr_mod
from app.services.fpbx.mappers import moh as moh_mod
from app.services.fpbx.mappers import outbound_route as outbound_route_mod
from app.services.fpbx.mappers import queue as queue_mod
from app.services.fpbx.mappers import ring_group as ring_group_mod
from app.services.fpbx.mappers import time_condition as time_condition_mod
from app.services.fpbx.mappers import time_group as time_group_mod
from app.services.fpbx.mappers import trunk as trunk_mod
from app.services.fpbx.mappers import voicemail as voicemail_mod

__all__ = ["Analysis", "analyze", "summary_by_kind"]

# Bog'liqlik tartibi (m5a-contract.md §0): audio/MOH -> vaqt guruhlari -> ichki
# raqamlar(+ovozli pochta) -> trunklar -> ring group/navbat/konferensiya/e'lon ->
# IVR/vaqt sharti -> kiruvchi/chiquvchi marshrutlar -> qora ro'yxat/xususiyat kodi.
_MAPPERS: tuple[tuple[str, Any], ...] = (
    ("audio", audio_mod.map_audio),
    ("moh", moh_mod.map_moh),
    ("time_group", time_group_mod.map_time_group),  # "time_group" + "holiday" ikkisi
    ("extension", extension_mod.map_extension),
    ("voicemail", voicemail_mod.map_voicemail),
    ("trunk", trunk_mod.map_trunk),
    ("ring_group", ring_group_mod.map_ring_group),
    ("queue", queue_mod.map_queue),
    ("conference", conference_mod.map_conference),
    ("announcement", announcement_mod.map_announcement),
    ("ivr", ivr_mod.map_ivr),
    ("time_condition", time_condition_mod.map_time_condition),
    ("inbound_route", inbound_route_mod.map_inbound_route),
    ("outbound_route", outbound_route_mod.map_outbound_route),
    ("blacklist", blacklist_mod.map_blacklist),
    ("feature_code", feature_code_mod.map_feature_code),
)

# Mapperlar `ctx.table()`/`ctx.eav()` bilan to'g'ridan-to'g'ri o'qiydigan jadvallar
# (bosh jadval + uning EAV/detail sherigi) — qator darajasida ALLAQACHON Entry'ga
# qoplangan, shu sabab pastdagi "qolgan jadvallar" aylanishida ALOHIDA ignored
# yozuvi OLMAYDI.
CONSUMED_TABLES = frozenset({
    "users", "devices", "sip", "pjsip",
    "ringgroups",
    "queues_config", "queues_details",
    "ivr_details", "ivr_entries",
    "timeconditions",
    "announcement",
    "meetme",
    "trunks",
    "recordings", "music",
    "timegroups_groups", "timegroups_details",
    "incoming",
    "outbound_routes", "outbound_route_patterns", "outbound_route_trunks", "outbound_route_sequence",
    "findmefollow",
    "featurecodes",
})

# m5a-contract.md §1.2 oxirgi qatori: FreePBX ICHKI/BOSHQARUV jadvallari — migratsiya
# uchun mazmunsiz (modul holati, kesh, sertifikat, log, foydalanuvchi-boshqaruv
# paneli, soat-xizmat sozlamalari va h.k.). "table_not_supported" dan ATAYLAB
# FARQLI sabab (`system_table`) bilan qayd etiladi: bu TANILGAN va doimiy chiqarib
# tashlash, "table_not_supported" esa "hali qo'llab-quvvatlanmagan" degani (kelgusi
# versiyada qo'shilishi mumkin bo'lgan nomzod). Ro'yxat maqsadga ko'ra ochiq —
# yangi FreePBX versiyasida mos keladigan nom chiqsa, shu yerga qo'shiladi (aks holda
# "jim yo'qolish" testi uni `table_not_supported` sifatida CHIQARIB QO'YADI — yo'qolmaydi,
# faqat noaniq tasniflanadi).
_SYSTEM_TABLE_NAMES = frozenset({
    "admin", "freepbx_settings", "module_xml", "modules", "globals", "iax",
    "notifications", "sipsettings", "freepbx_log", "kvblobstore",
    "dahdi", "dahdichandids", "cron_jobs", "cronmanager",
    "custom_extensions", "emergencydevices", "miscapps",
    "callrecording", "callrecording_module",
    "trunk_dialpatterns", "outbound_route_email", "indications_zonelist",
    "voicemail_admin",
})
_SYSTEM_TABLE_PREFIXES = ("kvstore_", "certman_", "logfile_", "soundlang_", "userman_")

# Raqam (`dial_numbers`) to'qnashuvi tekshiriladigan kindlar — qolganlari (masalan
# `trunk`/`ivr`/`announcement`/`time_condition`) nom-unikal emas, shu sabab bu
# bosqichda tekshirilmaydi (m5a-contract.md §0 "unique nomlar" — keyingi versiya).
_NUMBER_CONFLICT_KINDS = frozenset({"extension", "ring_group", "queue", "conference"})

_COMMENT_PREFIX = ";"


def _is_system_table(name: str) -> bool:
    return name in _SYSTEM_TABLE_NAMES or name.startswith(_SYSTEM_TABLE_PREFIXES)


@dataclass
class Analysis:
    """`analyze()` natijasi. `items` — TO'LIQ `Entry` ro'yxati (`payload` bilan,
    chaqiruvchi — `migration.py` — DB'ga yozishdan oldin `entry.public_dict()`
    chaqiradi); `ignored`/`warnings` — allaqachon ommaviy (`dict`) shaklda."""

    items: list[Entry] = field(default_factory=list)
    ignored: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)


def summary_by_kind(items: list[Entry]) -> dict[str, dict[str, int]]:
    """`{kind: {action: count}}` — job DTO'ning `summary.by_kind` maydoni uchun."""
    out: dict[str, dict[str, int]] = {}
    for entry in items:
        by_action = out.setdefault(entry.kind, {})
        by_action[entry.action] = by_action.get(entry.action, 0) + 1
    return out


def _build_ctx(bundle_dir: Path, meta: dict[str, Any]) -> Ctx:
    astdb_path = bundle_dir / "astdb" / "astdb.txt"
    flat_astdb = astdb_mod.parse_astdb_file(astdb_path) if astdb_path.exists() else {}
    ctx = Ctx(root=bundle_dir, meta=meta, catalog=dest_mod.DestCatalog(), astdb=flat_astdb)

    miscdests = {row["id"]: row.get("destdial") for row in ctx.table("miscdests") if row.get("id")}
    ctx.catalog = dest_mod.DestCatalog(
        extensions=frozenset(r["extension"] for r in ctx.table("users") if r.get("extension")),
        ring_groups=frozenset(r["grpnum"] for r in ctx.table("ringgroups") if r.get("grpnum")),
        queues=frozenset(r["extension"] for r in ctx.table("queues_config") if r.get("extension")),
        ivrs=frozenset(r["id"] for r in ctx.table("ivr_details") if r.get("id")),
        time_conditions=frozenset(
            r["timeconditions_id"] for r in ctx.table("timeconditions") if r.get("timeconditions_id")),
        announcements=frozenset(
            r["announcement_id"] for r in ctx.table("announcement") if r.get("announcement_id")),
        conferences=frozenset(r["exten"] for r in ctx.table("meetme") if r.get("exten")),
        miscdests=miscdests,
    )
    # Ovozli pochta qutilarini DestCatalog'ga qo'shish uchun avval `users`ga bog'liq
    # ekanligini bilish kerak — `voicemail.py` buni allaqachon biladi (dublikat yo'q).
    vm_all = set(voicemail_mod.all_boxes(ctx))
    vm_unmatched = set(voicemail_mod.unmatched_mailboxes(ctx))
    ctx.catalog.voicemail_boxes = frozenset(vm_all - vm_unmatched)
    return ctx


def _ignored_tables(ctx: Ctx) -> list[dict[str, str]]:
    declared = list(ctx.meta.get("tables", []))
    not_exported = set(ctx.meta.get("ignored_tables", []))
    ignored: list[dict[str, str]] = [
        {"table": name, "key": "n/a", "reason": "table_not_exported"} for name in sorted(not_exported)
    ]
    for name in declared:
        if name in not_exported or name in CONSUMED_TABLES:
            continue
        count = len(ctx.table(name))
        if name == "miscdests":
            reason = "resolved_inline"
        elif _is_system_table(name):
            reason = "system_table"
        else:
            reason = "table_not_supported"
        ignored.append({"table": name, "key": str(count), "reason": reason})
    return ignored


def _ignored_voicemail(ctx: Ctx) -> list[dict[str, str]]:
    return [
        {"table": "voicemail.conf", "key": f"default/{mailbox}", "reason": "vm_without_extension"}
        for mailbox in voicemail_mod.unmatched_mailboxes(ctx)
    ]


def _custom_dialplan_warnings(ctx: Ctx) -> list[dict[str, str]]:
    """`conf/*_custom*.conf` (izoh/bo'sh qatorlardan tozalangandan keyin bo'sh
    emas) -> `custom_dialplan_present` ogohlantirishi (m5a-contract.md §1.2 oxiri).
    Tarjima qilinmaydi — faqat fayl nomi + ichidagi `[kontekst]` sarlavhalari."""
    conf_dir = ctx.root / "conf"
    if not conf_dir.is_dir():
        return []
    warnings: list[dict[str, str]] = []
    for path in sorted(conf_dir.glob("*_custom*.conf")):
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()]
        real_lines = [ln for ln in lines if ln and not ln.startswith(_COMMENT_PREFIX)]
        if not real_lines:
            continue
        contexts = [ln[1:-1] for ln in real_lines if ln.startswith("[") and ln.endswith("]")]
        label = ", ".join(contexts) if contexts else "(kontekstsiz)"
        warnings.append(warning(
            "custom_dialplan_present",
            f"{path.name}: qo'lda yozilgan, DB'da izi yo'q — kontekst(lar): {label}",
        ))
    return warnings


async def _already_migrated(session: AsyncSession, tenant_id: str, entry: Entry) -> bool:
    """`migration_items`da shu `(tenant, kind, source_ref)` bo'yicha avvalgi import
    izi bor-yo'qligi — bor bo'lsa, to'qnashuv REPLACE qilinishi mumkin (sukut
    `skip`); yo'q bo'lsa qo'lda yaratilgan deb hisoblanadi — USTIDAN YOZISH YO'Q."""
    row = (await session.execute(
        select(MigrationItem.id).where(
            MigrationItem.tenant_id == tenant_id,
            MigrationItem.kind == entry.kind,
            MigrationItem.source_ref == entry.source_ref,
        ).limit(1)
    )).first()
    return row is not None


async def _number_taken(session: AsyncSession, tenant_id: str, entry: Entry) -> bool:
    """`dial_numbers` — ring_group/queue/conference; `extensions.number` ham —
    chunki `extensions.py::create_extension()` HECH QACHON `dial_numbers` qatori
    yozmaydi (raqam maydoni shu jadvalning o'zida, `numbers.py::number_taken()`
    bilan BIR XIL ikki jadval qoidasi, proof §7: qo'lda yaratilgan ichki raqam)."""
    row = (await session.execute(
        select(DialNumber.number).where(
            DialNumber.tenant_id == tenant_id, DialNumber.number == entry.number,
        ).limit(1)
    )).first()
    if row is not None:
        return True
    if entry.kind != "extension":
        return False
    row = (await session.execute(
        select(Extension.id).where(
            Extension.tenant_id == tenant_id, Extension.number == entry.number,
        ).limit(1)
    )).first()
    return row is not None


async def _check_number_conflict(session: AsyncSession, tenant_id: str, entry: Entry) -> None:
    if not await _number_taken(session, tenant_id, entry):
        return
    entry.action = "conflict"
    entry.reason = "number_taken"
    entry.replaceable = await _already_migrated(session, tenant_id, entry)


async def _check_blacklist_exists(session: AsyncSession, tenant_id: str, entry: Entry) -> None:
    number = entry.payload.get("number")
    row = (await session.execute(
        select(Blacklist.number).where(
            Blacklist.tenant_id == tenant_id, Blacklist.number == number,
        ).limit(1)
    )).first()
    if row is not None:
        entry.action = "skip"
        entry.reason = "exists"


async def _check_feature_code_conflict(session: AsyncSession, tenant_id: str, entry: Entry) -> None:
    code = entry.payload.get("code")
    feature = entry.payload.get("feature")
    row = (await session.execute(
        select(FeatureCode.feature).where(
            FeatureCode.tenant_id == tenant_id,
            FeatureCode.code == code,
            FeatureCode.feature != feature,
        ).limit(1)
    )).first()
    if row is None:
        return
    entry.action = "conflict"
    entry.reason = "code_taken"
    entry.replaceable = await _already_migrated(session, tenant_id, entry)


async def _apply_already_imported(session: AsyncSession, tenant_id: str, items: list[Entry]) -> None:
    """Idempotentlik (m5a-contract.md §5/proof §6): shu `(tenant, kind, source_ref)`
    avval `apply` qilingan bo'lsa (`migration_items`da izi bor) — qayta `create`
    EMAS, `skip reason=already_imported`. `_apply_conflicts()`DAN OLDIN chaqiriladi:
    shu sabab raqam/kod to'qnashuvi (`_check_number_conflict`/blacklist `exists`/
    feature_code `code_taken`) FAQAT haqiqatan YANGI (hali import qilinmagan)
    to'qnashuvlarda ishga tushadi — avvalgi importning o'zi "to'qnashuv" bo'lib
    ko'rinmaydi."""
    for entry in items:
        if entry.action == "create" and await _already_migrated(session, tenant_id, entry):
            entry.action = "skip"
            entry.reason = "already_imported"


async def _apply_conflicts(session: AsyncSession, tenant_id: str, items: list[Entry]) -> None:
    """m5a-contract.md §0 "To'qnashuv": Innova'da raqam/kod band -> `conflict`
    (qo'lda yaratilganni ustidan yozish YO'Q, sukut `replaceable=False`); blacklist
    o'ziga xos — band bo'lsa shunchaki `skip reason=exists` (raqam, conflict emas)."""
    for entry in items:
        if entry.action != "create":
            continue
        if entry.kind in _NUMBER_CONFLICT_KINDS and entry.number:
            await _check_number_conflict(session, tenant_id, entry)
        elif entry.kind == "blacklist":
            await _check_blacklist_exists(session, tenant_id, entry)
        elif entry.kind == "feature_code":
            await _check_feature_code_conflict(session, tenant_id, entry)


async def analyze(bundle_dir: Path, session: AsyncSession, tenant_id: str) -> Analysis:
    """`bundle_dir` — `bundle.find_bundle_root()` orqali ALLAQACHON aniqlangan,
    tasdiqlangan to'plam ildizi (router shuni chaqirib `migration_jobs.bundle_path`ga
    yozadi). Bu funksiya hech narsa yozmaydi (DB'dan faqat to'qnashuv uchun o'qiydi)."""
    meta = bundle_mod.read_meta(bundle_dir)
    ctx = _build_ctx(bundle_dir, meta)

    items: list[Entry] = []
    for _kind, mapper_fn in _MAPPERS:
        items.extend(mapper_fn(ctx))

    await _apply_already_imported(session, tenant_id, items)
    await _apply_conflicts(session, tenant_id, items)

    ignored = _ignored_tables(ctx) + _ignored_voicemail(ctx)
    warnings = _custom_dialplan_warnings(ctx)

    return Analysis(items=items, ignored=ignored, warnings=warnings)
