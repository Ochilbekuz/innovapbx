"""Butun `/api/v1` marshrut jadvalini aylanib, har birini m7-roles-contract.md
§1 toifasiga ajratadi: hudud(region) / tanlagich(picker GET) / ochiq
(`/me`, `/auth`, `/softphone` — `/me` ostida, `/setup`) / tizim (admin-only,
xaritada yo'q). `users`/`roles`/`backups`/`settings`/`security`/`migration`/
`audit`/`system` HECH QACHON hududga tushmasligi — fail-closed kafolati —
shu testning asosiy maqsadi."""
from __future__ import annotations

from app.core.permissions import REGIONS, is_picker_path, region_for_path
from app.main import app

_API_PREFIX = "/api/v1"

# Autentifikatsiya bo'lsa ham rol tekshiruvisiz ochiq — `get_current_user`
# yetarli (`require_access` ULARDA ISHLATILMAYDI, app/api/deps.py).
_OPEN_PREFIXES = ("/me", "/auth", "/setup")

# Tizim guruhi — m7-roles-contract.md §1: hech qachon hududga tushmasligi
# SHART (fail-closed, faqat `*`).
_SYSTEM_ONLY_PREFIXES = (
    "/users", "/roles", "/settings", "/security", "/backups", "/migration",
    "/audit", "/system", "/feature-codes", "/integrations", "/config",
)

# `/settings/provisioning` — ataylab `/settings`dan AJRATILGAN (eng uzun
# prefiks g'alaba qiladi, `permissions.py::region_for_path`): provisioning —
# `extensions` hududi, qolgan `/settings/*` esa tizim guruhi.
_SYSTEM_PREFIX_CARVEOUTS = ("/settings/provisioning",)


def _matches_system_prefix(path: str) -> bool:
    if any(path == c or path.startswith(c + "/") for c in _SYSTEM_PREFIX_CARVEOUTS):
        return False
    return any(path == p or path.startswith(p + "/") for p in _SYSTEM_ONLY_PREFIXES)


def _v1_routes() -> list[tuple[str, str]]:
    """`(method, path_without_/api/v1_prefix)` juftliklari — HEAD chiqarib
    tashlanadi (FastAPI GET uchun avtomatik qo'shadi, alohida tahlil kerak emas)."""
    out: list[tuple[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(_API_PREFIX):
            continue
        stripped = path[len(_API_PREFIX):] or "/"
        for method in sorted(getattr(route, "methods", set()) - {"HEAD"}):
            out.append((method, stripped))
    return out


def test_every_route_is_classified_into_exactly_one_category():
    routes = _v1_routes()
    assert routes, "marshrutlar topilmadi — test o'zi sinalmayapti"
    for method, path in routes:
        region = region_for_path(path)
        is_open = any(path == p or path.startswith(p + "/") for p in _OPEN_PREFIXES)
        is_picker = method == "GET" and is_picker_path(path)
        is_system = _matches_system_prefix(path)

        if region is not None:
            assert region in REGIONS, (method, path, region)
            assert not is_system, f"{method} {path} — hudud VA tizim bo'lishi mumkin emas"
        elif is_open:
            pass
        elif is_picker:
            pass
        else:
            # Hudud/ochiq/tanlagich EMAS — faqat tizim prefikslaridan bo'lishi
            # SHART (aks holda ro'yxatga kiritilmagan yangi admin-only
            # marshrut sezilmay qolib ketadi).
            assert is_system, f"{method} {path} — hech qaysi toifaga mos kelmadi (tizim ro'yxatiga qo'sh?)"


def test_system_prefixes_never_resolve_to_a_region():
    """Asosiy kafolat: users/roles/settings/security/backups/migration/audit/
    system HECH QACHON `region_for_path` orqali hudud olmaydi — demak
    `require_access` ularni avtomatik ravishda faqat `*`ga qoldiradi."""
    routes = _v1_routes()
    checked = set()
    for method, path in routes:
        if not _matches_system_prefix(path):
            continue
        assert region_for_path(path) is None, (method, path)
        checked.update(p for p in _SYSTEM_ONLY_PREFIXES if path == p or path.startswith(p + "/"))
    # Har bir tizim prefiksi kamida bitta haqiqiy marshrutga mos kelishi kerak
    # (aks holda ro'yxat eskirgan/yo'q marshrutni "tekshiryapti" deb aldaydi).
    missing = set(_SYSTEM_ONLY_PREFIXES) - checked
    assert not missing, f"tizim prefikslari marshrutlarda topilmadi: {missing}"


def test_open_prefixes_have_real_routes():
    routes = _v1_routes()
    checked = set()
    for _method, path in routes:
        for prefix in _OPEN_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                checked.add(prefix)
    missing = set(_OPEN_PREFIXES) - checked
    assert not missing, f"ochiq prefikslar marshrutlarda topilmadi: {missing}"


def test_all_regions_have_at_least_one_route():
    routes = _v1_routes()
    found = {region_for_path(path) for _method, path in routes}
    missing = set(REGIONS) - found
    assert not missing, f"hudud(lar) marshrutga ega emas: {missing}"


def test_picker_get_paths_all_correspond_to_real_get_routes():
    """`PICKER_GET_PATHS`dagi har bir yozuv — haqiqiy GET marshrut (yozib
    qo'yilgan-lekin mavjud bo'lmagan yo'l test ichida sezilmay qolmasligi
    uchun)."""
    from app.core.permissions import PICKER_GET_PATHS

    routes = {path for method, path in _v1_routes() if method == "GET"}
    missing = PICKER_GET_PATHS - routes
    assert not missing, f"tanlagich ro'yxatida haqiqiy marshrutga mos kelmagan yozuv: {missing}"


def test_secret_revealing_extension_routes_are_not_pickers():
    assert not is_picker_path("/extensions/{ext_id}/rotate-secret")
    assert not is_picker_path("/extensions/{ext_id}/secret")
