"""diagnose_ssl() flags a CA bundle that still trusts the compromised emSign root.

Bead: edgartools-a9bak. Incident: eMudhra emSign, 2026-10-20
(https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576).
Its CAs had trivially small EC private keys; certifi 2026.10.18 removed
"emSign ECC Root CA - G3" and 2026.10.19 restored the unaffected emSign roots.

edgartools verifies against the OS store by default, so OS updates fix default use.
The exposure is the corporate-proxy advice: it builds ~/combined-bundle.pem from
certifi and exports SSL_CERT_FILE, which replaces the OS store. That file is a
copy, so one built before 2026.10.19 keeps the root however certifi is upgraded.

Ground truth: the SHA-256 fingerprint below is the "# SHA256 Fingerprint" header
of "emSign ECC Root CA - G3" in certifi 2026.07.22's cacert.pem, and the root is
absent from the 120 certificates of certifi 2026.10.19's cacert.pem.
"""
import hashlib
import ssl

import pytest

from edgar.diagnose_ssl.checks import (
    DISTRUSTED_ROOTS,
    find_distrusted_roots,
    generate_checks,
    generate_recommendations,
    get_certificate_config,
)
from edgar.diagnose_ssl.report import CertificateConfig, CheckStatus, EnvironmentInfo, HttpClientState, NetworkTestResults
from edgar.httprequests import _combined_bundle_steps, _get_ssl_diagnostic

# Removed from certifi in 2026.10.18 (as shipped in certifi 2026.07.22)
EMSIGN_ECC_G3 = """-----BEGIN CERTIFICATE-----
MIICTjCCAdOgAwIBAgIKPPYHqWhwDtqLhDAKBggqhkjOPQQDAzBrMQswCQYDVQQG
EwJJTjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBUZWNo
bm9sb2dpZXMgTGltaXRlZDEgMB4GA1UEAxMXZW1TaWduIEVDQyBSb290IENBIC0g
RzMwHhcNMTgwMjE4MTgzMDAwWhcNNDMwMjE4MTgzMDAwWjBrMQswCQYDVQQGEwJJ
TjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBUZWNobm9s
b2dpZXMgTGltaXRlZDEgMB4GA1UEAxMXZW1TaWduIEVDQyBSb290IENBIC0gRzMw
djAQBgcqhkjOPQIBBgUrgQQAIgNiAAQjpQy4LRL1KPOxst3iAhKAnjlfSU2fySU0
WXTsuwYc58Byr+iuL+FBVIcUqEqy6HyC5ltqtdyzdc6LBtCGI79G1Y4PPwT01xyS
fvalY8L1X44uT6EYGQIrMgqCZH0Wk9GjQjBAMB0GA1UdDgQWBBR8XQKEE9TMipuB
zhccLikenEhjQjAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB/zAKBggq
hkjOPQQDAwNpADBmAjEAvvNhzwIQHWSVB7gYboiFBS+DCBeQyh+KTOgNG3qxrdWB
CUfvO6wIBHxcmbHtRwfSAjEAnbpV/KlK6O3t5nYBQnvI+GDZjVGLVTv7jHvrZQnD
+JbNR6iC8hZVdyR+EhCVBCyj
-----END CERTIFICATE-----"""

# Kept in certifi 2026.10.19: an emSign root that must not be flagged
EMSIGN_G1 = """-----BEGIN CERTIFICATE-----
MIIDlDCCAnygAwIBAgIKMfXkYgxsWO3W2DANBgkqhkiG9w0BAQsFADBnMQswCQYD
VQQGEwJJTjETMBEGA1UECxMKZW1TaWduIFBLSTElMCMGA1UEChMcZU11ZGhyYSBU
ZWNobm9sb2dpZXMgTGltaXRlZDEcMBoGA1UEAxMTZW1TaWduIFJvb3QgQ0EgLSBH
MTAeFw0xODAyMTgxODMwMDBaFw00MzAyMTgxODMwMDBaMGcxCzAJBgNVBAYTAklO
MRMwEQYDVQQLEwplbVNpZ24gUEtJMSUwIwYDVQQKExxlTXVkaHJhIFRlY2hub2xv
Z2llcyBMaW1pdGVkMRwwGgYDVQQDExNlbVNpZ24gUm9vdCBDQSAtIEcxMIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAk0u76WaK7p1b1TST0Bsew+eeuGQz
f2N4aLTNLnF115sgxk0pvLZoYIr3IZpWNVrzdr3YzZr/k1ZLpVkGoZM0Kd0WNHVO
8oG0x5ZOrRkVUkr+PHB1cM2vK6sVmjM8qrOLqs1D/fXqcP/tzxE7lM5OMhbTI0Aq
d7OvPAEsbO2ZLIvZTmmYsvePQbAyeGHWDV/D+qJAkh1cF+ZwPjXnorfCYuKrpDhM
tTk1b+oDafo6VGiFbdbyL0NVHpENDtjVaqSW0RM8LHhQ6DqS0hdW5TUaQBw+jSzt
Od9C4INBdN+jzcKGYEho42kLVACL5HZpIQ15TjQIXhTCzLG3rdd8cIrHhQIDAQAB
o0IwQDAdBgNVHQ4EFgQU++8Nhp6w492pufEhF38+/PB3KxowDgYDVR0PAQH/BAQD
AgEGMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAFn/8oz1h31x
PaOfG1vR2vjTnGs2vZupYeveFix0PZ7mddrXuqe8QhfnPZHr5X3dPpzxz5KsbEjM
wiI/aTvFthUvozXGaCocV685743QNcMYDHsAVhzNixl03r4PEuDQqqE/AjSxcM6d
GNYIAwlG7mDgfrbESQRRfXBgvKqy/3lyeqYdPV8q+Mri/Tm3R7nrft8EI6/6nAYH
6ftjk4BAtcZsCjEozgyfz7MjNYBBjWzEN3uBL4ChQEKF6dk4jeihU80Bv2noWgby
RQuQ+q7hv53yrlc8pa6yVvSLZUDp/TGBLPQ5Cdjua6e0ph0VpZj3AYHYhX3zUVxx
iN66zB+Afko=
-----END CERTIFICATE-----"""

