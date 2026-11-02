"""`app/services/maintenance.py` — ochiq yo'llar ro'yxati va middleware
(m4b-contract.md §0: "boshqa API so'rovlari 503 maintenance, /healthz va
/backups/jobs/{id} ochiq")."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import maintenance


def teardown_function() -> None:
    maintenance.state.enabled = False


@pytest.mark.parametrize("method,path,expected", [
    ("GET", "/healthz", True),
    ("GET", "/api/v1/backups/jobs/abc-123", True),
    ("POST", "/healthz", False),
    ("POST", "/api/v1/backups/jobs/abc-123", False),
    ("GET", "/api/v1/backups", False),
    ("GET", "/api/v1/backups/jobs/abc/extra", False),
])
def test_is_open_path(method, path, expected):
    assert maintenance.is_open_path(method, path) is expected


@pytest.mark.asyncio
async def test_middleware_passes_through_when_disabled():
    maintenance.state.enabled = False
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/v1/backups"))

    async def call_next(_request):
        return "ok"

    assert await maintenance.maintenance_middleware(request, call_next) == "ok"


@pytest.mark.asyncio
async def test_middleware_blocks_closed_path_when_enabled():
    maintenance.state.enabled = True
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/v1/backups"))

    async def call_next(_request):
        raise AssertionError("call_next chaqirilmasin")

    response = await maintenance.maintenance_middleware(request, call_next)
    assert response.status_code == 503
    import json
    assert json.loads(response.body)["error"]["code"] == "maintenance"


@pytest.mark.asyncio
async def test_middleware_allows_open_path_when_enabled():
    maintenance.state.enabled = True
    request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/healthz"))

    async def call_next(_request):
        return "ok"

    assert await maintenance.maintenance_middleware(request, call_next) == "ok"
