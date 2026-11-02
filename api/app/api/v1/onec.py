"""M3b §5 «1C» — tayyor namunalar (BSL modullar + qo'llanmalar) ro'yxati va yuklab olish (admin).

Manba: `app/resources/onec/manifest.json` (`[{name, title}]`). Yuklab olish faqat manifestdagi nom va
katalog ichidagi fayl (yo'l aylanib o'tish — 404). Manifest yo'q/buzuq → bo'sh ro'yxat.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import require_access
from app.core.errors import ApiError
from app.db.models import User
from app.schemas_crm import OneCSample

router = APIRouter(prefix="/integrations/1c", tags=["integrations"])
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "resources" / "onec"
MEDIA_TYPES = {".bsl": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8"}


def load_manifest(directory: Path) -> list[OneCSample]:
    try:
        raw = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [OneCSample(name=str(i["name"]), title=str(i.get("title") or i["name"]))
            for i in items if isinstance(i, dict) and i.get("name")]


def sample_path(directory: Path, name: str) -> Path:
    """Manifestda bor VA haqiqiy yo'li aynan katalog ichida bo'lgan fayl; aks holda 404."""
    known = {s.name for s in load_manifest(directory)}
    base = directory.resolve()
    path = (base / name).resolve()
    if name not in known or path.parent != base or not path.is_file():
        raise ApiError(404, "not_found", "Namuna topilmadi")
    return path


@router.get("/samples")
async def list_samples(_: User = Depends(require_access)) -> dict:
    return {"items": load_manifest(SAMPLES_DIR)}


@router.get("/samples/{name}")
async def download_sample(name: str, _: User = Depends(require_access)) -> FileResponse:
    path = sample_path(SAMPLES_DIR, name)
    return FileResponse(path, filename=path.name,
                        media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))
