"""1.0.4 — veb (nginx 443) HTTPS sertifikati, brauzer softfoni mikrofon
ruxsatini olishi uchun (WebRTC `getUserMedia` faqat xavfsiz kontekstda
ishlaydi). `tls_cert.py` (SIP TLS) BILAN BIR XIL o'z-imzoli EC P-256 qolipi,
lekin mustaqil: SAN bir nechta IP + hostname'ni o'z ichiga oladi, muddat 10
yil (SIP sertifikatining 2 yilidan farqli, admin undan alohida boshqaradi).

`ensure_web_certificate()` — BIR MARTA (birinchi ishga tushishda) generatsiya
qiladi; fayl allaqachon mavjud bo'lsa TEGMAYDI (yangilanishda o'zgarmasin).
"""
from __future__ import annotations

import ipaddress
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.core.config import settings
from app.services.atomic_write import atomic_write

_KEY_MODE = 0o600  # API (yozuvchi) va nginx (o'qiydi) ikkisi ham root sifatida ishlaydi.
_CERT_MODE = 0o644


def web_cert_path() -> str:
    return os.path.join(settings.certs_dir, settings.web_tls_cert_filename)


def web_key_path() -> str:
    return os.path.join(settings.certs_dir, settings.web_tls_key_filename)


def parse_san_ips(raw: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Vergul bilan ajratilgan IP ro'yxatini tahlil qiladi; bo'sh/yaroqsiz
    qiymatlar jimgina o'tkazib yuboriladi (install.sh/innova-start.sh
    aniqlagan manzillar — noto'g'ri bitta IP bor sertifikat generatsiyasini
    butunlay to'xtatmasin)."""
    result: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for part in raw.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            result.append(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return result


def _build_san(hostname: str, san_ips_csv: str) -> x509.SubjectAlternativeName:
    dns_names = [hostname] if hostname and hostname != "localhost" else []
    dns_names.append("localhost")
    ips = [ipaddress.ip_address("127.0.0.1"), *parse_san_ips(san_ips_csv)]
    entries: list[x509.GeneralName] = [x509.DNSName(name) for name in dns_names]
    entries += [x509.IPAddress(ip) for ip in dict.fromkeys(ips)]  # tartib saqlab, takrorni olib tashlaydi
    return x509.SubjectAlternativeName(entries)


def generate_web_certificate(hostname: str, san_ips_csv: str, validity_days: int) -> tuple[bytes, bytes]:
    """EC P-256, o'z-imzoli, SAN = hostname + localhost + IP'lar — sertifikat + kalit (PEM)."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(name)
    builder = builder.issuer_name(name)
    builder = builder.public_key(key.public_key())
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.not_valid_before(now - timedelta(minutes=5))
    builder = builder.not_valid_after(now + timedelta(days=validity_days))
    builder = builder.add_extension(_build_san(hostname, san_ips_csv), critical=False)
    cert = builder.sign(key, hashes.SHA256())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return cert_pem, key_pem


def _as_pem_text(pem: bytes) -> str:
    text = pem.decode("utf-8")
    return text if text.endswith("\n") else text + "\n"


def ensure_web_certificate() -> bool:
    """Diskda yo'q bo'lsagina generatsiya qiladi; `True` — yangi yaratildi,
    `False` — allaqachon mavjud (tegilmadi)."""
    if os.path.exists(web_cert_path()) and os.path.exists(web_key_path()):
        return False
    cert_pem, key_pem = generate_web_certificate(
        settings.web_tls_hostname, settings.web_tls_san_ips, settings.web_tls_validity_days)
    atomic_write(settings.certs_dir, settings.web_tls_cert_filename, _as_pem_text(cert_pem),
                tmp_prefix=".tmp-webcert-", mode=_CERT_MODE)
    atomic_write(settings.certs_dir, settings.web_tls_key_filename, _as_pem_text(key_pem),
                tmp_prefix=".tmp-webkey-", mode=_KEY_MODE)
    return True
