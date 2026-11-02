"""Ruxsatlar — m0-contract.md «Ruxsatlar (M0)» + m2b-contract.md §4:
admin — hammasi. operator — `GET /auth/me`, `GET /calls` (faqat o'z raqami),
`/me/*` (o'z ma'lumoti). Qolgani 403 `forbidden`.
"""
from __future__ import annotations

ALL = "*"
CALLS_READ_OWN = "calls:read:own"
CALLS_READ_ALL = "calls:read:all"
EXTENSIONS_WRITE = "extensions:write"
TRUNKS_WRITE = "trunks:write"
INBOUND_ROUTES_WRITE = "inbound_routes:write"
SYSTEM_READ = "system:read"
# M2b §4: `/me/*` — har qanday tizimga kirgan foydalanuvchiga ochiq (`get_current_user`
# yetarli, alohida tekshiruv shart emas — web/src/api/fake.ts'da ham shunday); shu
# ruxsat faqat rol ta'rifida ko'rsatish/UI uchun ro'yxatga kiritiladi.
ME_ALL = "me:*"

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [ALL],
    "operator": [CALLS_READ_OWN, ME_ALL],
}


def permissions_for(role: str) -> list[str]:
    return list(ROLE_PERMISSIONS.get(role, []))


def has_permission(user_permissions: list[str], required: str) -> bool:
    return ALL in user_permissions or required in user_permissions
