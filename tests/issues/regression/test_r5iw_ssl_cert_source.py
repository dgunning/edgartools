"""The SSL diagnostics and advice name the certificates httpx2 really verifies with.

bead edgartools-r5iw. The httpx -> httpx2 move (#842, PR #1410) made the OS trust
store the default, but the diagnostics and the error advice still assumed certifi:

1. diagnose_ssl() reported truststore as "available (not active)" while it was
   the active default, and warned "certifi bundle not found" on a base install,
   where certifi is absent and unused.
2. The SSL error advice told users to export REQUESTS_CA_BUNDLE, which httpx2
   never reads, and to opt into the OS store they were already using.
3. get_http_config()["use_system_certs"] read False while the OS store verified.
4. The diagnostic handshake used ssl.create_default_context(), OpenSSL's
   compiled-in paths, which is not the store the client uses on macOS/Windows.

httpx2 with verify=True reads SSL_CERT_FILE, then SSL_CERT_DIR, then the OS store
(httpcore2.default_ssl_context). get_cert_source() mirrors that order, and the
first tests pin it against httpcore2 itself so the two cannot drift apart.
"""
import platform
import re
import ssl

import httpcore2
import pytest
import truststore

import edgar.httpclient as httpclient
from edgar.diagnose_ssl.checks import generate_checks, generate_recommendations, get_http_client_state
from edgar.diagnose_ssl.report import (
    CertificateConfig,
    EnvironmentInfo,
    NetworkTestResults,
    SSLHandshakeResult,
)
from edgar.httprequests import SSLErrorCategory, SSLVerificationError, _build_solution_section, _get_ssl_diagnostic


@pytest.fixture
def clean_env(monkeypatch):
    for var in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "EDGAR_USE_SYSTEM_CERTS"):
        monkeypatch.delenv(var, raising=False)
    original = httpclient.HTTP_MGR.httpx_params.get("verify", True)
    httpclient.HTTP_MGR.httpx_params["verify"] = True
    yield monkeypatch
    httpclient.HTTP_MGR.httpx_params["verify"] = original


def _context_kwargs(monkeypatch):
    """Record what httpcore2 asks ssl to load, so no real CA file is needed."""
    seen = {}

    def fake_create_default_context(**kwargs):
        seen.update(kwargs)
        return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)
    httpcore2.default_ssl_context()
    return seen


@pytest.fixture
def ca_file(tmp_path):
    # Any readable PEM works for the source logic; the content is never verified here
    path = tmp_path / "bundle.pem"
    path.write_text("")
    return str(path)


# --- get_cert_source() agrees with httpcore2 ---------------------------------

@pytest.mark.fast
def test_default_source_is_the_os_store(clean_env):
    assert httpclient.get_cert_source() == "os-store"
    if platform.system() in ("Darwin", "Windows"):
        # httpcore2 hands back a truststore context: the OS store, not certifi
        assert isinstance(httpcore2.default_ssl_context(), truststore.SSLContext)


@pytest.mark.fast
def test_ssl_cert_file_replaces_the_os_store(clean_env, ca_file):
    clean_env.setenv("SSL_CERT_FILE", ca_file)
    assert httpclient.get_cert_source() == "SSL_CERT_FILE"
    # httpcore2 loads exactly that file instead of the OS store
    assert _context_kwargs(clean_env) == {"cafile": ca_file}


@pytest.mark.fast
def test_ssl_cert_dir_replaces_the_os_store(clean_env, tmp_path):
    clean_env.setenv("SSL_CERT_DIR", str(tmp_path))
    assert httpclient.get_cert_source() == "SSL_CERT_DIR"
    assert _context_kwargs(clean_env) == {"capath": str(tmp_path)}


@pytest.mark.fast
def test_explicit_system_certs_ignore_ssl_cert_file(clean_env, ca_file):
    clean_env.setenv("SSL_CERT_FILE", ca_file)
    httpclient.configure_http(use_system_certs=True)
    assert httpclient.get_cert_source() == "os-store"


@pytest.mark.fast
def test_disabled_and_custom_sources(clean_env):
    assert httpclient.get_cert_source(False) == "disabled"
    assert httpclient.get_cert_source(ssl.create_default_context()) == "custom"


# --- get_http_config() does not contradict the client -------------------------

@pytest.mark.fast
def test_http_config_reports_the_os_store_by_default(clean_env):
    config = httpclient.get_http_config()
    assert config["cert_source"] == "os-store"
    assert config["use_system_certs"] is True
    assert config["verify_ssl"] is True


@pytest.mark.fast
def test_http_config_reports_ssl_cert_file(clean_env, ca_file):
    clean_env.setenv("SSL_CERT_FILE", ca_file)
    config = httpclient.get_http_config()
    assert config["cert_source"] == "SSL_CERT_FILE"
    assert config["use_system_certs"] is False


@pytest.mark.fast
def test_http_config_reports_verification_off(clean_env):
    httpclient.configure_http(verify_ssl=False)
    config = httpclient.get_http_config()
    assert config["cert_source"] == "disabled"
    assert config["verify_ssl"] is False
    assert config["use_system_certs"] is False


# --- diagnose_ssl() checks ----------------------------------------------------

def _base_install_env():
    # A base 6.0 install: httpx2 and truststore, no certifi
    return EnvironmentInfo(python_version="3.11", platform="test", edgartools_version="6.0",
                           httpx_version="2.16.0", certifi_version=None, truststore_version="0.10.4")


