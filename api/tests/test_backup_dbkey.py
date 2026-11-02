from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from app.services.backup_dbkey import decrypt_db_key, encrypt_db_key


def test_round_trip():
    blob = encrypt_db_key("correct-passphrase-123", "the-db-key-value")
    assert decrypt_db_key("correct-passphrase-123", blob) == "the-db-key-value"


def test_wrong_passphrase_raises_invalid_tag():
    blob = encrypt_db_key("correct-passphrase-123", "the-db-key-value")
    with pytest.raises(InvalidTag):
        decrypt_db_key("wrong-passphrase", blob)


def test_each_call_uses_fresh_salt_and_nonce():
    a = encrypt_db_key("pw", "k")
    b = encrypt_db_key("pw", "k")
    assert a != b
