"""M5a apply/report endpointlari — soxta sessiya bilan tekshiruv tartibi (422/404/409/202) va CSV."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import migration as mg
from app.core.errors import ApiError
from app.schemas_migration import ApplyOptionsIn, ApplyPayload
from app.services.fpbx.apply_plan import PlanStaleError
from tests.test_migration_v1_unit import USER, _job, _plan_item, _Session

_READY = SimpleNamespace(backup={"passphrase_enc": "x"})


class _Lock:
    def __init__(self) -> None:
        self.released = 0

    async def release(self) -> None:
        self.released += 1


@pytest.fixture
def wired(monkeypatch):
    state: dict = {"job": _job(status="analyzed", plan={"items": [_plan_item()]}), "lock": _Lock(), "spawned": [],
                   "fresh_error": None}

    async def scoped(_session, _model, _tenant_id, _job_id, **_kw):
        if state["job"] is None:
            raise ApiError(404, "not_found", "Ish topilmadi")
        return state["job"]

    async def acquire(_engine):
        if state["lock"] is None:
            raise mg.JobAlreadyRunningError()
        return state["lock"]

    async def analyze(_path, _session, _tenant_id):
        return SimpleNamespace(items=[])

    def resolve(_stored, _fresh):
        if state["fresh_error"] is not None:
            raise state["fresh_error"]

    def spawn(coro):
        state["spawned"].append(coro)
        coro.close()

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", scoped)
    monkeypatch.setattr(mg, "try_acquire_job_lock", acquire)
    monkeypatch.setattr(mg.plan_mod, "analyze", analyze)
    monkeypatch.setattr(mg, "resolve_final_actions", resolve)
    monkeypatch.setattr(mg, "_spawn", spawn)
    return state


def _payload(confirm: str | None = "KOCHIRISH", rotate: bool = False) -> ApplyPayload:
    return ApplyPayload(confirm=confirm, options=ApplyOptionsIn(rotate_weak_secrets=rotate))


async def _call(payload: ApplyPayload, settings_row=_READY) -> SimpleNamespace:
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    out = await mg.apply_job_endpoint("j1", payload, session=session, user=USER, ami=None)
    return SimpleNamespace(out=out, session=session)


async def _error(payload: ApplyPayload, settings_row=_READY) -> tuple[int, str]:
    with pytest.raises(ApiError) as info:
        await _call(payload, settings_row)
    return info.value.status_code, info.value.code


@pytest.mark.asyncio
async def test_apply_accepted(wired) -> None:
    res = await _call(_payload(rotate=True))
    job = wired["job"]
    assert (job.status, job.progress, job.options) == ("applying", 0, {"rotate_weak_secrets": True})
    assert (res.out.item.status, res.session.commits, len(wired["spawned"])) == ("applying", 1, 1)
    assert wired["lock"].released == 0  # qulfni fon ishi bo'shatadi


@pytest.mark.asyncio
@pytest.mark.parametrize("confirm", [None, "", "kochirish", "KOCHIRISH "])
async def test_apply_requires_exact_confirm(wired, confirm) -> None:
    wired["job"] = None  # tasdiq 404'dan OLDIN tekshiriladi
    assert await _error(_payload(confirm)) == (422, "confirm_required")


@pytest.mark.asyncio
async def test_apply_not_found(wired) -> None:
    wired["job"] = None
    assert await _error(_payload()) == (404, "not_found")


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "plan"), [("uploaded", None), ("analyzed", None), ("ok", {"items": []}),
                                              ("applying", {"items": []})])
async def test_apply_requires_analyzed(wired, status, plan) -> None:
    wired["job"] = _job(status=status, plan=plan)
    assert await _error(_payload()) == (409, "job_not_analyzed")


@pytest.mark.asyncio
async def test_apply_requires_passphrase(wired) -> None:
    assert await _error(_payload(), settings_row=None) == (409, "passphrase_required")
    assert wired["job"].status == "analyzed"


@pytest.mark.asyncio
async def test_apply_job_running(wired) -> None:
    wired["lock"] = None
    assert await _error(_payload()) == (409, "job_running")


@pytest.mark.asyncio
async def test_apply_plan_stale_releases_lock(wired) -> None:
    wired["fresh_error"] = PlanStaleError("eski")
    assert await _error(_payload()) == (409, "plan_stale")
    assert (wired["lock"].released, wired["job"].status, wired["spawned"]) == (1, "analyzed", [])


@pytest.mark.asyncio
async def test_apply_unexpected_error_releases_lock(wired) -> None:
    wired["fresh_error"] = RuntimeError("x")
    with pytest.raises(RuntimeError):
        await _call(_payload())
    assert wired["lock"].released == 1


@pytest.mark.asyncio
async def test_apply_bundle_missing(wired) -> None:
    wired["job"].bundle_path = None
    assert await _error(_payload()) == (409, "bundle_missing")
    assert wired["lock"].released == 1


class _RowsSession(_Session):
    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    async def execute(self, _query):
        return self._Rows(self.rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "outcome"), [("ok", "created"), ("failed", "created")])
async def test_report_csv(wired, status, outcome) -> None:
    items = [_plan_item(name="=Ali"), _plan_item(source_ref="users:102", number="102", action="skip", reason="x")]
    wired["job"] = _job(status=status, plan={"items": items}, result={"rotated": []})
    session = _RowsSession(rows=[("extension", "users:101", "uuid-1"), ("extension", "users:999", None)])
    resp = await mg.get_job_report("j1", session=session, user=USER)
    lines = resp.body.decode().splitlines()
    assert lines[0] == "kind,source_ref,name,number,action,reason,result,innova_id"
    assert lines[1] == f"extension,users:101,'=Ali,101,create,,{outcome},uuid-1"
    assert lines[2] == f"extension,users:102,101,102,skip,x,{'skipped' if status == 'ok' else 'not_applied'},"
    assert resp.media_type.startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="migration-j1.csv"'


@pytest.mark.asyncio
async def test_report_requires_plan(wired) -> None:
    wired["job"] = _job(status="uploaded", plan=None)
    with pytest.raises(ApiError) as info:
        await mg.get_job_report("j1", session=_RowsSession(), user=USER)
    assert info.value.status_code == 409


@pytest.mark.asyncio
async def test_spawn_keeps_reference_until_done() -> None:
    done = []

    async def work():
        done.append(1)

    mg._spawn(work())
    assert len(mg._BACKGROUND) == 1
    task = next(iter(mg._BACKGROUND))
    await task
    await mg.asyncio.sleep(0)
    assert done == [1] and not mg._BACKGROUND
