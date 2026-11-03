"""Ruxsatlar — m7-roles-contract.md §1: `<hudud>:view` / `<hudud>:edit` modeli
(`edit` ⇒ `view`). Mavjud maxsus kalitlar saqlanadi: `*` (admin — hammasi),
`calls:read:own` (`/calls`da alohida tekshiriladi — `app/api/v1/calls.py`
`_require_calls_permission`), `me:*` (`/me/*` — `get_current_user` yetarli,
bu kalit faqat rol ta'rifida ko'rsatish/UI uchun).

Markaziy tekshiruv `app/api/deps.py` `require_access()`da: marshrut shabloni
(`/api/v1` olib tashlangan) → `region_for_path()` bilan hudud, GET/HEAD → view,
qolgani → edit (`action_for_route()`, bitta istisno — pastda). Xaritada yo'q
marshrut (`users`, `roles`, `settings`, `security`, `backups`, `migration`,
`audit`, `system`, `feature-codes`, `integrations`) → faqat `*` (fail-closed).

Shu modul — FAQAT sof funksiyalar (DB/HTTP yo'q), to'liq unit testlanadi."""
from __future__ import annotations

ALL = "*"
CALLS_READ_OWN = "calls:read:own"
ME_ALL = "me:*"

# Hududlar — m7-roles-contract.md §1 jadvali. Maxsus rolga FAQAT shular
# beriladi (`validate_permission_keys`), boshqa kalit → 422.
REGIONS = ("monitor", "extensions", "connect", "routing", "apps", "reports")

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [ALL],
    "operator": [CALLS_READ_OWN, ME_ALL],
}


def permissions_for(role: str) -> list[str]:
    return list(ROLE_PERMISSIONS.get(role, []))


def has_permission(user_permissions: list[str], required: str) -> bool:
    return ALL in user_permissions or required in user_permissions


# --------------------------------------------------------------------- normalizatsiya/validatsiya

def normalize_permissions(permissions: list[str]) -> list[str]:
    """Rol saqlanishidan oldin: takrorlar olib tashlanadi; `<hudud>:edit`
    bo'lsa shu hududning `<hudud>:view`i tashlab yuboriladi (eng yuqori
    daraja saqlanadi — `edit` allaqachon `view`ni qamraydi). `*`/`me:*`/
    `calls:read:own` kabi hudud shaklida bo'lmagan kalitlar o'zgarmaydi."""
    edit_regions = {
        region for perm in permissions
        for region, _, action in (perm.partition(":"),)
        if action == "edit" and region in REGIONS
    }
    result: list[str] = []
    for perm in permissions:
        region, _, action = perm.partition(":")
        if action == "view" and region in edit_regions:
            continue
        if perm not in result:
            result.append(perm)
    return result


_ALLOWED_PERMISSION_KEYS = frozenset(
    {ALL, ME_ALL, CALLS_READ_OWN} | {f"{region}:{action}" for region in REGIONS for action in ("view", "edit")}
)


def validate_permission_keys(permissions: list[str]) -> str | None:
    """Noma'lum kalit topilsa — o'zini qaytaradi (chaqiruvchi 422 ko'taradi);
    hammasi tanish bo'lsa `None`."""
    for perm in permissions:
        if perm not in _ALLOWED_PERMISSION_KEYS:
            return perm
    return None


# --------------------------------------------------------------------- marshrut → hudud