def _checks(cert_config):
    return {c.name: c for c in generate_checks(_base_install_env(), cert_config,
                                                get_http_client_state(), NetworkTestResults())}


@pytest.mark.fast
def test_base_install_reports_the_os_store_and_no_certifi_warning(clean_env):
    checks = _checks(CertificateConfig())
    assert checks["Certificate Source"].status.value == "pass"
    assert checks["Certificate Source"].message == "OS certificate store"
    assert "Certificate Bundle" not in checks
    assert not any(re.search(r"\bcertifi\b", c.message) for c in checks.values())
    assert not any("not active" in c.message for c in checks.values())


@pytest.mark.fast
def test_client_state_marks_the_os_store_active(clean_env):
    state = get_http_client_state()
    assert state.cert_source == "os-store"
    assert state.use_system_certs is True
    assert state.configured_verify is True


@pytest.mark.fast
def test_missing_ssl_cert_file_fails(clean_env, tmp_path):
    missing = str(tmp_path / "nope.pem")
    clean_env.setenv("SSL_CERT_FILE", missing)
    checks = _checks(CertificateConfig(ssl_cert_file=missing))
    assert checks["Certificate Source"].status.value == "fail"
    assert checks["Certificate Source"].details == missing


@pytest.mark.fast
def test_requests_ca_bundle_is_flagged_as_unread(clean_env, ca_file):
    clean_env.setenv("REQUESTS_CA_BUNDLE", ca_file)
    checks = _checks(CertificateConfig(requests_ca_bundle=ca_file))
    assert checks["REQUESTS_CA_BUNDLE"].status.value == "warn"
    assert "does not read it" in checks["REQUESTS_CA_BUNDLE"].message
    # The source is still the OS store: REQUESTS_CA_BUNDLE changed nothing
    assert checks["Certificate Source"].message == "OS certificate store"


@pytest.mark.fast
def test_failed_handshake_on_the_os_store_does_not_recommend_opting_into_it(clean_env):
    network = NetworkTestResults(ssl_handshake=SSLHandshakeResult(success=False, is_corporate_proxy=True))
    recs = generate_recommendations(CertificateConfig(), get_http_client_state(), network)
    text = " ".join(f"{r.title} {r.description} {r.code_snippet or ''}" for r in recs)
    assert recs[0].title == "Recommended: Add your corporate root CA to the OS trust store"
    assert "SSL_CERT_FILE" in text
    assert "use_system_certs" not in text
    assert "REQUESTS_CA_BUNDLE" not in text
    assert "pip install truststore" not in text


@pytest.mark.fast
def test_failed_handshake_with_ssl_cert_file_points_at_the_file(clean_env, ca_file):
    clean_env.setenv("SSL_CERT_FILE", ca_file)
    network = NetworkTestResults(ssl_handshake=SSLHandshakeResult(success=False))
    recs = generate_recommendations(CertificateConfig(ssl_cert_file=ca_file), get_http_client_state(), network)
    assert recs[0].title == "Check the CA file that replaces your OS certificate store"
    assert any("use_system_certs=True" in (r.code_snippet or "") for r in recs)


# --- the SSLVerificationError advice --------------------------------------------

@pytest.mark.fast
def test_corporate_network_advice_on_the_os_store(clean_env):
    diag = _get_ssl_diagnostic()
    assert diag.cert_source == "os-store"
    advice = _build_solution_section(SSLErrorCategory.CORPORATE_NETWORK, diag)
    assert "already verifies against your OS certificate store" in advice
    assert 'export SSL_CERT_FILE="$HOME/combined-bundle.pem"' in advice
    assert "REQUESTS_CA_BUNDLE" not in advice
    assert "use_system_certs" not in advice


@pytest.mark.fast
def test_advice_with_ssl_cert_file_set(clean_env, ca_file):
    clean_env.setenv("SSL_CERT_FILE", ca_file)
    diag = _get_ssl_diagnostic()
    assert diag.status == "CUSTOM_CA_NOT_WORKING"
    advice = _build_solution_section(SSLErrorCategory.CORPORATE_NETWORK, diag)
    assert f"SSL_CERT_FILE ({ca_file})" in advice
    assert "configure_http(use_system_certs=True)" in advice
    assert "REQUESTS_CA_BUNDLE" not in advice


@pytest.mark.fast
def test_requests_ca_bundle_alone_is_not_a_custom_ca(clean_env, ca_file):
    # httpx2 ignores it, so it must not switch the advice to "your CA file is wrong"
    clean_env.setenv("REQUESTS_CA_BUNDLE", ca_file)
    diag = _get_ssl_diagnostic()
    assert diag.status == "SSL_ENABLED"
    error = SSLVerificationError(ssl.SSLCertVerificationError("unable to get local issuer certificate"),
                                 "https://www.sec.gov")
    assert "(not read by edgartools; use SSL_CERT_FILE)" in str(error)
    assert "Certificates are verified against: OS certificate store." in str(error)


# --- live: the diagnostic handshake uses the client's certificates ---------------

@pytest.mark.network
def test_diagnostic_handshake_with_sec_succeeds(clean_env):
    from edgar.diagnose_ssl.checks import test_ssl_handshake as ssl_handshake

    result = ssl_handshake()
    assert result.success is True, result.error_message
    assert result.is_corporate_proxy is False
