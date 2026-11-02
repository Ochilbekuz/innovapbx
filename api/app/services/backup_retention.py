"""Saqlash muddati — eski nusxalarni aniqlash (m4b-contract.md §0: `keep_last`).

SOF funksiya: chaqiruvchi (`backup_job.py`) oldindan bitta saqlash joyidagi (local/s3/sftp)
FAQAT muvaffaqiyatli (`ok`) va FAQAT o'zimizning `innova-*.ibk` nusxalarini ro'yxatga
tergan bo'lishi kerak — bu modul begona fayllarga tegmaydi, chunki ularni umuman
ko'rmaydi."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RetentionItem:
    id: str
    created_at: datetime


def ids_to_delete(items: list[RetentionItem], keep_last: int) -> list[str]:
    """Eng yangi `keep_last` tadan tashqarisini o'chirish uchun qaytaradi."""
    if keep_last < 1:
        raise ValueError("keep_last >= 1 bo'lishi kerak")
    ordered = sorted(items, key=lambda item: item.created_at, reverse=True)
    return [item.id for item in ordered[keep_last:]]
