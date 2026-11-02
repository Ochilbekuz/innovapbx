"""Zaxira konteyneri — `ArchiveWriter`/`ArchiveReader` (`backup_format.py`) ICHIDAGI
oddiy, uzunlik-prefiksli freymlar ketma-ketligi (m4b-contract.md §0/§1).

Nega ichma-ich `tarfile` EMAS: manifest BARCHA qismlarning hajmi/sha256'ini bilishi
kerak, lekin bu qiymatlar faqat qismlar TO'LIQ yozilgandan KEYIN ma'lum bo'ladi —
shu sabab avval har bir qism (DB dump, har fayl-komponent uchun alohida `.tar`)
vaqtinchalik papkaga TO'LIQ yoziladi (hajm/sha256 hisoblab olinadi), SO'NGRA
manifest BIRINCHI freym sifatida (qismlardan OLDIN) yoziladi — bitta o'tishda
(single-pass) oqimli o'qish/tekshirish mumkin bo'lishi uchun (`inspect`/`restore`
butun arxivni xotiraga yuklamasdan, freymma-freym o'qiydi).

Freym shakli: `name_len(1) + name(utf-8) + size(8, katta-endian) + <size> bayt`."""
from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

from app.services.backup_format import BackupCorruptError

_DEFAULT_CHUNK = 1 << 20  # 1 MiB — fayl o'qishda xotiraga bir vaqtda shuncha yuklanadi


def frame_header(name: str, size: int) -> bytes:
    name_bytes = name.encode("utf-8")
    if len(name_bytes) > 255:
        raise ValueError("freym nomi juda uzun (>255 bayt)")
    return bytes([len(name_bytes)]) + name_bytes + struct.pack(">Q", size)


def iter_bytes_frame(name: str, data: bytes) -> Iterator[bytes]:
    yield frame_header(name, len(data))
    if data:
        yield data


def iter_file_frame(name: str, path: Path, *, chunk_size: int = _DEFAULT_CHUNK) -> Iterator[bytes]:
    size = path.stat().st_size
    yield frame_header(name, size)
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk_size)
            if not data:
                return
            yield data


class ChunkReader:
    """`ArchiveReader.read_chunks()` kabi ixtiyoriy o'lchamdagi bo'laklar generatorini
    aniq bayt-sonli o'qishlarga aylantiradi (buferlash bilan)."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._buf = bytearray()

    def _fill(self, n: int) -> None:
        while len(self._buf) < n:
            try:
                self._buf += next(self._chunks)
            except StopIteration as exc:
                raise BackupCorruptError("konteyner kutilganidan qisqa") from exc

    def read_exact(self, n: int) -> bytes:
        self._fill(n)
        data = bytes(self._buf[:n])
        del self._buf[:n]
        return data

    def try_read_exact(self, n: int) -> bytes | None:
        """Agar oqim ANIQ shu yerda (freym chegarasida) tugagan bo'lsa `None`;
        aks holda `read_exact(n)` (etarli bo'lmasa — `BackupCorruptError`, chunki
        bu holda freym O'RTASIDA uzilgan, bu haqiqiy buzilish)."""
        if not self._buf:
            try:
                self._buf += next(self._chunks)
            except StopIteration:
                return None
        return self.read_exact(n)

    def read_stream(self, n: int) -> Iterator[bytes]:
        """`n` baytni BOG'LANGAN (bounded) bo'laklarda chiqaradi — qabul qiluvchi
        (masalan diskka yozuvchi) hech qachon butun `n`ni bir martada xotirada
        ushlamaydi."""
        remaining = n
        while remaining > 0:
            if not self._buf:
                try:
                    self._buf += next(self._chunks)
                except StopIteration as exc:
                    raise BackupCorruptError("konteyner kutilganidan qisqa") from exc
            take = min(remaining, len(self._buf))
            data = bytes(self._buf[:take])
            del self._buf[:take]
            remaining -= take
            yield data


class FrameReader:
    """Konteynerni freymma-freym o'qiydi. Har `read_header()`dan keyin chaqiruvchi
    ANIQ `size` baytni (`read_exact`/`read_stream` orqali) iste'mol qilishi SHART —
    aks holda keyingi freym sarlavhasi noto'g'ri joydan o'qiladi."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._reader = ChunkReader(chunks)

    def read_header(self) -> tuple[str, int] | None:
        name_len_bytes = self._reader.try_read_exact(1)
        if name_len_bytes is None:
            return None
        name = self._reader.read_exact(name_len_bytes[0]).decode("utf-8")
        (size,) = struct.unpack(">Q", self._reader.read_exact(8))
        return name, size

    def read_exact(self, n: int) -> bytes:
        return self._reader.read_exact(n)

    def read_stream(self, n: int) -> Iterator[bytes]:
        return self._reader.read_stream(n)
