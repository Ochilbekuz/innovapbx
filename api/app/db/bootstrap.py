"""Konteyner ishga tushishida bir martalik DB sozlash: `innova.key` GUC'ni
joriy bazaga o'rnatish — Asterisk realtime view (`sip_secret()`,
alembic/sql/0001_schema.sql) shu yordamida parolni ochadi. `ALTER DATABASE
... SET` — rol/baza darajasida doimiy standart, idempotent (qayta ishga
tushirilsa ham xavfsiz)."""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.services.sip_transport import sync_sip_files


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


async def bootstrap_db_settings() -> None:
    key = settings.require_db_key()
    engine = create_async_engine(settings.database_url, pool_size=1)
    try:
        async with engine.begin() as conn:
            dbname = (await conn.execute(text("select current_database()"))).scalar_one()
            quoted_db = '"' + dbname.replace('"', '""') + '"'
            await conn.execute(text(f"alter database {quoted_db} set innova.key = {_quote_literal(key)}"))
        # M3a: SIP/RTP fayllari DB'dan qayta yoziladi (generator yangilangan bo'lsa — masalan
        # `transport-wss` — eski hajmdagi fayl ham yangilanadi). `migrate` servisi Asterisk'dan OLDIN
        # ishlaydi (compose: `dialplan` + `certs:ro` hajmlari ulangan).
        async with AsyncSession(engine) as session:
            await sync_sip_files(session)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(bootstrap_db_settings())


if __name__ == "__main__":
    main()