G3_SHA256 = "86:a1:ec:ba:08:9c:4a:8d:3b:be:27:34:c6:12:ba:34:1d:81:3e:04:3c:f9:e8:a8:62:cd:5c:57:a3:6b:be:6b"


@pytest.fixture
def clean_env(monkeypatch):
    for var in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_the_fingerprint_is_certifis():
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(EMSIGN_ECC_G3)).hexdigest()
    assert fingerprint == G3_SHA256.replace(":", "")
    assert DISTRUSTED_ROOTS[fingerprint] == "emSign ECC Root CA - G3"


def test_a_bundle_built_before_the_fix_is_flagged(tmp_path):
    bundle = tmp_path / "combined-bundle.pem"
    bundle.write_text(f"# emSign Root CA - G1\n{EMSIGN_G1}\n# emSign ECC Root CA - G3\n{EMSIGN_ECC_G3}\n")
    assert find_distrusted_roots(str(bundle)) == ["emSign ECC Root CA - G3"]


def test_a_bundle_built_after_the_fix_is_not(tmp_path):
    bundle = tmp_path / "combined-bundle.pem"
    bundle.write_text(EMSIGN_G1 + "\n")
    assert find_distrusted_roots(str(bundle)) == []


def test_a_cert_directory_is_scanned(tmp_path):
    (tmp_path / "a1b2c3d4.0").write_text(EMSIGN_ECC_G3 + "\n")
    (tmp_path / "e5f6a7b8.0").write_text(EMSIGN_G1 + "\n")
    assert find_distrusted_roots(str(tmp_path)) == ["emSign ECC Root CA - G3"]


@pytest.mark.parametrize("path", [None, "", "/no/such/bundle.pem"])
def test_no_bundle_finds_nothing(path):
    assert find_distrusted_roots(path) == []


def test_a_malformed_block_is_skipped(tmp_path):
    bundle = tmp_path / "bundle.pem"
    bundle.write_text("-----BEGIN CERTIFICATE-----\nnot base64\n-----END CERTIFICATE-----\n" + EMSIGN_ECC_G3)
    assert find_distrusted_roots(str(bundle)) == ["emSign ECC Root CA - G3"]


def test_get_certificate_config_reads_ssl_cert_file(clean_env, tmp_path):
    bundle = tmp_path / "combined-bundle.pem"
    bundle.write_text(EMSIGN_ECC_G3)
    clean_env.setenv("SSL_CERT_FILE", str(bundle))
    assert get_certificate_config().distrusted_roots == ["emSign ECC Root CA - G3"]


def test_get_certificate_config_reads_ssl_cert_dir(clean_env, tmp_path):
    (tmp_path / "a1b2c3d4.0").write_text(EMSIGN_ECC_G3)
    clean_env.setenv("SSL_CERT_DIR", str(tmp_path))
    assert get_certificate_config().distrusted_roots == ["emSign ECC Root CA - G3"]


def test_the_os_store_default_scans_nothing(clean_env):
    assert get_certificate_config().distrusted_roots == []


def _env():
    return EnvironmentInfo(python_version="3.12", platform="test", edgartools_version="6.0", httpx_version="2")


def test_the_check_fails_and_recommends_a_rebuild_even_when_requests_work(tmp_path):
    bundle = str(tmp_path / "combined-bundle.pem")
    config = CertificateConfig(ssl_cert_file=bundle, distrusted_roots=["emSign ECC Root CA - G3"])
    state = HttpClientState(cert_source="SSL_CERT_FILE")
    network = NetworkTestResults(dns_resolved=True, tcp_connected=True, http_request_ok=True)

    [check] = [c for c in generate_checks(_env(), config, state, network) if c.name == "Distrusted Root CA"]
    assert check.status is CheckStatus.FAIL
    assert "emSign ECC Root CA - G3" in check.message

    [rec] = generate_recommendations(config, state, network)
    assert rec.priority == 1
    assert rec.title.startswith("Rebuild your CA bundle")
    assert 'pip install --upgrade "certifi>=2026.10.19"' in rec.code_snippet


def test_a_clean_bundle_gets_no_check_or_recommendation():
    config = CertificateConfig()
    state = HttpClientState()
    network = NetworkTestResults(dns_resolved=True, tcp_connected=True, http_request_ok=True)
    assert not [c for c in generate_checks(_env(), config, state, network) if c.name == "Distrusted Root CA"]
    assert generate_recommendations(config, state, network) == []


def test_the_ssl_error_advice_floors_certifi(clean_env):
    steps = _combined_bundle_steps(_get_ssl_diagnostic())
    assert steps.splitlines()[0].strip() == 'pip install --upgrade "certifi>=2026.10.19"'
