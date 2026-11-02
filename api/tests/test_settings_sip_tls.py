"""SIP TLS endpoint yordamchilari — m1c-contract.md bo'lim 3 (sof funksiyalar,
DB/FastAPI'siz; `_tls_out`/`_install_certificate` to'g'ridan-to'g'ri sinaladi,
`test_sip_settings_validation.py` bilan bir xil qolip)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.settings import _install_certificate, _tls_out
from app.core.errors import ApiError
from app.services import tls_cert
from app.services.tls_cert import generate_self_signed, write_certificate


def _row(**over):
    base = dict(sip_tls_port=5061, restart_required=False)
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def certs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_cert.settings, "certs_dir", str(tmp_path))
    return tmp_path


def test_tls_out_disabled_when_no_certificate_on_disk(certs_dir):
    out = _tls_out(_row())
    assert out.enabled is False
    assert out.certificate is None
    assert out.port == 5061


def test_tls_out_disabled_when_port_is_null_even_with_certificate(certs_dir):
    cert_pem, key_pem = generate_self_signed("pbx.test")
    write_certificate(cert_pem, key_pem)
    out = _tls_out(_row(sip_tls_port=None))
    assert out.enabled is False
    assert out.certificate is not None  # sertifikat ko'rsatiladi, faqat yoqilmagan
    assert out.port is None


def test_tls_out_enabled_when_port_and_certificate_present(certs_dir):
    cert_pem, key_pem = generate_self_signed("pbx.enabled.test")
    write_certificate(cert_pem, key_pem)
    out = _tls_out(_row())
    assert out.enabled is True
    assert out.certificate.subject
    assert out.certificate.fingerprint_sha256
    assert out.restart_required is False


def test_tls_out_reflects_row_restart_required(certs_dir):
    assert _tls_out(_row(restart_required=True)).restart_required is True


def test_install_certificate_writes_matching_pair_and_returns_metadata(certs_dir):
    cert_pem, key_pem = generate_self_signed("install.test")
    meta = _install_certificate(cert_pem, key_pem, None)
    assert "install.test" in meta.subject
    assert (certs_dir / tls_cert.settings.tls_cert_filename).exists()
    assert (certs_dir / tls_cert.settings.tls_key_filename).exists()


def test_install_certificate_rejects_mismatched_key_pair_as_422(certs_dir):
    cert_pem, _ = generate_self_signed("a.test")
    _, other_key_pem = generate_self_signed("b.test")
    with pytest.raises(ApiError) as exc:
        _install_certificate(cert_pem, other_key_pem, None)
    assert exc.value.status_code == 422
    assert exc.value.code == "bad_certificate"
    assert exc.value.details == {"reason": "key_mismatch"}


def test_install_certificate_rejects_garbage_as_not_pem(certs_dir):
    with pytest.raises(ApiError) as exc:
        _install_certificate(b"garbage", b"garbage", None)
    assert exc.value.details == {"reason": "not_pem"}


def test_install_certificate_does_not_write_on_failure(certs_dir):
    cert_pem, _ = generate_self_signed("fail.test")
    _, other_key_pem = generate_self_signed("other.test")
    with pytest.raises(ApiError):
        _install_certificate(cert_pem, other_key_pem, None)
    assert not (certs_dir / tls_cert.settings.tls_cert_filename).exists()
