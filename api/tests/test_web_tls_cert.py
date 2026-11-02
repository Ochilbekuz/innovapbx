"""Veb (nginx 443) HTTPS sertifikati — 1.0.4. Sof funksiyalar (SAN tahlili,
generatsiya) + `ensure_web_certificate` idempotentligi (disk, DB/HTTP yo'q)."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

from cryptography import x509

from app.core.config import settings
from app.services.web_tls_cert import (
    ensure_web_certificate,
    generate_web_certificate,
    parse_san_ips,
    web_cert_path,
    web_key_path,
)


def test_parse_san_ips_splits_and_skips_blank_and_invalid():
    ips = parse_san_ips("10.0.0.5, , bad-value,192.168.1.1")
    assert [str(ip) for ip in ips] == ["10.0.0.5", "192.168.1.1"]


def test_parse_san_ips_empty_string_gives_empty_list():
    assert parse_san_ips("") == []


def test_generate_web_certificate_includes_hostname_and_ips():
    cert_pem, key_pem = generate_web_certificate("innova-pbx", "10.0.0.5,192.168.1.1", 3650)
    cert = x509.load_pem_x509_certificate(cert_pem)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns_names = san.get_values_for_type(x509.DNSName)
    ip_addrs = san.get_values_for_type(x509.IPAddress)
    assert "innova-pbx" in dns_names
    assert "localhost" in dns_names
    assert ipaddress.ip_address("10.0.0.5") in ip_addrs
    assert ipaddress.ip_address("192.168.1.1") in ip_addrs
    assert ipaddress.ip_address("127.0.0.1") in ip_addrs
    # Kalit sertifikatga mos (o'z-imzoli).
    key = __import__("cryptography.hazmat.primitives.serialization", fromlist=["load_pem_private_key"])
    private_key = key.load_pem_private_key(key_pem, password=None)
    assert private_key.public_key().public_numbers() == cert.public_key().public_numbers()


def test_generate_web_certificate_validity_is_about_ten_years():
    cert_pem, _ = generate_web_certificate("innova-pbx", "", 3650)
    cert = x509.load_pem_x509_certificate(cert_pem)
    delta = cert.not_valid_after_utc - datetime.now(timezone.utc)
    assert delta.days > 3650 - 2  # bir necha soniya/kun farq bilan


def test_ensure_web_certificate_creates_once_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "certs_dir", str(tmp_path))
    monkeypatch.setattr(settings, "web_tls_hostname", "innova-pbx")
    monkeypatch.setattr(settings, "web_tls_san_ips", "10.0.0.5")

    created = ensure_web_certificate()
    assert created is True
    cert_bytes = (tmp_path / settings.web_tls_cert_filename).read_bytes()

    created_again = ensure_web_certificate()
    assert created_again is False
    # Mavjud sertifikat O'ZGARMAGAN (yangilanishda qayta generatsiya qilinmaydi).
    assert (tmp_path / settings.web_tls_cert_filename).read_bytes() == cert_bytes


def test_ensure_web_certificate_paths_use_certs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "certs_dir", str(tmp_path))
    assert web_cert_path() == str(tmp_path / settings.web_tls_cert_filename)
    assert web_key_path() == str(tmp_path / settings.web_tls_key_filename)


def test_ensure_web_certificate_rejects_nothing_when_san_ips_empty(tmp_path, monkeypatch):
    """Faqat hostname/localhost bilan ham ishlasin (SAN IP berilmagan holat)."""
    monkeypatch.setattr(settings, "certs_dir", str(tmp_path))
    monkeypatch.setattr(settings, "web_tls_san_ips", "")
    assert ensure_web_certificate() is True
