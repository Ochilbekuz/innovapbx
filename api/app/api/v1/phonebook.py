"""M9 B2 — Telefon kitobi (m9-freepbx-gaps-contract.md Bo'lak B2). CRUD +
CSV eksport/import; CID Lookup qidiruvi `app/services/cid_lookup.py`da shu
jadvallarni ishlatadi (`kind == "phonebook"`)."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import PlainTextResponse

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import PhonebookContact, PhonebookNumber, User
from app.schemas import (
    CreatePhonebookContactPayload,
    Paged,
    PhonebookContactMutated,
    PhonebookContactOut,
    PhonebookImportError,
    PhonebookImportResult,
    PhonebookNumberOut,
    UpdatePhonebookContactPayload,
)
from app.services.audit import record_audit
from app.services.fpbx.apply_plan import csv_cell
from app.services.number_normalize import normalize_number

router = APIRouter(prefix="/phonebook", tags=["phonebook"])

_CONTACT_OPTIONS = (selectinload(PhonebookContact.numbers),)
_MAX_ROWS = 2000
_MAX_BYTES = 1_000_000
_NUMBER_SEP = ";"
_LABEL_SEP = ":"
_CSV_COLUMNS = ("name", "company", "note", "numbers")


def _contact_out(contact: PhonebookContact) -> PhonebookContactOut:
    return PhonebookContactOut(
        id=str(contact.id), name=contact.name, company=contact.company, note=contact.note,
        numbers=[PhonebookNumberOut(id=str(n.id), number=n.number_norm, label=n.label) for n in contact.numbers],
        updated_at=contact.updated_at,
    )


async def _get_contact_or_404(session: AsyncSession, tenant_id: str, contact_id: str) -> PhonebookContact:
    return await get_tenant_scoped_or_404(
        session, PhonebookContact, tenant_id, contact_id, not_found_message="Kontakt topilmadi",
        options=_CONTACT_OPTIONS,
    )


def _build_numbers(tenant_id: str, numbers: list) -> list[PhonebookNumber]:
    rows = []
    for item in numbers:
        norm = normalize_number(item.number)
        if not norm:
            raise ApiError(422, "bad_number", "Raqam noto'g'ri", field="numbers")
        rows.append(PhonebookNumber(tenant_id=tenant_id, number_norm=norm, label=item.label))
    return rows


@router.get("", response_model=Paged)
async def list_contacts(
    q: str | None = None, page: int = 1, page_size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    tenant_id = str(user.tenant_id)
    stmt = select(PhonebookContact).where(PhonebookContact.tenant_id == tenant_id)
    count_stmt = select(func.count()).select_from(PhonebookContact).where(PhonebookContact.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        cond = (PhonebookContact.name.ilike(like)) | (PhonebookContact.company.ilike(like))
        stmt, count_stmt = stmt.where(cond), count_stmt.where(cond)
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(PhonebookContact.name).offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.options(*_CONTACT_OPTIONS)
    items = (await session.execute(stmt)).scalars().all()
    return Paged(items=[_contact_out(c) for c in items], total=total)


@router.post("", response_model=PhonebookContactMutated, status_code=201)
async def create_contact(
    payload: CreatePhonebookContactPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> PhonebookContactMutated:
    tenant_id = str(user.tenant_id)
    contact = PhonebookContact(tenant_id=tenant_id, name=payload.name, company=payload.company, note=payload.note)
    contact.numbers = _build_numbers(tenant_id, payload.numbers)
    session.add(contact)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="phonebook.create",
                        entity="phonebook_contact", entity_id=str(contact.id), diff={"name": payload.name})
    await session.commit()
    contact = await _get_contact_or_404(session, tenant_id, str(contact.id))
    return PhonebookContactMutated(item=_contact_out(contact))


@router.patch("/{contact_id}", response_model=PhonebookContactMutated)
async def update_contact(
    contact_id: str, payload: UpdatePhonebookContactPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> PhonebookContactMutated:
    tenant_id = str(user.tenant_id)
    contact = await _get_contact_or_404(session, tenant_id, contact_id)
    check_not_stale(contact.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        contact.name, diff["name"] = payload.name, payload.name
    if payload.company is not None:
        contact.company, diff["company"] = payload.company, payload.company
    if payload.note is not None:
        contact.note, diff["note"] = payload.note, payload.note
    if payload.numbers is not None:
        contact.numbers = _build_numbers(tenant_id, payload.numbers)
        diff["numbers"] = len(payload.numbers)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="phonebook.update",
                        entity="phonebook_contact", entity_id=str(contact.id), diff=diff)
    await session.commit()
    contact = await _get_contact_or_404(session, tenant_id, contact_id)
    return PhonebookContactMutated(item=_contact_out(contact))


@router.delete("/{contact_id}", status_code=204, response_model=None)
async def delete_contact(
    contact_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    contact = await _get_contact_or_404(session, tenant_id, contact_id)
    await session.delete(contact)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="phonebook.delete",
                        entity="phonebook_contact", entity_id=str(contact_id))
    await session.commit()


def _numbers_cell(contact: PhonebookContact) -> str:
    parts = [f"{n.number_norm}{_LABEL_SEP}{n.label}" if n.label else n.number_norm for n in contact.numbers]
    return _NUMBER_SEP.join(parts)


@router.get("/export.csv")
async def export_contacts_csv(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> PlainTextResponse:
    tenant_id = str(user.tenant_id)
    items = (await session.execute(
        select(PhonebookContact).where(PhonebookContact.tenant_id == tenant_id).order_by(PhonebookContact.name)
        .options(*_CONTACT_OPTIONS)
    )).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    for c in items:
        writer.writerow([csv_cell(v) for v in (c.name, c.company or "", c.note or "", _numbers_cell(c))])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="phonebook.csv"',
    })


def _parse_numbers_cell(raw: str) -> list[PhonebookNumber]:
    rows = []
    for part in filter(None, (p.strip() for p in raw.split(_NUMBER_SEP))):
        number, _, label = part.partition(_LABEL_SEP)
        norm = normalize_number(number)
        if norm:
            rows.append(PhonebookNumber(number_norm=norm, label=label or None))
    return rows


async def _existing_contacts_by_number(
    session: AsyncSession, tenant_id: str,
) -> dict[str, PhonebookContact]:
    """`number_norm -> PhonebookContact` — import qatorini mos kontaktga bog'lash
    uchun (SQLAlchemy identity-map tufayli bir xil kontakt bir necha raqamdan
    topilsa ham BIR XIL Python obyekti bo'ladi)."""
    rows = (await session.execute(
        select(PhonebookNumber.number_norm, PhonebookContact)
        .join(PhonebookContact, PhonebookContact.id == PhonebookNumber.contact_id)
        .where(PhonebookContact.tenant_id == tenant_id)
        .options(*_CONTACT_OPTIONS)
    )).all()
    return {number_norm: contact for number_norm, contact in rows}


def _clean_str(value: str | None) -> str:
    return (value or "").strip()


def _clean_optional(value: str | None) -> str | None:
    return _clean_str(value) or None


def _match_existing_contact(
    numbers: list[PhonebookNumber], existing_by_number: dict[str, PhonebookContact],
) -> PhonebookContact | None:
    """Qatordagi raqamlardan BIRI mavjud kontaktga tegishli bo'lsa — o'shani
    qaytaradi (bo'lmasa `None`, yangi kontakt yaratiladi)."""
    for number in numbers:
        if number.number_norm in existing_by_number:
            return existing_by_number[number.number_norm]
    return None


def _reindex_numbers(
    contact: PhonebookContact, numbers: list[PhonebookNumber], existing_by_number: dict[str, PhonebookContact],
) -> None:
    for number in numbers:
        existing_by_number[number.number_norm] = contact


def _update_existing_contact(
    existing: PhonebookContact, *, name: str, company: str | None, note: str | None,
    numbers: list[PhonebookNumber], existing_by_number: dict[str, PhonebookContact],
) -> None:
    existing.name, existing.company, existing.note = name, company, note
    existing.numbers = numbers
    _reindex_numbers(existing, numbers, existing_by_number)


def _create_new_contact(
    session: AsyncSession, tenant_id: str, *, name: str, company: str | None, note: str | None,
    numbers: list[PhonebookNumber], existing_by_number: dict[str, PhonebookContact],
) -> None:
    contact = PhonebookContact(tenant_id=tenant_id, name=name, company=company, note=note)
    contact.numbers = numbers
    session.add(contact)
    _reindex_numbers(contact, numbers, existing_by_number)


async def _import_row(
    session: AsyncSession, tenant_id: str, row: dict, existing_by_number: dict[str, PhonebookContact],
) -> tuple[str, str | None]:
    """Bitta CSV qatorini qo'llaydi: `(action, message)` — `action`
    'created'|'updated'|'skipped'|'error'. Moslik/yaratish/yangilash — alohida
    kichik yordamchilarda (CRAP: CC pastroq, splitting — ub-mode)."""
    name = _clean_str(row.get("name"))
    numbers = _parse_numbers_cell(_clean_str(row.get("numbers")))
    for number in numbers:
        number.tenant_id = tenant_id
    if not name and not numbers:
        return "skipped", None
    if not name:
        return "error", "name majburiy"

    company = _clean_optional(row.get("company"))
    note = _clean_optional(row.get("note"))
    existing = _match_existing_contact(numbers, existing_by_number)

    if existing is not None:
        _update_existing_contact(existing, name=name, company=company, note=note,
                                  numbers=numbers, existing_by_number=existing_by_number)
        return "updated", None

    _create_new_contact(session, tenant_id, name=name, company=company, note=note,
                         numbers=numbers, existing_by_number=existing_by_number)
    return "created", None


async def _run_import(
    session: AsyncSession, tenant_id: str, rows: list[dict], *, dry_run: bool,
) -> PhonebookImportResult:
    """Bitta tranzaksiya: xato bo'lsa HECH NARSA yozilmaydi; `dry_run` — flush qilib
    ko'radi-da qaytaradi (commit — chaqiruvchida, audit bilan birga, bitta commit)."""
    existing_by_number = await _existing_contacts_by_number(session, tenant_id)
    created = updated = skipped = 0
    errors: list[PhonebookImportError] = []
    for idx, row in enumerate(rows, start=2):  # 1-qator sarlavha
        action, message = await _import_row(session, tenant_id, row, existing_by_number)
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        elif action == "skipped":
            skipped += 1
        else:
            errors.append(PhonebookImportError(row=idx, message=message or "xato"))
    if errors:
        await session.rollback()
        return PhonebookImportResult(created=0, updated=0, skipped=0, errors=errors)

    await session.flush()
    if dry_run:
        await session.rollback()
    return PhonebookImportResult(created=created, updated=updated, skipped=skipped, errors=[])


@router.post("/import", response_model=PhonebookImportResult)
async def import_contacts_csv(
    file: UploadFile = File(...), dry_run: bool = Form(False),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> PhonebookImportResult:
    raw = await file.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ApiError(413, "too_large", "Fayl juda katta (≤1MB)")
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if len(rows) > _MAX_ROWS:
        raise ApiError(413, "too_large", f"Qatorlar soni {_MAX_ROWS}dan ko'p")

    tenant_id = str(user.tenant_id)
    result = await _run_import(session, tenant_id, rows, dry_run=dry_run)
    if not dry_run and not result.errors:
        await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="phonebook.import",
                            entity="phonebook_contact", entity_id="-", diff={"created": result.created})
        await session.commit()
    return result
