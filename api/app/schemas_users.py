"""§3 (Foydalanuvchilar) va §4 (Operator portali /me) Pydantic sxemalari —
manba: `replica/m2b-contract.md`, `replica/m7-roles-contract.md` §3 (rol — endi
istalgan mavjud rol NOMI), frontend `web/src/api/types.ts` (`ManagedUser`,
`CreateUserPayload`, `UpdateUserPayload`, `ChangePasswordPayload`, `MeOverview`,
`MeExtensionOverview`, `MeQueueOverview`, `PatchMeExtensionPayload`) bilan AYNAN
mos bo'lishi SHART. Asosiy `app/schemas.py`dan ALOHIDA — u yerdagi `UserOut`
(auth oqimi: login/setup/me — `{id,login,full_name,role,permissions,language}`)
BOSHQA shartnoma bo'limi (m0/m1c), shu sabab ikkisi aralashtirilmaydi."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas import ExtensionRef, Lang

# m7-roles-contract.md §3: `role` — Literal['admin','operator'] EMAS, istalgan
# mavjud rol nomi (1-40 belgi); noma'lum nom bo'lsa `users.py::_role_for` 422
# `validation_error` ko'taradi (bu yerda faqat uzunlik tekshiriladi).


class ManagedUserOut(BaseModel):
    """`GET/POST/PATCH /users` javobidagi `UserOut` (m2b-contract.md §3) —
    parol/TOTP HECH QACHON bu yerda yo'q."""
    id: str
    username: str
    full_name: str
    email: str | None
    role: str
    extension: ExtensionRef | None
    is_active: bool
    language: Lang
    must_change_password: bool
    last_login_at: datetime | None
    updated_at: datetime
    # M10 B2: admin ro'yxatida 2FA holati ko'rsatiladi (yoqilganmi); sir maydon YO'Q.
    totp_enabled: bool = False


class CreateUserPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=128)
    email: str | None = None
    role: str = Field(min_length=1, max_length=40)
    extension_id: str | None = None
    password: str
    language: Lang | None = None


class UpdateUserPayload(BaseModel):
    """Barcha maydon ixtiyoriy — berilmagan = o'zgarmaydi; `email`/`extension_id`
    aniq `null` = tozalash (`model_fields_set` bilan ajratiladi, ext PATCH'dagi
    bilan bir xil naqsh)."""
    username: str | None = Field(default=None, min_length=1, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = None
    role: str | None = Field(default=None, min_length=1, max_length=40)
    extension_id: str | None = None
    language: Lang | None = None
    is_active: bool | None = None
    password: str | None = None
    updated_at: datetime


class UserMutated(BaseModel):
    item: ManagedUserOut


class ChangePasswordPayload(BaseModel):
    current: str
    new: str


# --------------------------------------------------------------------- §2 — /roles (m7)
class RoleOut(BaseModel):
    id: str
    name: str
    permissions: list[str]
    is_system: bool
    user_count: int
    updated_at: datetime


class RolesListOut(BaseModel):
    items: list[RoleOut]


class CreateRolePayload(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    permissions: list[str]


class UpdateRolePayload(BaseModel):
    """Ikkisi ham ixtiyoriy — berilmagan = o'zgarmaydi (`UpdateMohClassPayload`
    naqshi); tizim rolida (`is_system`) ikkisi ham taqiqlanadi (409 `system_role`)."""
    name: str | None = Field(default=None, min_length=1, max_length=40)
    permissions: list[str] | None = None
    updated_at: datetime


class RoleMutated(BaseModel):
    item: RoleOut


# --------------------------------------------------------------------- §4 — /me
class MeExtensionOut(BaseModel):
    id: str
    number: str
    name: str
    dnd: bool
    forward_always: str | None
    forward_busy: str | None
    outbound_allowed: bool
    voicemail_box_id: str | None
    updated_at: datetime


class MeQueueOut(BaseModel):
    id: str
    name: str
    number: str | None
    dynamic: bool
    logged_in: bool
    paused: bool
    pause_reason: str | None


class MeToday(BaseModel):
    answered: int
    missed: int
    talk_seconds: int


class MeOverviewOut(BaseModel):
    user: ManagedUserOut
    extension: MeExtensionOut | None
    queues: list[MeQueueOut]
    today: MeToday


class PatchMeExtensionPayload(BaseModel):
    """`dnd`/`forward_always`/`forward_busy` — admin `UpdateExtensionPayload`
    bilan BIR XIL tekshiruv/normalizatsiya funksiyasini chaqiradi
    (`app.api.v1.extensions.apply_call_field_patch`), faqat shu 3 maydon bilan."""
    dnd: bool | None = None
    forward_always: str | None = None
    forward_busy: str | None = None
    updated_at: datetime


class MeExtensionMutated(BaseModel):
    item: MeExtensionOut


class MeQueueActionMutated(BaseModel):
    item: MeQueueOut
