"""Yuklangan/SSH orqali olingan FreePBX eksport to'plamini (`.tar.gz`) xavfsiz ochish.

Python 3.12 `tarfile` o'rnatilgan `filter="data"` (PEP 706) yo'l o'tish/mutlaq yo'l/
ramziy havola himoyasini beradi (`app/services/restore_job.py`dagi M4b qolipi BILAN BIR
XIL) — bu yerga hajm-bombasi himoyasi (umumiy va bitta a'zo chegarasi) qo'shiladi."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

_MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
_EXPECTED_FORMAT = "INNOVA-FPBX-EXPORT/1"
_REQUIRED_META_FIELDS = ("format", "tables")


class BundleInvalidError(Exception):
    """Buzilgan/xavfli to'plam — router 422 `bundle_invalid`ga aylantiradi."""


def _check_members(tar: tarfile.TarFile, max_total_bytes: int) -> None:
    total = 0
    for member in tar.getmembers():
        if member.isdir():
            continue
        if not member.isfile():
            raise BundleInvalidError(f"qo'llab-quvvatlanmaydigan a'zo turi: {member.name}")
        if member.size > _MAX_MEMBER_BYTES:
            raise BundleInvalidError(f"a'zo juda katta: {member.name}")
        total += member.size
        if total > max_total_bytes:
            raise BundleInvalidError("to'plam hajmi chegaradan katta")


def _lock_down_permissions(dest_dir: Path) -> None:
    dest_dir.chmod(0o700)
    for path in dest_dir.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)


def extract_bundle(archive_path: Path, dest_dir: Path, *, max_total_bytes: int) -> None:
    """Xavfli/buzilgan to'plam -> `BundleInvalidError`. Muvaffaqiyatli bo'lsa `dest_dir`
    ichidagi hamma narsa 0700 (papka)/0600 (fayl) — boshqa foydalanuvchi o'qiy olmaydi."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.chmod(0o700)
    try:
        with tarfile.open(archive_path, mode="r:*") as tar:
            _check_members(tar, max_total_bytes)
            tar.extractall(dest_dir, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise BundleInvalidError(f"to'plam ochilmadi: {exc}") from exc
    _lock_down_permissions(dest_dir)


def find_bundle_root(dest_dir: Path) -> Path:
    """To'plam odatda bitta ichki papka ichida keladi (`fpbx-export-<host>-<vaqt>/...`)
    — `meta.json` qaysi papkada bo'lsa, shu ildiz hisoblanadi."""
    if (dest_dir / "meta.json").exists():
        return dest_dir
    candidates = [p for p in dest_dir.iterdir() if p.is_dir() and (p / "meta.json").exists()]
    if len(candidates) == 1:
        return candidates[0]
    raise BundleInvalidError("to'plam ildizi (meta.json) topilmadi")


def read_meta(bundle_root: Path) -> dict:
    meta_path = bundle_root / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BundleInvalidError(f"meta.json o'qilmadi: {exc}") from exc
    missing = [f for f in _REQUIRED_META_FIELDS if f not in meta]
    if missing:
        raise BundleInvalidError(f"meta.json maydonlari yo'q: {missing}")
    if meta.get("format") != _EXPECTED_FORMAT:
        raise BundleInvalidError(f"noma'lum format: {meta.get('format')}")
    return meta
