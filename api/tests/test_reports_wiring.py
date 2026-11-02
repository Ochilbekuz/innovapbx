"""`/reports/*` marshrutlarining `app.main.app`ga ulanganini tekshiradi
(DB/AMI SHART EMAS) — `test_app_wiring.py`dagi regressiya naqshi bilan BIR
XIL: `@router.get` dekoratori yordamchi funksiya ustiga EMAS, aniq handler
ustiga yozilganini tasdiqlaydi (FastAPI tuzog'i, m2b-contract.md §5)."""
from __future__ import annotations

from app.api.v1 import reports
from app.main import app


def test_reports_routes_registered_on_app():
    paths = {route.path for route in app.routes}
    assert "/api/v1/reports/summary" in paths
    assert "/api/v1/reports/queues" in paths
    assert "/api/v1/reports/agents" in paths
    assert "/api/v1/reports/hourly" in paths
    assert "/api/v1/reports/daily" in paths


def test_reports_get_routes_bound_to_handler_not_helper():
    expected = [
        ("/reports/summary", reports.get_summary),
        ("/reports/queues", reports.get_queues_report),
        ("/reports/agents", reports.get_agents_report),
        ("/reports/hourly", reports.get_hourly_report),
        ("/reports/daily", reports.get_daily_report),
    ]
    for path, handler in expected:
        get_routes = [
            r for r in reports.router.routes
            if getattr(r, "path", "") == path and "GET" in getattr(r, "methods", set())
        ]
        assert len(get_routes) == 1, path
        assert get_routes[0].endpoint is handler, path
