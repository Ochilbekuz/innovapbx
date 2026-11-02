"""Qayta shifrlash registri — disaster recovery re-key (m4b-contract.md §0/§4.5).

Boshqa serverga (boshqa `INNOVA_DB_KEY` bilan) tiklaganda, zaxiradagi barcha
`pgcrypto` bilan shifrlangan ustunlar ESKI kalit (zaxiradan, `db_key.enc`) bilan
ochiladi va YANGI (joriy server) kalit bilan qayta yopiladi — `restore_job.py`
chaqiradi. Ro'yxat QO'LDA to'ldiriladi, lekin `tests/test_crypto_registry.py`
`app/db/models.py` dagi har `*_enc` ustunni avtomatik skanerlab, shu yerda
RO'YXATDAN O'TGANINI tekshiradi — yangi ustun qo'shilib, bu faylga yozilmasa test
qiziladi (to'liqlik kafolati)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class EncryptedColumn:
    table: str
    column: str
    # `column` jsonb bo'lsa — ichidagi shifrlangan kalit (masalan "admin_password_enc"
    # `system_settings.provisioning` ichida); oddiy matn ustun bo'lsa — None.
    json_path: str | None = None


# `app/services/crypto.py` (`encrypt_secret`/pgcrypto `base64(pgp_sym_encrypt(...))`)
# yoki bevosita SQL (`alembic/sql/0001_schema.sql` `sip_secret()`) orqali yoziladigan
# HAR BIR ustun — manba: `grep -rn "encrypt_secret\|_enc" app`.
ENCRYPTED_COLUMNS: tuple[EncryptedColumn, ...] = (
    EncryptedColumn("extensions", "sip_password_enc"),
    EncryptedColumn("trunks", "password_enc"),
    EncryptedColumn("integration_subscriptions", "secret_enc"),
    EncryptedColumn("notify_settings", "smtp_password_enc"),
    EncryptedColumn("notify_settings", "telegram_token_enc"),
    EncryptedColumn("users", "totp_secret_enc"),
    EncryptedColumn("system_settings", "provisioning", json_path="admin_password_enc"),
    # M4b §1 — `system_settings.backup` ichidagi sirlar: zaxira parol iborasi va
    # masofaviy nishon (S3/SFTP) sirlari ham `INNOVA_DB_KEY` bilan shifrlangan
    # (`app/services/crypto.py` `encrypt_secret`) — disaster-recovery qayta tiklashda
    # YANGI kalit bilan qayta yopilmasa, tiklashdan keyin o'qib bo'lmaydi.
    EncryptedColumn("system_settings", "backup", json_path="passphrase_enc"),
    EncryptedColumn("system_settings", "backup", json_path="targets.s3.secret_key_enc"),
    EncryptedColumn("system_settings", "backup", json_path="targets.sftp.password_enc"),
    EncryptedColumn("system_settings", "backup", json_path="targets.sftp.key_enc"),
)


def _json_path_array(json_path: str) -> str:
    """`"a.b.c"` → Postgres yo'l massivi matni `"{a,b,c}"` (`jsonb_set`/`#>>` uchun)."""
    return "{" + json_path.replace(".", ",") + "}"


def _json_extract_expr(column: str, json_path: str) -> str:
    """Bir qatlamli yo'l — eski `->>'key'` shakli (test/ishlab chiqilgan SQL o'zgarmasin);
    ko'p qatlamli (`"a.b.c"`) — `#>>'{a,b,c}'` (chuqur qiymatni oladi)."""
    if "." in json_path:
        return f"{column}#>>'{_json_path_array(json_path)}'"
    return f"{column}->>'{json_path}'"


def rekey_sql(col: EncryptedColumn) -> str:
    """Bitta ustun uchun UPDATE SQL — `:old_key`/`:new_key` parametrlari bilan
    bog'lanadi. Bo'sh (`null`/`""`) qiymatlar tegilmaydi."""
    if col.json_path:
        expr = _json_extract_expr(col.column, col.json_path)
        path = _json_path_array(col.json_path)
        new_value = (
            f"to_jsonb(encode(pgp_sym_encrypt("
            f"pgp_sym_decrypt(decode({expr}, 'base64'), :old_key), :new_key), 'base64'))"
        )
        set_clause = f"{col.column} = jsonb_set({col.column}, '{path}', {new_value})"
        where_clause = f"coalesce({expr}, '') <> ''"
    else:
        set_clause = (
            f"{col.column} = encode(pgp_sym_encrypt("
            f"pgp_sym_decrypt(decode({col.column}, 'base64'), :old_key), :new_key), 'base64')"
        )
        where_clause = f"coalesce({col.column}, '') <> ''"
    return f"update {col.table} set {set_clause} where {where_clause}"


def column_label(col: EncryptedColumn) -> str:
    suffix = f".{col.json_path}" if col.json_path else ""
    return f"{col.table}.{col.column}{suffix}"


async def rekey_all(session: AsyncSession, old_key: str, new_key: str) -> dict[str, int]:
    """Har ustun uchun qayta shifrlaydi, `{ustun_nomi: o'zgartirilgan_qatorlar}` qaytaradi
    (audit/jurnal uchun) — `restore_job.py` manifestdagi `db_key_fp` joriydan farq qilsagina
    chaqiradi."""
    counts: dict[str, int] = {}
    for col in ENCRYPTED_COLUMNS:
        result = await session.execute(text(rekey_sql(col)), {"old_key": old_key, "new_key": new_key})
        counts[column_label(col)] = result.rowcount or 0
    return counts
