"""SIP TLS sertifikati — m1c-contract.md bo'lim 3 (S32 davomi).

Sof funksiyalar (PEM tahlil, kalit<->sertifikat mosligi, muddat, o'z-imzoli
yaratish, metadata) — `cryptography` kutubxonasi, Asterisk/DB'siz. Diskka
yozish/o'qish BITTA joyda (`write_certificate`/`read_cert_metadata`) — API
qatlami (`app/api/v1/settings.py`) faqat shularni chaqiradi.

Baza sertifikatni saqlamaydi — metadata har doim diskdan o'qiladi (yagona
haqiqat manbai). Xato `ApiError`ga EMAS, `BadCertificateError`ga aylanadi
(sof funksiya FastAPI'ga bog'liq bo'lmasin) — API qatlami 422
`bad_certificate` + `details.reason`ga map qiladi.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.core.config import settings
from app.services.atomic_write import atomic_write

# andrius/asterisk:22 image — Asterisk `-U asterisk` bilan ishlaydi, jonli
# tekshirilgan (2026-10-28, `docker exec innova-m0-asterisk-1 id`/`ps`):
# jarayon uid=1000(asterisk) gid=1000(asterisk) sifatida. Kalit faylini shu
# guruh o'qiy oladi, dunyoga esa YO'Q (0640).
ASTERISK_GID = 1000
_CERT_MODE = 0o644  # sertifikat sir emas — dunyoga ochiq (boshqa fayllar bilan bir xil qolip)
_KEY_MODE = 0o640

SELF_SIGNED_VALIDITY_DAYS = 730  # ~2 yil


class BadCertificateError(ValueError):
    """`reason` ∈ {"key_mismatch", "expired", "not_pem", "encrypted_key"}
    (m1c-contract.md bo'lim 3) — API qatlami 422 `bad_certificate`ga map qiladi."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class CertMetadata:
    subject: str
    issuer: str
    not_after: datetime
    self_signed: bool
    fingerprint_sha256: str


def cert_path() -> str:
    return os.path.join(settings.certs_dir, settings.tls_cert_filename)


def key_path() -> str:
    return os.path.join(settings.certs_dir, settings.tls_key_filename)


def _load_certificate(pem: bytes) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(pem)
    except ValueError as exc:
        raise BadCertificateError("not_pem") from exc


def _load_private_key(pem: bytes):
    try:
        return serialization.load_pem_private_key(pem, password=None)
    except TypeError as exc:
        # `cryptography` shifrlangan kalit uchun parol so'raydi — parolsiz
        # chaqiruvda TypeError beradi.
        raise BadCertificateError("encrypted_key") from exc
    except ValueError as exc:
        raise BadCertificateError("not_pem") from exc


def _public_key_bytes(public_key) -> bytes:
    return public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def _check_not_expired(cert: x509.Certificate) -> None:
    if cert.not_valid_after_utc < datetime.now(timezone.utc):
        raise BadCertificateError("expired")


def _check_key_matches_cert(cert: x509.Certificate, key) -> None:
    if _public_key_bytes(cert.public_key()) != _public_key_bytes(key.public_key()):
        raise BadCertificateError("key_mismatch")


def _check_chain_is_pem(chain_pem: bytes) -> None:
    try:
        x509.load_pem_x509_certificates(chain_pem)
    except ValueError as exc:
        raise BadCertificateError("not_pem") from exc


def validate_certificate(cert_pem: bytes, key_pem: bytes, chain_pem: bytes | None = None) -> x509.Certificate:
    """Tahlil + muddat + kalit mosligi — BITTA joyda. Muvaffaqiyatli bo'lsa
    tahlil qilingan sertifikat obyektini qaytaradi (metadata uchun)."""
    cert = _load_certificate(cert_pem)
    key = _load_private_key(key_pem)
    _check_not_expired(cert)
    _check_key_matches_cert(cert, key)
    if chain_pem:
        _check_chain_is_pem(chain_pem)
    return cert


def _subject_str(name: x509.Name) -> str:
    return name.rfc4514_string()


def extract_metadata(cert: x509.Certificate) -> CertMetadata:
    return CertMetadata(
        subject=_subject_str(cert.subject), issuer=_subject_str(cert.issuer),
        not_after=cert.not_valid_after_utc, self_signed=cert.issuer == cert.subject,
        fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(),
    )


def generate_self_signed(common_name: str) -> tuple[bytes, bytes]:
    """EC P-256, 2 yil, SAN = CN — o'z-imzoli sertifikat + kalit (PEM).

    Har bosqich ALOHIDA qatorda (bitta fluent zanjir EMAS) — qarorlarni
    (muddat offset'lari, SAN `critical` bayrog'i) mutator/coverage har
    birini mustaqil ko'rsin deb."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    not_before = now - timedelta(minutes=5)
    not_after = now + timedelta(days=SELF_SIGNED_VALIDITY_DAYS)
    san = x509.SubjectAlternativeName([x509.DNSName(common_name)])
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(name)
    builder = builder.issuer_name(name)
    builder = builder.public_key(key.public_key())
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.not_valid_before(not_before)
    builder = builder.not_valid_after(not_after)
    builder = builder.add_extension(san, critical=False)
    cert = builder.sign(key, hashes.SHA256())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return cert_pem, key_pem


def _as_pem_text(pem: bytes) -> str:
    text = pem.decode("utf-8")
    return text if text.endswith("\n") else text + "\n"


def write_certificate(cert_pem: bytes, key_pem: bytes, chain_pem: bytes | None = None) -> None:
    """Sertifikat (+ zanjir) va kalitni atomik yozadi — kalit 0640, faqat
    `ASTERISK_GID` guruhi o'qiy oladi; sertifikat 0644 (sir emas)."""
    cert_text = _as_pem_text(cert_pem) + (_as_pem_text(chain_pem) if chain_pem else "")
    atomic_write(settings.certs_dir, settings.tls_cert_filename, cert_text,
                tmp_prefix=".tmp-tlscert-", mode=_CERT_MODE)
    atomic_write(settings.certs_dir, settings.tls_key_filename, _as_pem_text(key_pem),
                tmp_prefix=".tmp-tlskey-", mode=_KEY_MODE, chown_gid=ASTERISK_GID)


def read_cert_metadata() -> CertMetadata | None:
    """Diskdagi sertifikatni o'qiydi — yo'q yoki buzilgan bo'lsa `None`
    (bazaga sertifikat holati yozilmaydi — yagona haqiqat manbai disk)."""
    path = cert_path()
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        pem = fh.read()
    try:
        cert = _load_certificate(pem)
    except BadCertificateError:
        return None
    return extract_metadata(cert)
