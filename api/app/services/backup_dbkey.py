"""`db_key.enc` qismi — `INNOVA_DB_KEY`ni ZAXIRA PAROLI bilan mustaqil shifrlash
(m4b-contract.md §0/§1: "Arxiv ichida db_key.enc ... zaxira paroli bilan shifrlangan").

Nega bu shifrlash ARXIVNING o'z shifrlashidan (INNOVABK1, `backup_format.py`) MUSTAQIL,
garchi bitta parol ishlatilsa ham: disaster recovery paytida `restore_job.py` old
`INNOVA_DB_KEY`ni ANIQ shu qism orqali oladi (pgcrypto ustunlarini qayta kalitlash,
`crypto_registry.rekey_all`, uchun) — DB'ga ulanishdan ham, boshqa hech narsadan ham
qat'iy MUSTAQIL bo'lishi SHART (yangi server hali bo'sh, DB kaliti hali eski emas).

Butun modul SOF — `backup_format.derive_key` (scrypt) + AES-256-GCM, alohida tuz/nonce."""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.backup_format import derive_key

_SALT_LEN = 16
_NONCE_LEN = 12
_AAD = b"innova-db-key"


def encrypt_db_key(passphrase: str, db_key: str) -> bytes:
    """Qaytaradi: `tuz(16) || nonce(12) || shifr matn` — bitta bayt oqimi, `db_key.enc` qism tarkibi."""
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    aead = AESGCM(derive_key(passphrase, salt))
    return salt + nonce + aead.encrypt(nonce, db_key.encode("utf-8"), _AAD)


def decrypt_db_key(passphrase: str, blob: bytes) -> str:
    """`encrypt_db_key` teskarisi. Parol noto'g'ri yoki qism buzilgan bo'lsa
    `cryptography.exceptions.InvalidTag` ko'taradi — chaqiruvchi (`restore_job.py`)
    uni `bad_passphrase`/`backup_corrupt`ga aylantiradi."""
    salt, nonce, ct = blob[:_SALT_LEN], blob[_SALT_LEN:_SALT_LEN + _NONCE_LEN], blob[_SALT_LEN + _NONCE_LEN:]
    aead = AESGCM(derive_key(passphrase, salt))
    return aead.decrypt(nonce, ct, _AAD).decode("utf-8")
