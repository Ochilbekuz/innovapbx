"""`/users/*` va `/me/*` marshrutlarining `app.main.app`ga ulanganini
tekshiradi (DB/AMI SHART EMAS) — `test_app_wiring.py`/`test_reports_wiring.py`
naqshi bilan BIR XIL: `@router` dekoratori yordamchi funksiya ustiga EMAS,
aniq handler ustiga yozilganini tasdiqlaydi (FastAPI tuzog'i,
m2b-contract.md §3/§4)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1 import me, users
from app.main import app


def test_users_and_me_routes_registered_on_app():
    paths = {route.path for route in app.routes}
    assert "/api/v1/users" in paths
    assert "/api/v1/users/{user_id}" in paths
    assert "/api/v1/auth/change-password" in paths
    assert "/api/v1/me/overview" in paths
    assert "/api/v1/me/extension" in paths
    assert "/api/v1/me/queues/{queue_id}/{action}" in paths
    assert "/api/v1/me/calls" in paths
    assert "/api/v1/me/voicemail" in paths
    assert "/api/v1/me/voicemail/{msg:path}/audio" in paths
    assert "/api/v1/me/voicemail/{msg:path}/heard" in paths
    assert "/api/v1/me/voicemail/{msg:path}" in paths


def test_users_routes_bound_to_handler_not_helper():
    expected = [
        ("/users", "GET", users.list_users),
        ("/users", "POST", users.create_user),
        ("/users/{user_id}", "PATCH", users.update_user),
        ("/users/{user_id}", "DELETE", users.delete_user),
    ]
    for path, method, handler in expected:
        routes = [r for r in users.router.routes if getattr(r, "path", "") == path
                  and method in getattr(r, "methods", set())]
        assert len(routes) == 1, (path, method)
        assert routes[0].endpoint is handler, (path, method)


def test_me_routes_bound_to_handler_not_helper():
    expected = [
        ("/me/overview", "GET", me.my_overview),
        ("/me/extension", "PATCH", me.patch_my_extension),
        ("/me/queues/{queue_id}/{action}", "POST", me.act_on_my_queue),
        ("/me/calls", "GET", me.my_calls),
        ("/me/voicemail", "GET", me.my_voicemail),
        ("/me/voicemail/{msg:path}/audio", "GET", me.my_voicemail_audio),
        ("/me/voicemail/{msg:path}/heard", "POST", me.my_voicemail_heard),
        ("/me/voicemail/{msg:path}", "DELETE", me.my_voicemail_delete),
    ]
    for path, method, handler in expected:
        routes = [r for r in me.router.routes if getattr(r, "path", "") == path
                  and method in getattr(r, "methods", set())]
        assert len(routes) == 1, (path, method)
        assert routes[0].endpoint is handler, (path, method)


def test_users_endpoint_reachable_without_db_returns_401():
    """DB ulanmagan — 401 (autentifikatsiya yo'q) YETARLI dalil: marshrut
    routerga yetib boradi (`test_app_wiring.py` bilan bir xil mantiq)."""
    client = TestClient(app)
    r = client.get("/api/v1/users")
    assert r.status_code == 401
    r = client.get("/api/v1/me/overview")
    assert r.status_code == 401
