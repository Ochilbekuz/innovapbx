"""INNOVABK1 — oqimli shifrlangan zaxira formati (m4b-contract.md §0).

Sarlavha: magic(9) + versiya(1) + scrypt tuz(16) + scrypt n_log2/r/p(1+1+1) + asosiy
nonce(12) + parol tekshiruv bloki (uzunlik + shifr matn). Tekshiruv bloki parolni
DARHOL tasdiqlaydi — shu sabab noto'g'ri parol `BadPassphraseError` (422
`bad_passphrase`) bilan, tana buzilishi esa `BackupCorruptError` (422
`backup_corrupt`) bilan ALOHIDA aniqlanadi.

Tana — ketma-ket bloklar (sukut 1 MiB, oxirgisi kichikroq bo'lishi mumkin), har biri
AES-256-GCM: nonce = asosiy_nonce[:4] ‖ hisoblagich(8 bayt KE), AAD = hisoblagich(8
bayt KE) ‖ oxirgi_bayroq(1 bayt). Bitta bayt o'zgartirilsa, bloklar almashtirilsa
(AAD'dagi hisoblagich mos kelmaydi) yoki oxiri kesilsa (oxirgi bayroqli blok hech
qachon kelmaydi) — bari `BackupCorruptError`.

Butun modul SOF (fayl tizim/DB bilan ishlamaydi) — faqat berilgan ikkilik oqim
ob'ektlariga yozadi/o'qiydi, shu sabab to'liq xotirasiz (GB'lik arxivlar) sinaladi.
"""
from __future__ import annotations

import hashlib
import os
import struct
from collections.abc import Iterable, Iterator
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"INNOVABK1"
VERSION = 1
CHUNK_SIZE = 1024 * 1024

_SCRYPT_N_LOG2 = 15
_SCRYPT_R = 8
_SCRYPT_P = 1
# Sarlavhadagi n_log2/r/p HAR BIRI 1 bayt (0-255) -- hujumchi arxiv yasasa
# (masalan n_log2=255 -> N=2**255) `Scrypt().derive()` xotira/CPU'ni abadiy band
# qilib DoS beradi. Haqiqiy arxivlar doim yuqoridagi SUKUT qiymatlarni yozadi --
# chegara shundan SEZILARLI yuqori (kelgusi parametr kuchaytirishga joy qoldirish
# uchun), lekin DoS qila olmaydigan darajada (N=2**20, r=16 -> taxminan 1 GiB).
_MAX_SCRYPT_N_LOG2 = 20
_MAX_SCRYPT_R = 16
_MAX_SCRYPT_P = 16
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32
_CHECK_PLAINTEXT = b"INNOVA-BACKUP-OK"
_CHECK_AAD = b"check"
_CHECK_COUNTER = (1 << 64) - 1  # tana hisoblagichlari bilan hech qachon to'qnashmaydi


class BackupFormatError(Exception):
    """INNOVABK1 formati xatosi — asoschi."""


class BadPassphraseError(BackupFormatError):
    """Parol tekshiruv bloki ochilmadi — parol noto'g'ri."""


class BackupCorruptError(BackupFormatError):
    """Tana bloki buzilgan, tartib almashtirilgan yoki fayl kesilgan."""


