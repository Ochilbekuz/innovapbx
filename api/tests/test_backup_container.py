"""`app/services/backup_container.py` — uzunlik-prefiksli freymlar, to'liq sof."""
from __future__ import annotations

import hashlib

import pytest

from app.services.backup_container import (
    FrameReader,
    frame_header,
    iter_bytes_frame,
    iter_file_frame,
)
from app.services.backup_format import BackupCorruptError


def test_frame_header_encodes_name_and_size():
    header = frame_header("db.dump", 1234)
    assert header[0] == len("db.dump")
    assert header[1:1 + len("db.dump")] == b"db.dump"
    assert header[-8:] == (1234).to_bytes(8, "big")


def test_frame_header_rejects_overlong_name():
    with pytest.raises(ValueError):
        frame_header("x" * 256, 1)


def _as_chunks(*frames_bytes: bytes, piece: int = 7):
    """Barcha freym baytlarini BIRLASHTIRIB, kichik, teng bo'lmagan bo'laklarga
    qirqadi — o'qish tomoni freym chegaralarini o'zi hisoblaydi, tashqi
    bo'lak chegaralariga bog'liq bo'lmasligi SHART."""
    blob = b"".join(frames_bytes)
    return (blob[i:i + piece] for i in range(0, len(blob), piece))


def test_round_trip_single_bytes_frame():
    frame = b"".join(iter_bytes_frame("manifest.json", b'{"a":1}'))
    reader = FrameReader(_as_chunks(frame))
    header = reader.read_header()
    assert header == ("manifest.json", len(b'{"a":1}'))
    assert reader.read_exact(header[1]) == b'{"a":1}'
    assert reader.read_header() is None


def test_round_trip_multiple_frames_in_order():
    frames = b"".join(iter_bytes_frame("manifest.json", b"abc")) + \
        b"".join(iter_bytes_frame("db_key.enc", b"xyz12345"))
    reader = FrameReader(_as_chunks(frames))

    name, size = reader.read_header()
    assert (name, size) == ("manifest.json", 3)
    assert reader.read_exact(size) == b"abc"

    name, size = reader.read_header()
    assert (name, size) == ("db_key.enc", 8)
    assert reader.read_exact(size) == b"xyz12345"

    assert reader.read_header() is None


def test_read_stream_yields_bounded_pieces_and_full_content():
    payload = b"0123456789" * 1000  # 10 KB
    frame = b"".join(iter_bytes_frame("sounds.tar", payload))
    reader = FrameReader(_as_chunks(frame, piece=333))

    name, size = reader.read_header()
    assert (name, size) == ("sounds.tar", len(payload))
    collected = bytearray()
    for piece in reader.read_stream(size):
        assert len(piece) <= 333 * 2  # buferlash tufayli biroz kattaroq bo'lishi mumkin, lekin CHAKLANGAN
        collected += piece
    assert bytes(collected) == payload


def test_empty_bytes_frame_round_trip():
    frame = b"".join(iter_bytes_frame("empty.part", b""))
    reader = FrameReader(_as_chunks(frame))
    name, size = reader.read_header()
    assert (name, size) == ("empty.part", 0)
    assert reader.read_exact(0) == b""


def test_truncated_frame_header_raises_corrupt():
    frame = b"".join(iter_bytes_frame("manifest.json", b"abcdef"))
    truncated = frame[:3]  # sarlavha o'rtasida kesilgan
    reader = FrameReader(_as_chunks(truncated))
    with pytest.raises(BackupCorruptError):
        reader.read_header()


def test_truncated_frame_body_raises_corrupt():
    frame = b"".join(iter_bytes_frame("manifest.json", b"abcdef"))
    truncated = frame[:-2]  # tana oxiridan kesilgan
    reader = FrameReader(_as_chunks(truncated))
    name, size = reader.read_header()
    assert (name, size) == ("manifest.json", 6)
    with pytest.raises(BackupCorruptError):
        reader.read_exact(size)


def test_iter_file_frame_streams_file_content(tmp_path):
    path = tmp_path / "db.dump"
    content = hashlib.sha256(b"seed").digest() * 4096  # ~128 KB
    path.write_bytes(content)
    frame = b"".join(iter_file_frame("db.dump", path, chunk_size=1024))
    reader = FrameReader(_as_chunks(frame, piece=500))
    name, size = reader.read_header()
    assert (name, size) == ("db.dump", len(content))
    assert reader.read_exact(size) == content


def test_clean_end_of_stream_after_last_frame_vs_mid_frame_distinguished():
    """Freym chegarasida tugash — `None` (normal); freym ICHIDA tugash — xato."""
    clean = b"".join(iter_bytes_frame("a", b"1"))
    reader = FrameReader(_as_chunks(clean))
    reader.read_header()
    reader.read_exact(1)
    assert reader.read_header() is None  # endi hech narsa yo'q — toza oxiri