# Eng uzun prefiks g'alaba qiladi (`region_for_path`) — shu sabab
# `/settings/provisioning` `/settings`dan OLDIN emas, UMUMAN BOSHQA yozuv
# (kalitlar ro'yxatida tartib muhim emas, taqqoslash uzunlik bo'yicha).
_PREFIX_REGION: tuple[tuple[str, str], ...] = (
    ("/dashboard", "monitor"),
    ("/alerts", "monitor"),
    ("/live", "monitor"),
    ("/settings/provisioning", "extensions"),
    ("/extensions", "extensions"),
    ("/devices", "extensions"),
    ("/voicemail-boxes", "extensions"),
    ("/trunks", "connect"),
    ("/inbound-routes", "connect"),
    ("/outbound-routes", "connect"),
    # M9 B1/B2: PIN to'plamlari va CID Lookup manbalari — `connect` (chiquvchi/
    # kiruvchi marshrutlar bilan bir hudud); telefon kitobi — `apps` (B2).
    ("/pin-sets", "connect"),
    ("/cid-sources", "connect"),
    ("/phonebook", "apps"),
    ("/time-groups", "routing"),
    ("/holidays", "routing"),
    ("/time-conditions", "routing"),
    ("/ivrs", "routing"),
    ("/queues", "routing"),
    ("/ring-groups", "routing"),
    # M9 A1/A2: e'lonlar va boshqa manzillar/ilovalar — marshrutlash
    # satellitlari (IVR/navbat kabi) — `routing`.
    ("/announcements", "routing"),
    ("/misc-destinations", "routing"),
    ("/misc-applications", "routing"),
    ("/audio", "apps"),
    ("/moh-classes", "apps"),
    ("/conferences", "apps"),
    ("/parking", "apps"),
    # M9 A4: paging/intercom guruhlari — `apps` (konferensiya/parking kabi).
    ("/page-groups", "apps"),
    ("/blacklist", "apps"),
    ("/campaigns", "apps"),
    # M10 A1: qayta chaqirish vidjeti — chiquvchi/kiruvchi marshrutlar bilan bir hudud.
    ("/callback-widgets", "connect"),
    ("/callback-requests", "connect"),
    # M10 A2: o'tkazib yuborilgan qo'ng'iroq bildirishnomasi — boshqa ilovalar kabi `apps`.
    ("/missed-call-rules", "apps"),
    ("/missed-call-notices", "apps"),
    ("/calls", "reports"),
    ("/reports", "reports"),
    ("/recordings", "reports"),
    # M10 B1: sifat baholash varaqalari/baholashlari — `reports` (edit=baholash).
    ("/qa", "reports"),
)


def region_for_path(path: str) -> str | None:
    """`path` — `/api/v1` OLIB TASHLANGAN marshrut shabloni. Mos prefiks
    topilmasa `None` (tizim/boshqa — fail-closed)."""
    matches = [(prefix, region) for prefix, region in _PREFIX_REGION
               if path == prefix or path.startswith(prefix + "/")]
    if not matches:
        return None
    return max(matches, key=lambda m: len(m[0]))[1]


# `POST /outbound-routes/simulate` — yozuvchi EMAS, dialplan qoidalarini
# (`outbound_rules.resolve_route`) SINAB ko'rish, ma'lumot o'zgarmaydi — shu
# sabab `edit` o'rniga `view` talab qilinadi (contract §1: "aniq istisno
# ro'yxati").
_READ_EXCEPTIONS = frozenset({"/outbound-routes/simulate"})


def action_for_route(method: str, path: str) -> str:
    if method in ("GET", "HEAD") or path in _READ_EXCEPTIONS:
        return "view"
    return "edit"


def has_region_access(user_permissions: list[str], region: str, action: str) -> bool:
    if ALL in user_permissions:
        return True
    if f"{region}:edit" in user_permissions:
        return True
    return action == "view" and f"{region}:view" in user_permissions


def _has_any_edit(user_permissions: list[str]) -> bool:
    return ALL in user_permissions or any(f"{region}:edit" in user_permissions for region in REGIONS)


# Umumiy tanlagichlar — m7-roles-contract.md §1: boshqa hudud ekranlaridagi
# destination picker shu GET'larni chaqiradi (masalan IVR/navbat/kiruvchi
# marshrut formasidagi manzil/ovoz/ichki raqam tanlagichi). Faqat GET,
# faqat aniq ro'yxat — sirlarni qaytaruvchi GET'lar (masalan ext secret
# reveal) BU YERGA QO'SHILMAYDI.
PICKER_GET_PATHS = frozenset({
    "/targets",
    "/targets/{target_id}/usages",
    "/flow/{inbound_route_id}",
    "/numbers/free",
    "/extensions",
    "/audio",
    "/moh-classes",
    "/time-groups",
})


def is_picker_path(path: str) -> bool:
    return path in PICKER_GET_PATHS


def check_access(user_permissions: list[str], method: str, path: str) -> bool:
    """`True`/`False` — `app/api/deps.py::require_access` shu bo'yicha 403
    ko'taradi. `path` — `/api/v1` OLIB TASHLANGAN marshrut shabloni."""
    if ALL in user_permissions:
        return True
    region = region_for_path(path)
    action = action_for_route(method, path)
    if region is not None and has_region_access(user_permissions, region, action):
        return True
    if method in ("GET", "HEAD") and is_picker_path(path) and _has_any_edit(user_permissions):
        return True
    return False
