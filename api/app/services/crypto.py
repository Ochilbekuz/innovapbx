"""SIP/trunk siri shifrlash — baza tomonidagi `pgcrypto` orqali (Python PGP
kutubxonasi shart emas). Kalit Asterisk realtime view (`sip_secret()`) bilan
bir xil (`INNOVA_DB_KEY`) — alembic/sql/0001_schema.sql'ga qarang."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


async def encrypt_secret(session: AsyncSession, plaintext: str) -> str:
    result = await session.execute(
        text("select encode(pgp_sym_encrypt(:plain, :key), 'base64')"),
        {"plain": plaintext, "key": settings.require_db_key()},
    )
    return result.scalar_one()


async def decrypt_secret(session: AsyncSession, encrypted: str) -> str:
    """`encrypt_secret` teskarisi — faqat server ichida ishlatiladi (SMTP
    parol / Telegram token yuborish paytida), javobga hech qachon chiqmaydi."""
    result = await session.execute(
        text("select pgp_sym_decrypt(decode(:enc, 'base64'), :key)"),
        {"enc": encrypted, "key": settings.require_db_key()},
    )
    return result.scalar_one()