def derive_key(passphrase: str, salt: bytes, n_log2: int = _SCRYPT_N_LOG2,
                r: int = _SCRYPT_R, p: int = _SCRYPT_P) -> bytes:
    kdf = Scrypt(salt=salt, length=_KEY_LEN, n=2 ** n_log2, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def _nonce_for(base_nonce: bytes, counter: int) -> bytes:
    return base_nonce[:4] + struct.pack(">Q", counter)


def rechunk(source: Iterable[bytes], size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Ixtiyoriy o'lchamdagi bo'laklar oqimini ANIQ `size` (oxirgisi kichikroq)
    bo'laklarga qayta bo'ladi — manba, masalan, `tarfile` chiqishi bo'lishi mumkin."""
    buf = bytearray()
    for piece in source:
        buf += piece
        while len(buf) >= size:
            yield bytes(buf[:size])
            del buf[:size]
    if buf:
        yield bytes(buf)


class ArchiveWriter:
    """Berilgan ikkilik faylga (`fh`) INNOVABK1 arxivini yozadi."""

    def __init__(self, fh: BinaryIO, passphrase: str, *,
                 salt: bytes | None = None, base_nonce: bytes | None = None) -> None:
        self._fh = fh
        self._salt = salt or os.urandom(_SALT_LEN)
        self._base_nonce = base_nonce or os.urandom(_NONCE_LEN)
        self._aead = AESGCM(derive_key(passphrase, self._salt))
        self._counter = 0
        self._finished = False
        self._digest = hashlib.sha256()
        self._write_header()

    def _write(self, data: bytes) -> None:
        self._fh.write(data)
        self._digest.update(data)

    def _write_header(self) -> None:
        check_ct = self._aead.encrypt(_nonce_for(self._base_nonce, _CHECK_COUNTER),
                                       _CHECK_PLAINTEXT, _CHECK_AAD)
        header = (MAGIC + bytes([VERSION]) + self._salt
                  + bytes([_SCRYPT_N_LOG2, _SCRYPT_R, _SCRYPT_P]) + self._base_nonce
                  + struct.pack(">H", len(check_ct)) + check_ct)
        self._write(header)

    def write_chunk(self, data: bytes, *, last: bool) -> None:
        if self._finished:
            raise BackupFormatError("yopilgan arxivga yozib bo'lmaydi")
        aad = struct.pack(">Q", self._counter) + (b"\x01" if last else b"\x00")
        ct = self._aead.encrypt(_nonce_for(self._base_nonce, self._counter), data, aad)
        self._write(struct.pack(">I", len(ct)) + ct)
        self._counter += 1
        self._finished = last

    def write_stream(self, chunks: Iterable[bytes]) -> None:
        """`chunks` — ochiq matn bo'laklari ketma-ketligi; oxirgisi avtomatik
        `last=True` bilan belgilanadi (bo'sh oqim bo'lsa ham bitta bo'sh blok yoziladi,
        shu bilan arxiv har doim kamida bitta — oxirgi — blokka ega bo'ladi)."""
        pending: bytes | None = None
        for chunk in chunks:
            if pending is not None:
                self.write_chunk(pending, last=False)
            pending = chunk
        self.write_chunk(pending if pending is not None else b"", last=True)

    def sha256(self) -> str:
        return self._digest.hexdigest()


class ArchiveReader:
    """Berilgan ikkilik fayldan (`fh`) INNOVABK1 arxivini ochiq matn bo'laklari
    oqimiga deshifrlaydi. `read_chunks()` generatori tugamaguncha arxiv to'liq
    tekshirilgan deb hisoblanmaydi."""

    def __init__(self, fh: BinaryIO, passphrase: str) -> None:
        self._fh = fh
        self._read_header(passphrase)

    def _read_exact(self, n: int) -> bytes:
        data = self._fh.read(n)
        if len(data) != n:
            raise BackupCorruptError("fayl kutilganidan qisqa")
        return data

    def _read_header(self, passphrase: str) -> None:
        if self._read_exact(len(MAGIC)) != MAGIC:
            raise BackupCorruptError("INNOVABK1 sarlavhasi topilmadi")
        version = self._read_exact(1)[0]
        if version != VERSION:
            raise BackupCorruptError(f"qo'llab-quvvatlanmaydigan versiya: {version}")
        salt = self._read_exact(_SALT_LEN)
        n_log2, r, p = self._read_exact(3)
        if not (1 <= n_log2 <= _MAX_SCRYPT_N_LOG2 and 1 <= r <= _MAX_SCRYPT_R and 1 <= p <= _MAX_SCRYPT_P):
            raise BackupCorruptError("scrypt parametrlari ruxsat etilgan chegaradan tashqarida")
        base_nonce = self._read_exact(_NONCE_LEN)
        (check_len,) = struct.unpack(">H", self._read_exact(2))
        check_ct = self._read_exact(check_len)
        aead = AESGCM(derive_key(passphrase, salt, n_log2, r, p))
        self._verify_passphrase(aead, base_nonce, check_ct)
        self._aead = aead
        self._base_nonce = base_nonce
        self._counter = 0
        self._finished = False

    @staticmethod
    def _verify_passphrase(aead: AESGCM, base_nonce: bytes, check_ct: bytes) -> None:
        try:
            plain = aead.decrypt(_nonce_for(base_nonce, _CHECK_COUNTER), check_ct, _CHECK_AAD)
        except InvalidTag as exc:
            raise BadPassphraseError("parol noto'g'ri") from exc
        if plain != _CHECK_PLAINTEXT:
            raise BadPassphraseError("parol noto'g'ri")

    def _decrypt_frame(self, ct: bytes) -> tuple[bytes, bool]:
        for last_flag in (False, True):
            aad = struct.pack(">Q", self._counter) + (b"\x01" if last_flag else b"\x00")
            try:
                plain = self._aead.decrypt(_nonce_for(self._base_nonce, self._counter), ct, aad)
            except InvalidTag:
                continue
            return plain, last_flag
        raise BackupCorruptError(f"blok #{self._counter} buzilgan yoki o'rni almashtirilgan")

    def read_chunks(self) -> Iterator[bytes]:
        while True:
            length_bytes = self._fh.read(4)
            if not length_bytes:
                if not self._finished:
                    raise BackupCorruptError("arxiv kesilgan — oxirgi blok topilmadi")
                return
            if len(length_bytes) != 4:
                raise BackupCorruptError("blok uzunligi buzilgan")
            (length,) = struct.unpack(">I", length_bytes)
            plain, last = self._decrypt_frame(self._read_exact(length))
            self._counter += 1
            self._finished = last
            yield plain
