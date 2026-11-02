"""Commit-confirm holati — m8-network-contract.md bo'lim 2: `pending.json`
(host faylida, `/var/lib/innova/netd/pending.json`) — qayta ishga tushganda
DARHOL qaytarish uchun saqlanadi."""
from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.netd.executor import Executor


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class Snapshot:
    interfaces: str | None
    resolv_conf: str | None
    hostname: str | None
    hosts: str | None


@dataclass(frozen=True)
class PendingRecord:
    id: str
    applied_at: datetime
    expires_at: datetime
    summary: list[str]
    snapshot: Snapshot
    meta: dict = field(default_factory=dict)

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict:
        d = asdict(self)
        d["applied_at"] = _iso(self.applied_at)
        d["expires_at"] = _iso(self.expires_at)
        return d

    @staticmethod
    def from_dict(d: dict) -> PendingRecord:
        return PendingRecord(
            id=d["id"], applied_at=_parse_iso(d["applied_at"]), expires_at=_parse_iso(d["expires_at"]),
            summary=d["summary"], snapshot=Snapshot(**d["snapshot"]), meta=d.get("meta", {}),
        )


def load_pending(executor: Executor, path: str) -> PendingRecord | None:
    raw = executor.read_text(path)
    if raw is None or not raw.strip():
        return None
    return PendingRecord.from_dict(json.loads(raw))


def save_pending(executor: Executor, path: str, record: PendingRecord) -> None:
    executor.write_text_atomic(path, json.dumps(record.to_dict(), indent=2) + "\n", mode=0o600)


def clear_pending(executor: Executor, path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(executor.path(path))
