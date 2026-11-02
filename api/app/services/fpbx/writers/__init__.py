"""M5a apply — reja elementlarini Innova jadvallariga yozish (m5a-contract.md §0).
Ikki o'tish: (1) barcha yaratiladigan call_target'li obyektlar uchun maqsad
ochiladi (oldinga havolalar — masalan ichki raqam `no_answer` -> pochta qutisi —
qaysi tartibda yozilishidan qat'i nazar hal bo'ladi); (2) `KIND_ORDER` bo'yicha
satellitlar yoziladi, har biriga `migration_items` qatori. Commit YO'Q."""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from app.db.models import MigrationItem
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import SkipItem, WriteCtx, WriteError, entry_key
from app.services.fpbx.writers.endpoints import write_extension, write_trunk, write_voicemail
from app.services.fpbx.writers.groups import (
    write_announcement,
    write_conference,
    write_ivr,
    write_queue,
    write_ring_group,
)
from app.services.fpbx.writers.media import write_audio, write_moh
from app.services.fpbx.writers.routes import (
    write_blacklist,
    write_feature_code,
    write_inbound_route,
    write_outbound_route,
)
from app.services.fpbx.writers.schedule import write_holiday, write_time_condition, write_time_group
from app.services.target_resolution import create_target

__all__ = ["KIND_ORDER", "TestFailError", "WriteCtx", "WriteError", "maybe_test_fail", "write_entries"]

Writer = Callable[[WriteCtx, Entry], Awaitable[str | None]]

WRITERS: dict[str, Writer] = {
    "audio": write_audio, "moh": write_moh, "time_group": write_time_group, "holiday": write_holiday,
    "extension": write_extension, "voicemail": write_voicemail, "trunk": write_trunk,
    "ring_group": write_ring_group, "queue": write_queue, "conference": write_conference,
    "announcement": write_announcement, "ivr": write_ivr, "time_condition": write_time_condition,
    "inbound_route": write_inbound_route, "outbound_route": write_outbound_route,
    "blacklist": write_blacklist, "feature_code": write_feature_code,
}
KIND_ORDER: tuple[str, ...] = tuple(WRITERS)
TARGET_KINDS = frozenset({"extension", "voicemail", "ring_group", "queue", "conference",
                          "announcement", "ivr", "time_condition"})
TEST_FAIL_ENV = "INNOVA_TEST_FAIL_AT"


class TestFailError(Exception):
    """`INNOVA_TEST_FAIL_AT=<bosqich>` — atomarlik isboti uchun ataylab xato."""

    __test__ = False  # pytest buni test klassi deb yig'masin

    code = "test_fail"


def maybe_test_fail(stage: str) -> None:
    if os.environ.get(TEST_FAIL_ENV, "").strip() == stage:
        raise TestFailError(f"Sinov: '{stage}' bosqichida ataylab xato")


def _label(entry: Entry) -> str:
    if entry.kind == "extension":
        return f"{entry.number} · {entry.name}"
    if entry.kind == "voicemail":
        return f"Ovozli pochta · {entry.payload.get('mailbox') or entry.number}"
    return entry.name


async def _precreate_targets(ctx: WriteCtx, entries: list[Entry]) -> None:
    for entry in entries:
        if entry.kind in TARGET_KINDS:
            target = await create_target(ctx.session, ctx.tenant_id, entry.kind, _label(entry))
            ctx.targets[entry_key(entry)] = str(target.id)


async def _write_one(ctx: WriteCtx, entry: Entry) -> bool:
    try:
        innova_id = await WRITERS[entry.kind](ctx, entry)
    except SkipItem as exc:
        ctx.warn(entry.source_ref, exc.code, exc.message)
        ctx.skipped[entry_key(entry)] = exc.code
        return False
    if innova_id is not None:
        ctx.entities[entry_key(entry)] = innova_id
    ctx.session.add(MigrationItem(job_id=ctx.job_id, tenant_id=ctx.tenant_id, kind=entry.kind,
                                  source_ref=entry.source_ref, innova_kind=entry.kind, innova_id=innova_id))
    ctx.created[entry.kind] = ctx.created.get(entry.kind, 0) + 1
    return True


async def write_entries(ctx: WriteCtx, entries: list[Entry]) -> int:
    """Yaratiladigan elementlarni yozadi; yaratilmay qolganlar (SkipItem) sonini qaytaradi.
    `routes` sinov nuqtasi — kiruvchi/chiquvchi yo'nalishlar yozilgandan keyin."""
    await _precreate_targets(ctx, entries)
    not_created = 0
    for kind in KIND_ORDER:
        for entry in (e for e in entries if e.kind == kind):
            not_created += 0 if await _write_one(ctx, entry) else 1
        if kind == "outbound_route":
            await ctx.session.flush()
            maybe_test_fail("routes")
    await ctx.session.flush()
    return not_created
