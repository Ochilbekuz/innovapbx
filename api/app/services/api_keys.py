"""REST API kalitlari (m3b-contract.md §4) — sof qoidalar.

Format `ipk_<prefix8>_<secret32>`; bazada FAQAT `sha256(kalit)` + `prefix` (ochiq kalit bir marta
yaratishda qaytariladi). `last_used_at` ko'pi bilan daqiqada bir yangilanadi.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

SCOPES = ("calls:read", "recordings:read", "calls:originate", "extensions:read")
KEY_RE = re.compile(r"ipk_([a-z0-9]{8})_[A-Za-z0-9]{32}")
_PREFIX_ALPHABET = string.ascii_lowercase + string.digits
_SECRET_ALPHABET = string.ascii_letters + string.digits
TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class NewKey:
    plaintext: str
    prefix: str
    key_hash: str


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def generate_key() -> NewKey:
    prefix = "".join(secrets.choice(_PREFIX_ALPHABET) for _ in range(8))
    secret = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(32))
    plaintext = f"ipk_{prefix}_{secret}"
    return NewKey(plaintext=plaintext, prefix=prefix, key_hash=hash_key(plaintext))


def parse_prefix(raw: str) -> str | None:
    match = KEY_RE.fullmatch(raw)
    return match.group(1) if match else None


def key_matches(plaintext: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_key(plaintext), stored_hash)


def validate_scopes(scopes: list[str]) -> list[str]:
    unique = list(dict.fromkeys(scopes))
    if not unique or any(s not in SCOPES for s in unique):
        raise ValueError("scopes")
    return unique


def key_usable(row: Any, now: datetime) -> bool:
    return row.revoked_at is None and (row.expires_at is None or row.expires_at > now)


def should_touch(last_used_at: datetime | None, now: datetime) -> bool:
    return last_used_at is None or now - last_used_at >= TOUCH_INTERVAL


def has_scope(scopes: list[str], needed: str) -> bool:
    return needed in scopes
