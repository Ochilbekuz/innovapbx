"""S32/M1c — SIP TLS sertifikat boshqaruvi (sof funksiyalar, Asterisk/DB'siz).
m1c-contract.md bo'lim 3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from app.services import tls_cert
from app.services.tls_cert import (
    ASTERISK_GID,
    BadCertificateError,
    extract_metadata,
    generate_self_signed,
    read_cert_metadata,
    validate_certificate,
    write_certificate,
)


def _build_cert(*, key=None, common_name="pbx.innova.test", not_after=None, issuer_name=None):
    key = key or ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    issuer = issuer_name or subject
    now = datetime.now(timezone.utc)
    not_after = not_after or (now + timedelta(days=365))
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return cert_pem, key_pem


def test_validate_certificate_accepts_matching_pair():
    cert_pem, key_pem = _build_cert()
    cert = validate_certificate(cert_pem, key_pem)
    assert isinstance(cert, x509.Certificate)


def test_validate_certificate_rejects_mismatched_key():
    cert_pem, _ = _build_cert()
    _, other_key_pem = _build_cert()
    with pytest.raises(BadCertificateError) as exc:
        validate_certificate(cert_pem, other_key_pem)
    assert exc.value.reason == "key_mismatch"


def test_validate_certificate_rejects_expired():
    cert_pem, key_pem = _build_cert(not_after=datetime.now(timezone.utc) - timedelta(days=1))
    with pytest.raises(BadCertificateError) as exc:
        validate_certificate(cert_pem, key_pem)
    assert exc.value.reason == "expired"


def test_validate_certificate_rejects_garbage_as_not_pem():
    with pytest.raises(BadCertificateError) as exc:
        validate_certificate(b"not a pem file", b"also not a pem file")
    assert exc.value.reason == "not_pem"


def test_validate_certificate_rejects_encrypted_key():
    key = ec.generate_private_key(ec.SECP256R1())
    cert_pem, _ = _build_cert(key=key)
    encrypted_key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"s3cr3t"),
    )
    with pytest.raises(BadCertificateError) as exc:
        validate_certificate(cert_pem, encrypted_key_pem)
    assert exc.value.reason == "encrypted_key"


def test_validate_certificate_accepts_rsa_pair_too():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert_pem, key_pem = _build_cert(key=key)
    validate_certificate(cert_pem, key_pem)


def test_extract_metadata_reports_self_signed_and_fingerprint():
    cert_pem, key_pem = _build_cert(common_name="selfsigned.test")
    cert = validate_certificate(cert_pem, key_pem)
    meta = extract_metadata(cert)
    assert meta.self_signed is True
    assert "selfsigned.test" in meta.subject
    assert len(meta.fingerprint_sha256) == 64  # sha256 hex


def test_extract_metadata_reports_not_self_signed_when_issuer_differs():
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Innova CA")])
    cert_pem, key_pem = _build_cert(common_name="leaf.test", issuer_name=ca_name)
    # Qo'lda yaratilgan sertifikat o'z-o'zini "sign" qiladi (kalit leaf'ga tegishli),
    # lekin issuer/subject nomi farqli bo'lsa self_signed=False bo'lishi kerak.
    cert = x509.load_pem_x509_certificate(cert_pem)
    meta = extract_metadata(cert)
    assert meta.self_signed is False


def test_generate_self_signed_produces_valid_matching_pair():
    cert_pem, key_pem = generate_self_signed("pbx.local")
    cert = validate_certificate(cert_pem, key_pem)
    meta = extract_metadata(cert)
    assert meta.self_signed is True
    assert "pbx.local" in meta.subject
    expected_not_after = datetime.now(timezone.utc) + timedelta(days=730)
    assert abs((meta.not_after - expected_not_after).total_seconds()) < 60
    san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    assert san_ext.value.get_values_for_type(x509.DNSName) == ["pbx.local"]
    assert san_ext.critical is False


def test_read_cert_metadata_returns_none_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    assert read_cert_metadata() is None


def test_write_certificate_then_read_back_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    cert_pem, key_pem = generate_self_signed("round-trip.test")
    write_certificate(cert_pem, key_pem)
    meta = read_cert_metadata()
    assert meta is not None
    assert "round-trip.test" in meta.subject


def test_write_certificate_key_file_is_group_readable_not_world(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    cert_pem, key_pem = generate_self_signed("perm.test")
    write_certificate(cert_pem, key_pem)
    key_file = tmp_path / tls_cert.settings.tls_key_filename
    mode = key_file.stat().st_mode & 0o777
    assert mode == 0o640
    assert key_file.stat().st_gid == ASTERISK_GID


def test_write_certificate_cert_file_is_world_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    cert_pem, key_pem = generate_self_signed("perm2.test")
    write_certificate(cert_pem, key_pem)
    cert_file = tmp_path / tls_cert.settings.tls_cert_filename
    assert cert_file.stat().st_mode & 0o777 == 0o644


def test_write_certificate_appends_chain_after_leaf(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    cert_pem, key_pem = generate_self_signed("leaf.test")
    chain_pem, _ = generate_self_signed("chain-ca.test")
    write_certificate(cert_pem, key_pem, chain_pem)
    content = (tmp_path / tls_cert.settings.tls_cert_filename).read_text()
    assert content.count("BEGIN CERTIFICATE") == 2


def test_read_cert_metadata_returns_none_for_corrupted_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    (tmp_path / tls_cert.settings.tls_cert_filename).write_text("garbage, not a cert")
    assert read_cert_metadata() is None


def test_validate_certificate_rejects_invalid_chain():
    cert_pem, key_pem = _build_cert()
    with pytest.raises(BadCertificateError) as exc:
        validate_certificate(cert_pem, key_pem, chain_pem=b"garbage chain")
    assert exc.value.reason == "not_pem"
