"""Ilova import/marshrut ulanishini tekshiradi — DB/AMI SHART EMAS.

Sabab: `update_inbound_route`ning `@router.patch` dekoratori refaktoring
paytida (CRAP/CC pasaytirish, helper funksiyalarga ajratish) xato joyga —
yordamchi funksiya ustiga — qolib ketgan edi. Buni na `pytest` (ilova
import qilinmagani uchun), na `crapper`/`dryer` (statik tahlil, routerni
ishga tushirmaydi) tutib bermadi — faqat Docker qayta qurilib, konteyner
ishga tushishga harakat qilganda (`fastapi.exceptions.FastAPIError`
startup'da) sinovda topildi. Shu klassdagi xatoni endi mahalliy (Docker'siz)
tutish uchun — ilovani import qilib, har bir marshrut to'g'ri funksiyaga
ulanganini tekshiradi."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_app_imports_and_all_routes_registered():
    """Import paytidagi FastAPIError (masalan noto'g'ri joyga qolib ketgan
    dekorator) shu yerda ko'tariladi — Docker qayta qurilguncha emas."""
    client = TestClient(app)
    paths = {route.path for route in app.routes}
    assert "/api/v1/inbound-routes/{route_id}" in paths
    assert "/api/v1/extensions/{ext_id}" in paths
    assert "/api/v1/trunks/{trunk_id}" in paths
    # M1a — kiruvchi oqim ilovalari routerlari.
    assert "/api/v1/time-groups/{group_id}" in paths
    assert "/api/v1/holidays/import-uz" in paths
    assert "/api/v1/time-conditions/{tc_id}/override" in paths
    assert "/api/v1/ivrs/{ivr_id}" in paths
    assert "/api/v1/ring-groups/{rg_id}" in paths
    assert "/api/v1/queues/{queue_id}/members" in paths
    assert "/api/v1/audio/{audio_id}/stream" in paths
    assert "/api/v1/numbers/free" in paths
    assert "/api/v1/flow/{inbound_route_id}" in paths
    assert "/api/v1/targets/{target_id}/usages" in paths
    # M1b — sozlamalar, audit, bosh panel routerlari.
    assert "/api/v1/settings/sip" in paths
    assert "/api/v1/audit" in paths
    assert "/api/v1/dashboard" in paths
    # Ichki PIN tekshiruv — `/api/v1` OSTIDA EMAS (dialplan `CURL()` shu bilan
    # ishlaydi, m1b-contract.md bo'lim 2), token yo'q bo'lsa ham qotmasdan
    # "0" bilan javob beradi (DB'siz ham, chunki token tekshiruvi oldin).
    assert "/internal/outbound-routes/{route_id}/pin-check" in paths
    # M1c §2 — ovozli pochta.
    assert "/api/v1/voicemail-boxes/{box_id}" in paths
    assert "/api/v1/voicemail-boxes/{box_id}/messages/{msg:path}/audio" in paths
    assert "/api/v1/voicemail-boxes/{box_id}/messages/{msg:path}/heard" in paths
    assert "/api/v1/settings/notify" in paths
    assert "/api/v1/settings/notify/test" in paths
    assert "/internal/voicemail/pin-check" in paths
    # DB ulanmagan — 500 kutilmaydi, lekin ishlov so'rovi routerga YETIB borishi
    # kerak (401 — autentifikatsiya yo'q, bu YETARLI dalil: route topildi).
    r = client.get("/api/v1/extensions")
    assert r.status_code == 401


def test_m1a_patch_routes_bound_to_handler_not_helper():
    """Regressiya: har bir yangi routerdagi `@router.patch` o'ziga tegishli
    handler funksiyaga ulangan bo'lishi kerak (helper funksiyaga EMAS) —
    `update_inbound_route` tarixidagi xatoning umumlashtirilgan tekshiruvi."""
    from app.api.v1 import ivrs, queues, ring_groups, time_conditions, time_groups

    expected = [
        (time_groups.router, "/time-groups/{group_id}", time_groups.update_time_group),
        (time_conditions.router, "/time-conditions/{tc_id}", time_conditions.update_time_condition),
        (ivrs.router, "/ivrs/{ivr_id}", ivrs.update_ivr),
        (ring_groups.router, "/ring-groups/{rg_id}", ring_groups.update_ring_group),
        (queues.router, "/queues/{queue_id}", queues.update_queue),
    ]
    for router, path, handler in expected:
        patch_routes = [r for r in router.routes if getattr(r, "path", "") == path
                        and "PATCH" in getattr(r, "methods", set())]
        assert len(patch_routes) == 1, path
        assert patch_routes[0].endpoint is handler, path


def test_inbound_route_patch_bound_to_update_function_not_helper():
    """Regressiya: `@router.patch(...)` `_apply_did_cid_change` ustida EMAS,
    `update_inbound_route` ustida bo'lishi kerak."""
    from app.api.v1 import inbound_routes

    patch_routes = [
        r for r in inbound_routes.router.routes
        if getattr(r, "path", "") == "/inbound-routes/{route_id}" and "PATCH" in getattr(r, "methods", set())
    ]
    assert len(patch_routes) == 1
    assert patch_routes[0].endpoint is inbound_routes.update_inbound_route


def test_voicemail_message_routes_resolve_to_right_handlers():
    """`{msg:path}` ochko'z — `/audio`, `/heard` qo'shimchalari to'g'ri
    handler'ga tushishi (DELETE /messages/{msg} emas) tekshiriladi."""
    from starlette.routing import Match

    def handler_for(method: str, path: str) -> str:
        scope = {"type": "http", "method": method, "path": path, "root_path": ""}
        for route in app.routes:
            match, child = route.matches(scope)
            if match == Match.FULL:
                return route.endpoint.__name__, child["path_params"]
        return "", {}

    assert handler_for("GET", "/api/v1/voicemail-boxes/b1/messages/INBOX/msg0000/audio") == (
        "message_audio", {"box_id": "b1", "msg": "INBOX/msg0000"})
    assert handler_for("POST", "/api/v1/voicemail-boxes/b1/messages/INBOX/msg0000/heard") == (
        "mark_heard", {"box_id": "b1", "msg": "INBOX/msg0000"})
    assert handler_for("DELETE", "/api/v1/voicemail-boxes/b1/messages/Old/msg0001") == (
        "delete_message", {"box_id": "b1", "msg": "Old/msg0001"})
