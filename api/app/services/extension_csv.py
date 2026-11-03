"""M9 B4 — ichki raqamlar CSV import/eksport (m9-freepbx-gaps-contract.md Bo'lak B4).

Cheklovlar (hujjatlashtirilgan, kontraktda aniq ko'rsatilmagan ustunlar uchun):
- `language` — FAQAT eksport (`User.language`, ext'ga bog'langan portal foydalanuvchisi
  bo'lsa); import paytida o'ZGARTIRILMAYDI (Extension'da bunday ustun yo'q).
- `voicemail` — FAQAT eksport (quti mavjudligi, `VoicemailBox.extension_id`); import orqali
  quti YARATILMAYDI/o'CHIRILMAYDI (alohida funksiya — M1c).
- `call_waiting` — `Extension.call_waiting` ustuniga bog'liq; ustun hali bo'lmasa (eski
  migratsiya holati) eksportda bo'sh, import qatori ustunni e'tiborsiz qoldiradi
  (`hasattr` bilan forward-compat).

Yaratish — `app/api/v1/extensions.py::new_extension` QAYTA ishlatiladi (dublikat
validatsiya yozilmagan, dryer). Import — IKKI bosqich: avval HAMMA qator tekshiriladi/
rejalashtiriladi (yozishsiz — `ensure_number_free` ham shu bosqichda), SHUNDAN KEYIN
(xato bo'lmasa) haqiqiy yozish — shunday qilib bitta qatordagi xato oldingi qatorlar
uchun qisman flush/rollback holatini buzmaydi (CRAP/async xavfsizlik)."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import generate_sip_secret
from app.db.models import CallTarget, Extension, User, VoicemailBox
from app.schemas import ExtensionImportRow, ExtensionImportResult
from app.services.crypto import encrypt_secret
from app.services.dialplan_safety import has_control_chars, is_dialplan_number
from app.services.numbers import ensure_number_free

MAX_ROWS = 2000
MAX_BYTES = 1_000_000
COLUMNS = (
    "number", "name", "email", "outbound_cid", "language", "voicemail",
    "record_in", "record_out", "max_contacts", "call_waiting", "enabled",
)
_NUMBER_RE = re.compile(r"^\d{2,10}$")
_RECORDING_VALUES = {"always", "never", "on_demand"}
_BOOL_TRUE = {"1", "true", "yes", "ha"}
_BOOL_FALSE = {"0", "false", "no", "yo'q", "yoq"}
_HAS_CALL_WAITING = hasattr(Extension, "call_waiting")


def _bool_cell(value: bool) -> str:
    return "1" if value else "0"


def _parse_bool(raw: str, *, default: bool) -> bool:
    low = raw.strip().lower()
    if not low:
        return default
    if low in _BOOL_TRUE:
        return True
    if low in _BOOL_FALSE:
        return False
    raise ValueError(f"noto'g'ri mantiqiy qiymat: {raw!r}")


async def export_rows(session: AsyncSession, tenant_id: str) -> list[list[str]]:
    """Sarlavha + har bir ichki raqam uchun bitta qator (sir HECH QACHON — faqat
    ommaviy maydonlar, kontrakt talabi)."""
    exts = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id).order_by(Extension.number)
    )).scalars().all()
    languages = dict((await session.execute(
        select(User.extension_id, User.language).where(
            User.tenant_id == tenant_id, User.extension_id.is_not(None))
    )).all())
    mailboxes = set((await session.execute(
        select(VoicemailBox.extension_id).where(VoicemailBox.tenant_id == tenant_id)
    )).scalars().all())

    rows = [list(COLUMNS)]
    for ext in exts:
        call_waiting = _bool_cell(getattr(ext, "call_waiting", True)) if _HAS_CALL_WAITING else ""
        rows.append([
            ext.number, ext.name, ext.email or "", ext.outbound_callerid or "",
            languages.get(ext.id) or "", _bool_cell(ext.id in mailboxes),
            ext.recording, ext.recording_out, str(ext.max_contacts), call_waiting, _bool_cell(ext.enabled),
        ])
    return rows


def rows_to_csv(rows: list[list[str]]) -> str:
    from app.services.fpbx.apply_plan import csv_cell

    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow([csv_cell(v) for v in row])
    return buf.getvalue()


def parse_csv(text: str) -> list[dict]:
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader)


def _text_field_changes(row: dict) -> dict:
    """CONFIRMED HIGH tuzatish: `name`/`outbound_cid` generatsiya qilinadigan
    dialplan'ga tushadi (`app/services/compiler.py`), shu sabab bu yerda — CSV
    import `app/schemas.py` Pydantic validatsiyasini chetlab o'tadi — ularni
    `dialplan_safety` bilan tekshiramiz (xato -> qator xabari, `_plan_row`da
    tutiladi)."""
    changes: dict = {}
    if row.get("name"):
        name = row["name"].strip()
        if has_control_chars(name):
            raise ValueError("name: boshqaruv belgilar (shu jumladan qator ko'chirish) ruxsat etilmagan")
        changes["name"] = name
    if "email" in row:
        changes["email"] = row.get("email", "").strip() or None
    if "outbound_cid" in row:
        outbound_cid = row.get("outbound_cid", "").strip() or None
        if outbound_cid is not None and not is_dialplan_number(outbound_cid):
            raise ValueError("outbound_cid: faqat raqam va + * # _ X N Z . ! [ ] - belgilari (1-40 ta) ruxsat etilgan")
        changes["outbound_callerid"] = outbound_cid
    return changes


def _recording_field_changes(row: dict) -> dict:
    changes: dict = {}
    for csv_field, model_field in (("record_in", "recording"), ("record_out", "recording_out")):
        raw = (row.get(csv_field) or "").strip()
        if not raw:
            continue
        if raw not in _RECORDING_VALUES:
            raise ValueError(f"{csv_field}: noto'g'ri qiymat {raw!r}")
        changes[model_field] = raw
    return changes


def _max_contacts_change(row: dict) -> dict:
    raw_max = (row.get("max_contacts") or "").strip()
    if not raw_max:
        return {}
    if not raw_max.isdigit() or int(raw_max) < 1:
        raise ValueError("max_contacts: butun son (>=1) bo'lishi kerak")
    return {"max_contacts": int(raw_max)}


def _bool_field_changes(row: dict) -> dict:
    changes: dict = {}
    if "enabled" in row and row.get("enabled", "").strip():
        changes["enabled"] = _parse_bool(row["enabled"], default=True)
    if _HAS_CALL_WAITING and row.get("call_waiting", "").strip():
        changes["call_waiting"] = _parse_bool(row["call_waiting"], default=True)
    return changes


def _row_changes(row: dict) -> dict:
    """CSV qatoridan `Extension` maydonlari changes-dict'i (`ValueError` — 1-bosqichda
    tutiladi, qator xabariga aylanadi). Har bir maydon guruhi alohida kichik
    yordamchida (CRAP: CC pastroq, splitting — ub-mode)."""
    changes: dict = {}
    changes.update(_text_field_changes(row))
    changes.update(_recording_field_changes(row))
    changes.update(_max_contacts_change(row))
    changes.update(_bool_field_changes(row))
    return changes


def _apply_changes(ext: Extension, changes: dict) -> None:
    for model_field, value in changes.items():
        setattr(ext, model_field, value)


@dataclass
class _PlannedRow:
    row: int
    number: str
    action: str  # create|update|skip|error
    message: str | None = None
    changes: dict = field(default_factory=dict)
    existing: Extension | None = None


async def _plan_row(
    session: AsyncSession, tenant_id: str, row_no: int, row: dict,
    existing_by_number: dict[str, Extension], seen: set[str],
) -> _PlannedRow:
    """Yozishsiz tekshirish/rejalashtirish — `ensure_number_free` ham shu yerda
    (409 `ApiError` qator xabariga aylanadi, butun so'rovni yiqitmaydi)."""
    number = (row.get("number") or "").strip()
    if not number:
        return _PlannedRow(row=row_no, number="", action="skip")
    if not _NUMBER_RE.fullmatch(number):
        return _PlannedRow(row=row_no, number=number, action="error",
                            message="number: 2-10 raqam bo'lishi kerak")
    if number in seen:
        return _PlannedRow(row=row_no, number=number, action="error", message="takrorlangan raqam")
    seen.add(number)

    try:
        changes = _row_changes(row)
    except ValueError as exc:
        return _PlannedRow(row=row_no, number=number, action="error", message=str(exc))

    existing = existing_by_number.get(number)
    if existing is None:
        if "name" not in changes:
            return _PlannedRow(row=row_no, number=number, action="error",
                                message="name majburiy (yangi raqam)")
        try:
            await ensure_number_free(session, tenant_id, number)
        except ApiError as exc:
            return _PlannedRow(row=row_no, number=number, action="error", message=exc.message)
        return _PlannedRow(row=row_no, number=number, action="create", changes=changes)
    return _PlannedRow(row=row_no, number=number, action="update", changes=changes, existing=existing)


async def _create_extension(session: AsyncSession, tenant_id: str, number: str, changes: dict) -> str:
    """Yangi ichki raqam — `extensions.py::new_extension` BILAN BIR XIL yaratish
    (qayta ishlatish, dryer); qaytaradi — yaratilgan SIP siri (bir martalik)."""
    from app.api.v1.extensions import new_extension

    name = changes.pop("name")
    secret = generate_sip_secret()
    secret_enc = await encrypt_secret(session, secret)
    target = CallTarget(tenant_id=tenant_id, kind="extension", label=f"{number} · {name}")
    session.add(target)
    await session.flush()
    ext = new_extension(tenant_id=tenant_id, target_id=target.id, number=number,
                        name=name, sip_password_enc=secret_enc, codecs=None)
    _apply_changes(ext, changes)
    session.add(ext)
    return secret


async def run_import(
    session: AsyncSession, tenant_id: str, rows: list[dict], *, dry_run: bool,
) -> tuple[ExtensionImportResult, dict[str, str]]:
    """Bitta tranzaksiya: biror qatorda xato bo'lsa HECH NARSA yozilmaydi (kontrakt
    talabi) — shuning uchun avval HAMMASI rejalashtiriladi (`_plan_row`, yozishsiz),
    faqat xatosiz bo'lsa haqiqiy yozish bosqichi ishga tushadi. `secrets_csv` —
    faqat `dry_run=False` va yangilarining SIP siri (BIR MARTA, chaqiruvchida)."""
    existing_by_number = {e.number: e for e in (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id))).scalars().all()}

    seen: set[str] = set()
    planned = [await _plan_row(session, tenant_id, idx, row, existing_by_number, seen)
               for idx, row in enumerate(rows, start=2)]  # 1-qator sarlavha

    result_rows = [ExtensionImportRow(row=p.row, number=p.number, action=p.action, message=p.message)
                   for p in planned if p.action != "skip"]
    errors = sum(1 for p in planned if p.action == "error")
    if errors:
        return ExtensionImportResult(rows=result_rows, created=0, updated=0, errors=errors,
                                      secrets_csv=None), {}

    created = updated = 0
    secrets: dict[str, str] = {}
    for p in planned:
        if p.action == "update":
            _apply_changes(p.existing, p.changes)
            updated += 1
        elif p.action == "create":
            secrets[p.number] = await _create_extension(session, tenant_id, p.number, p.changes)
            created += 1
    await session.flush()

    if dry_run:
        await session.rollback()
        return ExtensionImportResult(rows=result_rows, created=created, updated=updated, errors=0,
                                      secrets_csv=None), {}
    return ExtensionImportResult(rows=result_rows, created=created, updated=updated, errors=0,
                                  secrets_csv=None), secrets
