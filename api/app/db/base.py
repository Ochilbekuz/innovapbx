"""DeclarativeBase — barcha `datetime` ustunlari global ravishda `timestamptz`
(timezone-aware) sifatida xaritalanadi, chunki schema.sql'da HAMMA vaqt
ustuni `timestamptz` (architecture.md qoidasi). Buni `type_annotation_map`
orqali bir joyda hal qilmasak, SQLAlchemy `Mapped[datetime]`ni sukut
bo'yicha naive `DateTime()` deb oladi — asyncpg esa `datetime.now(timezone.utc)`
(aware) qiymatini "timestamp without time zone" ustunga yozishga urinib,
`can't subtract offset-naive and offset-aware datetimes` bilan 500 beradi
(sinovda topilgan — `POST /setup` AVVAL shu bilan qulagan edi)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }
