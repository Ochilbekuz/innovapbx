"""M5a — to'plam (`.tar.gz`) qabul qilishning umumiy yarmi: xavfsiz ochish +
`meta.json`dan `source_meta` qurish (m5a-contract.md §0: "ikki yo'l (yuklash/SSH) bir
xil kod yo'liga tushadi"). `app/api/v1/migration.py::upload_bundle`dagi inline mantiq
BILAN BIR XIL `bundle.py` chaqiruvlari — ATAYLAB o'sha faylga tegilmagan (parallel ish,
`/tmp/backend-ssh.txt`), shu sabab bu yerda ALOHIDA, lekin bir xil yordamchi (`bundle.py`)
dan foydalanadigan funksiya: `app/services/fpbx/ssh_fetch.py` shuni chaqiradi."""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.fpbx import bundle as bundle_mod


def extract_and_read_meta(archive_path: Path, work_dir: Path) -> tuple[Path, dict]:
    """`archive_path` (`work_dir` ICHIDA bo'lishi tavsiya etiladi, lekin shart emas) ni
    `bundle.extract_bundle` bilan xavfsiz ochadi va `meta.json`ni o'qiydi. Xato bo'lsa
    `bundle_mod.BundleInvalidError` chaqiruvchiga ko'tariladi (u 422 `bundle_invalid`ga
    yoki fon-vazifa `error.code`ga aylantiradi) — `work_dir` BU YERDA o'chirilmaydi."""
    extracted_dir = work_dir / "extracted"
    max_bytes = settings.migration_upload_max_bytes
    bundle_mod.extract_bundle(archive_path, extracted_dir, max_total_bytes=max_bytes)
    bundle_root = bundle_mod.find_bundle_root(extracted_dir)
    meta = bundle_mod.read_meta(bundle_root)
    return bundle_root, meta


def build_source_meta(meta: dict, *, size_bytes: int, extra: dict | None = None) -> dict:
    """`upload_bundle`dagi `source_meta` qurilishi BILAN BIR XIL maydonlar (`app/api/v1/
    migration.py` §«yuklash»). `extra` — ssh yo'lida masalan `host` (ulanish parametri,
    `meta.json`dagi `host`dan ustun turadi, chunki ulanish manzili haqiqiyroq)."""
    base = {
        "size_bytes": size_bytes, "host": meta.get("host"),
        "freepbx_version": meta.get("freepbx_version"), "asterisk_version": meta.get("asterisk_version"),
        "created_at": meta.get("created_at"),
    }
    base.update(extra or {})
    return base


def place_bundle_dir(job_id: str, work_dir: Path, bundle_root: Path) -> Path:
    """`work_dir`ni doimiy manzilga (`migrations_dir/<job_id>`) ko'chiradi — `upload_bundle`
    bilan BIR XIL qolip — va yakuniy `bundle_path`ni qaytaradi."""
    migrations_dir = Path(settings.migrations_dir)
    final_dir = migrations_dir / job_id
    work_dir.rename(final_dir)
    return final_dir / bundle_root.relative_to(work_dir)
