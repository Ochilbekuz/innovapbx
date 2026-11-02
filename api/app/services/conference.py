"""Konferensiya (S25, m2a-contract.md §4) — `confbridge_innova.conf` qurish
va Asterisk `app_confbridge` bilan yetkazish. `voicemail.py`/`parking.py`
BILAN BIR XIL qolip: sof qurish (`build_confbridge_conf`) -> atomik yozish
-> AMI reload + CLI tasdiq (`parking.py`dagi "module reload X.so" + CLI
`show` tekshiruvi namunasi bo'yicha, chunki `app_confbridge`da ham profil
ro'yxatini ko'rsatadigan alohida "list configured profiles" buyrug'i yo'q —
`confbridge show profile bridge <nom>` profil mavjudligini tasdiqlaydi).

PIN HECH QACHON: faylda, API javobida, audit logda ochiq matnda yo'q — faqat
bcrypt hash (`core.security.hash_password`/`verify_password`, `pin_role()`
orqali solishtiriladi). Dialplan hashni solishtirmaydi — ichki `CURL()`
(`app/api/internal_conference.py`) chaqiradi (`services/compiler.py`:
`_conference_dest_lines`)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_password
from app.db.models import Conference
from app.services.apply import AmiLike
from app.services.atomic_write import atomic_write
from app.services.dialplan_features import conf_admin_profile, conf_bridge_profile, conf_user_profile


@dataclass(frozen=True)
class ConferenceConfItem:
    id: str
    record: bool
    max_members: int | None


# ------------------------------------------------------------ sof qurish
def build_confbridge_conf(tenant_code: str, items: list[ConferenceConfItem]) -> str:
    lines = [
        "; Innova PBX — API avtomatik generatsiya qiladi (qo'lda tahrirlanmasin).",
        f"; tenant={tenant_code}",
    ]
    for item in sorted(items, key=lambda i: i.id):
        bridge = conf_bridge_profile(tenant_code, item.id)
        user = conf_user_profile(tenant_code, item.id)
        admin = conf_admin_profile(tenant_code, item.id)
        lines += ["", f"[{bridge}]", "type=bridge"]
        if item.max_members is not None:
            lines.append(f"max_members={item.max_members}")
        if item.record:
            lines.append("record_conference=yes")
        lines += ["", f"[{user}]", "type=user"]
        lines += ["", f"[{admin}]", "type=user", "admin=yes", "marked=yes"]
    return "\n".join(lines) + "\n"


def pin_role(pin: str, pin_hash: str | None, admin_pin_hash: str | None) -> str:
    """`"admin"`/`"user"`/`"deny"` — ichki PIN-tekshiruv endpoint javobi
    (dialplan qaysi profilga qo'shishni shu bilan hal qiladi). Admin PIN
    birinchi tekshiriladi (ikkisi bir xil tasodifan bo'lsa ham admin ustun)."""
    if admin_pin_hash and verify_password(pin, admin_pin_hash):
        return "admin"
    if pin_hash and verify_password(pin, pin_hash):
        return "user"
    return "deny"


# ------------------------------------------------------------------- disk/AMI
def write_confbridge_file(text_content: str) -> None:
    atomic_write(settings.dialplan_dir, settings.confbridge_filename, text_content, tmp_prefix=".tmp-conf-")


def _check_response(resp: dict, what: str) -> None:
    if str(resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"{what} rad etildi: {resp.get('Message', '')}")


async def _reload_and_verify_confbridge(ami: AmiLike, bridge_profiles: list[str]) -> None:
    await ami.ensure_connected()
    _check_response(await ami.action("Command", Command="module reload app_confbridge.so"),
                    "app_confbridge reload")
    for profile in bridge_profiles:
        show = await ami.action("Command", Command=f"confbridge show profile bridge {profile}")
        output = show.get("Output", "") or ""
        if profile not in output or "No bridge profile" in output:
            raise RuntimeError(f"tekshiruv muvaffaqiyatsiz: bridge profili ko'rinmadi: {profile}")


async def live_members(ami: AmiLike, room: str) -> int:
    """Asterisk ishlamasa/erishib bo'lmasa — xatolik emas, `0` (shart:
    m2a-contract.md §4 `live.members`)."""
    try:
        await ami.ensure_connected()
        events = await ami.action_list("ConfbridgeList", Conference=room)
    except Exception:  # noqa: BLE001 — qasddan keng: Asterisk yo'qligi 0 qaytarsin
        return 0
    return len([e for e in events if e.get("Event") == "ConfbridgeList"])


# ------------------------------------------------------------- nosof yig'ish
async def load_tenant_conferences(session: AsyncSession, tenant_id: str) -> list[Conference]:
    return list((await session.execute(
        select(Conference).where(Conference.tenant_id == tenant_id).order_by(Conference.name)
    )).scalars().all())


async def apply_confbridge(session: AsyncSession, *, tenant_id: str, tenant_code: str, ami: AmiLike) -> None:
    """Konferensiyalar -> `confbridge_innova.conf` -> reload+tasdiq. `apply_config()`
    (dialplan) BILAN BIRGA, lekin undan ALOHIDA chaqiriladi (voicemail.py namunasi)."""
    confs = await load_tenant_conferences(session, tenant_id)
    items = [ConferenceConfItem(id=str(c.id), record=c.record, max_members=c.max_members) for c in confs]
    write_confbridge_file(build_confbridge_conf(tenant_code, items))
    profiles = [conf_bridge_profile(tenant_code, item.id) for item in items]
    await _reload_and_verify_confbridge(ami, profiles)
