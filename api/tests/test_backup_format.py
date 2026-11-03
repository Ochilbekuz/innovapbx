"""INNOVABK1 arxiv formati — m4b-contract.md §0/§4 2-band (buzilish aniqlanishi)."""
from __future__ import annotations

import io

import pytest

from app.services.backup_format import (
    ArchiveReader,
    ArchiveWriter,
    BackupCorruptError,
    BadPassphraseError,
    rechunk,
)

PASSPHRASE = "to'g'ri-maxfiy-parol-12"


def _write_archive(chunks: list[bytes], passphrase: str = PASSPHRASE) -> bytes:
    buf = io.BytesIO()
    writer = ArchiveWriter(buf, passphrase)
    writer.write_stream(chunks)
    return buf.getvalue()


def _read_all(data: bytes, passphrase: str = PASSPHRASE) -> list[bytes]:
    reader = ArchiveReader(io.BytesIO(data), passphrase)
    return list(reader.read_chunks())


def test_round_trip_single_chunk():
    data = _write_archive([b"salom dunyo"])
    assert _read_all(data) == [b"salom dunyo"]


def test_round_trip_multiple_chunks_preserves_order_and_bytes():
    chunks = [b"a" * 10, b"b" * 20, b"c" * 5]
    data = _write_archive(chunks)
    assert b"".join(_read_all(data)) == b"".join(chunks)


def test_round_trip_empty_stream_still_produces_one_final_block():
    data = _write_archive([])
    assert _read_all(data) == [b""]


def test_wrong_passphrase_is_bad_passphrase_not_corrupt():
    data = _write_archive([b"sir"])
    with pytest.raises(BadPassphraseError):
        _read_all(data, passphrase="boshqa-parol")


def test_single_byte_flip_in_body_is_corrupt():
    data = bytearray(_write_archive([b"x" * 50]))
    data[-1] ^= 0x01  # oxirgi blok ichida — tag yoki shifr matnni buzadi
    with pytest.raises(BackupCorruptError):
        _read_all(bytes(data))


def test_truncated_end_is_corrupt():
    data = _write_archive([b"y" * (1024 * 1024 + 10)])  # kamida 2 bo'lak
    truncated = data[: len(data) - 20]
    with pytest.raises(BackupCorruptError):
        _read_all(truncated)


def test_header_only_truncation_is_corrupt():
    data = _write_archive([b"z"])
    with pytest.raises(BackupCorruptError):
        _read_all(data[:5])


def test_trailing_garbage_after_final_block_is_corrupt():
    """Oxirgi (`last=True`) blokdan keyin qo'shilgan har qanday bayt(lar) —
    arxivga qo'shilgan begona ma'lumot — aniqlanishi kerak, ko'r-ko'rona
    e'tiborsiz qolib ketmasligi uchun."""
    data = _write_archive([b"tamom"]) + b"keraksiz-qoldiq"
    with pytest.raises(BackupCorruptError):
        _read_all(data)


def test_oversized_scrypt_n_log2_in_header_is_rejected_before_derive():
    """Sarlavhadagi `n_log2` hujumchi nazorat qiladigan 1 bayt (0-255) — cheklovsiz
    `Scrypt().derive()` chaqirilsa N=2**255 bilan abadiy CPU/xotira band bo'lardi
    (DoS). Chegaradan tashqari qiymat `derive_key()`ga YETMASDAN rad etilishi kerak."""
    data = bytearray(_write_archive([b"x"]))
    n_log2_offset = len(b"INNOVABK1") + 1 + 16  # magic + versiya + tuz
    data[n_log2_offset] = 200
    with pytest.raises(BackupCorruptError):
        _read_all(bytes(data))


def test_zero_scrypt_r_in_header_is_rejected():
    data = bytearray(_write_archive([b"x"]))
    r_offset = len(b"INNOVABK1") + 1 + 16 + 1
    data[r_offset] = 0
    with pytest.raises(BackupCorruptError):
        _read_all(bytes(data))


def test_normal_archive_ends_cleanly_without_raising():
    # Haqiqiy oxirga yetgach, generator tinch holda tugashi kerak (xatosiz).
    data = _write_archive([b"ok"])
    assert _read_all(data) == [b"ok"]


def test_swapped_blocks_are_detected_as_corrupt():
    chunks = [b"1" * (1024 * 1024), b"2" * (1024 * 1024), b"3" * 10]
    data = bytearray(_write_archive(chunks))
    # Sarlavha uzunligini tekshirmay, tana ichidagi ikki blokni joy almashtiramiz —
    # eng oson yo'l: yozishni ikki marta boshqa tartibda qilib, natijalarni taqqoslash
    # o'rniga — bu yerda shunchaki butun faylni teskari tartibda oxirgi N baytni
    # boshqa joyga olib o'tamiz, bu GCM tag/AAD hisoblagichini buzadi.
    mid = len(data) // 2
    data[mid:], data[:mid] = data[:mid], data[mid:]
    with pytest.raises(BackupCorruptError):
        _read_all(bytes(data))


def test_rechunk_produces_exact_sizes_except_last():
    pieces = [b"a" * 3, b"b" * 3, b"c" * 3, b"d" * 1]
    out = list(rechunk(pieces, size=5))
    assert out == [b"aaabb", b"bcccd"]
    assert b"".join(out) == b"".join(pieces)


def test_rechunk_empty_source_yields_nothing():
    assert list(rechunk([], size=5)) == []


def test_large_stream_round_trips_across_many_chunk_boundaries():
    chunks = [bytes([i % 256]) * (1024 * 1024) for i in range(3)]
    data = _write_archive(chunks)
    assert b"".join(_read_all(data)) == b"".join(chunks)


def test_sha256_is_deterministic_for_same_input_and_keys():
    buf1, buf2 = io.BytesIO(), io.BytesIO()
    salt, nonce = b"s" * 16, b"n" * 12
    w1 = ArchiveWriter(buf1, PASSPHRASE, salt=salt, base_nonce=nonce)
    w1.write_stream([b"abc"])
    w2 = ArchiveWriter(buf2, PASSPHRASE, salt=salt, base_nonce=nonce)
    w2.write_stream([b"abc"])
    assert w1.sha256() == w2.sha256()
    assert buf1.getvalue() == buf2.getvalue()
