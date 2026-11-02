"""M2c §2/§0 — PJSIP ACL fayli (`pjsip_acl_innova.conf`, `dialplan` umumiy
hajmiga, `pjsip.conf` #include qiladi) `ip_bans` jadvalidan generatsiya
qilinadi (`app/services/apply.py` dialplan BILAN BIR XIL yozish/qo'llash
qolipi — atomik yozish + AMI `Command`, lekin compile/config_revisions yo'q:
ACL holatining YAGONA manbai `ip_bans`, fayl faqat uning KO'ZGUSI — bitta
`apply_acl()` chaqiruvi fayl matnini QAYTA generatsiya qiladi, idempotent).

Jonli tasdiqlangan (CTO, 2026-10-28, andrius/asterisk:22): `[innova-ban]
type=acl deny=<ip>/32` sorcery obyekti HECH QANDAY endpoint/identify'da
ko'rsatilmasa HAM GLOBAL qo'llanadi (barcha kiruvchi SIP so'roviga) — PJSIP
`type=acl` obyektlari sukut bo'yicha global ACL ro'yxatiga kiradi."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import IpBan
from app.services.atomic_write import atomic_write

ACL_OBJECT_NAME = "innova-ban"


@dataclass(frozen=True)
class AclApplyResult:
    status: str  # applied | failed
    message: str | None

    def to_dict(self) -> dict:
        return {"status": self.status, "revision": None, "message": self.message}


async def active_banned_ips(session: AsyncSession) -> list[str]:
    """Barcha tenant bo'yicha (fayl BITTA, Asterisk fizik infratuzilmasi
    ulashiladi — m2c-contract.md §0; amalda bitta tenant modeli)."""
    rows = (await session.execute(
        select(IpBan.ip).where(IpBan.lifted_at.is_(None)).order_by(IpBan.ip)
    )).scalars().all()
    return [str(ip) for ip in rows]


def hash_ips(ips: list[str]) -> str:
    """ACL kontenti identifikatori — fon vazifasi avvalgisi bilan BIR XIL
    bo'lsa (hech narsa o'zgarmagan) qayta AMI'ga murojaat qilmasligi uchun."""
    return hashlib.sha256(",".join(sorted(ips)).encode()).hexdigest()


def render_acl(ips: list[str]) -> str:
    if not ips:
        return "; Innova PBX — SIP ACL: hozircha bloklangan IP yo'q.\n"
    body = "\n".join(f"deny={ip}/32" for ip in ips)
    return f"[{ACL_OBJECT_NAME}]\ntype=acl\n{body}\n"


def write_acl_file(ips: list[str]) -> None:
    atomic_write(settings.dialplan_dir, settings.sip_acl_filename, render_acl(ips),
                tmp_prefix=".tmp-sip-acl-")


async def apply_acl_ips(ips: list[str], ami) -> AclApplyResult:
    """Faylni yozadi + AMI `module reload res_pjsip.so`. Ban ro'yxati
    chaqiruvchida ALLAQACHON o'qilgan bo'lsa (fon vazifa — ikki marta
    so'ramaslik uchun) shu funksiya ishlatiladi; API endpoint uchun
    `apply_acl()` (pastda) ni ishlating."""
    write_acl_file(ips)
    try:
        await ami.ensure_connected()
        resp = await ami.action("Command", Command="module reload res_pjsip.so")
        if str(resp.get("Response", "")).lower() != "success":
            raise RuntimeError(resp.get("Message") or "module reload rad etildi")
        return AclApplyResult(status="applied", message=None)
    except Exception as exc:  # noqa: BLE001 — AMI/tarmoq xatosi boshqariladi (ban bazada qoladi)
        return AclApplyResult(status="failed", message=str(exc)[:500])


async def apply_acl(session: AsyncSession, ami) -> AclApplyResult:
    """API endpoint (`POST`/`DELETE /security/bans`) uchun qulay o'rash —
    joriy faol ban ro'yxatini o'zi o'qiydi."""
    return await apply_acl_ips(await active_banned_ips(session), ami)
