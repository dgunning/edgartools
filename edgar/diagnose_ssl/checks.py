"""
Diagnostic checks for SSL troubleshooting.
"""
import os
import platform
import socket
import ssl
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from .report import (
    CertificateConfig,
    CertificateInfo,
    CheckResult,
    CheckStatus,
    DiagnosticResult,
    EnvironmentInfo,
    HttpClientState,
    NetworkTestResults,
    ProxyConfig,
    Recommendation,
    SSLHandshakeResult,
)

# SEC.gov connection details
SEC_HOST = "www.sec.gov"
SEC_PORT = 443


def get_environment_info() -> EnvironmentInfo:
    """Gather environment information."""
    import httpx

    from edgar.__about__ import __version__ as edgartools_version

    # Get certifi version if available
    certifi_version = None
    try:
        import certifi
        certifi_version = getattr(certifi, "__version__", "unknown")
    except ImportError:
        pass

    # Get cryptography version if available
    cryptography_version = None
    try:
        import cryptography
        cryptography_version = getattr(cryptography, "__version__", "unknown")
    except ImportError:
        pass

    # Format platform info
    platform_info = f"{platform.system()} {platform.release()}"
    if platform.system() == "Darwin":
        platform_info = f"macOS {platform.mac_ver()[0]}"
    elif platform.system() == "Windows":
        platform_info = f"Windows {platform.version()}"

    return EnvironmentInfo(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform_info,
        edgartools_version=edgartools_version,
        httpx_version=httpx.__version__,
        certifi_version=certifi_version,
        cryptography_version=cryptography_version,
    )


def get_certificate_config() -> CertificateConfig:
    """Check certificate configuration."""
    config = CertificateConfig()

    # Check environment variables for CA bundles
    config.requests_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
    config.ssl_cert_file = os.environ.get("SSL_CERT_FILE")
    config.curl_ca_bundle = os.environ.get("CURL_CA_BUNDLE")

    # Check certifi path
    try:
        import certifi
        config.certifi_path = certifi.where()
        cert_path = Path(config.certifi_path)
        if cert_path.exists():
            config.bundle_exists = True
            config.bundle_size_kb = int(cert_path.stat().st_size / 1024)
    except ImportError:
        pass

    return config


def get_proxy_config() -> ProxyConfig:
    """Check proxy configuration from environment and runtime settings."""
    config = ProxyConfig()

    # Check environment variables (case-insensitive on some systems)
    config.http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    config.https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    config.no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")

    # Check runtime-configured proxy
    try:
        from edgar.httpclient import HTTP_MGR
        config.configured_proxy = HTTP_MGR.httpx_params.get("proxy")
    except Exception:
        pass

    return config


def get_http_client_state() -> HttpClientState:
    """Check HTTP client state."""
    from edgar.httpclient import HTTP_MGR, get_edgar_rate_limit_per_sec

    state = HttpClientState()

    # Get configured settings
    state.configured_verify = HTTP_MGR.httpx_params.get("verify", True)
    state.rate_limit_per_sec = get_edgar_rate_limit_per_sec()

    # Check if client exists
    state.client_created = HTTP_MGR._client is not None

    if state.client_created:
        # Try to get actual client SSL setting
        transport = HTTP_MGR._client._transport
        try:
            # Direct HTTPTransport
            ssl_ctx = transport._pool._ssl_context
            state.client_verify = ssl_ctx.check_hostname
        except (AttributeError, TypeError):
            try:
                # CacheTransport wrapping HTTPTransport
                ssl_ctx = transport._transport._pool._ssl_context
                state.client_verify = ssl_ctx.check_hostname
            except (AttributeError, TypeError):
                state.client_verify = None

        # Check if settings match
        if state.client_verify is not None:
            state.settings_match = state.configured_verify == state.client_verify
        else:
            # Can't determine, assume mismatch if configured is False but we can't verify
            state.settings_match = state.configured_verify

    return state


def test_dns_resolution() -> Tuple[bool, Optional[str], Optional[str]]:
    """Test DNS resolution for SEC.gov (IPv4 and IPv6)."""
    ipv4 = None
    ipv6 = None

    # Try IPv4
    try:
        ipv4 = socket.gethostbyname(SEC_HOST)
    except socket.gaierror:
        pass

    # Try IPv6
    try:
        infos = socket.getaddrinfo(SEC_HOST, SEC_PORT, socket.AF_INET6, socket.SOCK_STREAM)
        if infos:
            ipv6 = infos[0][4][0]
    except (socket.gaierror, IndexError):
        pass

    resolved = ipv4 is not None or ipv6 is not None
    return resolved, ipv4, ipv6


def test_tcp_connection() -> bool:
    """Test TCP connection to SEC.gov port 443."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((SEC_HOST, SEC_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_certificate_chain(host: str, port: int) -> List[CertificateInfo]:
    """Get the certificate chain from the server."""
    chain = []
    try:
        # Create SSL context that doesn't verify - we just want to see the chain
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # Get peer certificate
                cert = ssock.getpeercert(binary_form=True)
                if cert:
                    # Parse the certificate using cryptography if available
                    try:
                        from cryptography import x509
                        from cryptography.hazmat.backends import default_backend

                        parsed = x509.load_der_x509_certificate(cert, default_backend())

                        # Get subject and issuer
                        subject = parsed.subject.rfc4514_string()
                        issuer = parsed.issuer.rfc4514_string()

                        # Check if this looks like a corporate proxy
                        is_proxy = _is_corporate_proxy_cert(subject, issuer)

                        chain.append(CertificateInfo(
                            subject=subject,
                            issuer=issuer,
                            not_before=parsed.not_valid_before_utc.isoformat() if hasattr(parsed, 'not_valid_before_utc') else str(parsed.not_valid_before),
                            not_after=parsed.not_valid_after_utc.isoformat() if hasattr(parsed, 'not_valid_after_utc') else str(parsed.not_valid_after),
                            is_corporate_proxy=is_proxy,
                        ))
                    except ImportError:
                        # No cryptography library, provide basic info
                        chain.append(CertificateInfo(
                            subject="(cryptography library not installed)",
                            issuer="(install cryptography for certificate details)",
                        ))
    except Exception:
        pass

    return chain


def _is_corporate_proxy_cert(subject: str, issuer: str) -> bool:
    """
    Check if certificate appears to be from a corporate proxy.

    Uses a tiered approach:
    1. Strong indicators (SSL inspection product names) - high confidence
    2. Context-dependent indicators - check for proxy/firewall context

    Avoids false positives from company names like "Enterprise Products Partners"
    by requiring proxy-related context for generic terms.
    """
    combined = (subject + issuer).lower()

    # Tier 1: SSL inspection product names - high confidence
    ssl_inspection_products = [
        "zscaler", "bluecoat", "forcepoint", "websense",
        "palo alto networks", "fortiguard", "fortigate",
        "checkpoint", "barracuda", "sophos", "mcafee web gateway",
        "symantec ssl", "cisco umbrella", "netskope",
    ]
    if any(product in combined for product in ssl_inspection_products):
        return True

    # Tier 2: Check for proxy/firewall/inspection context
    proxy_context_words = ["proxy", "firewall", "mitm", "inspection", "intercept", "ssl visibility"]
    has_proxy_context = any(word in combined for word in proxy_context_words)

    if has_proxy_context:
        return True

    # Tier 3: Generic corporate terms - only flag if issuer doesn't match expected SEC.gov issuers
    # Real SEC.gov certs are issued by known CAs like DigiCert, Let's Encrypt, etc.
    legitimate_issuers = [
        "digicert", "let's encrypt", "globalsign", "comodo", "godaddy",
        "amazon", "entrust", "sectigo", "baltimore", "verisign",
    ]
    issuer_lower = issuer.lower()
    issued_by_known_ca = any(ca in issuer_lower for ca in legitimate_issuers)

    # If not issued by a known CA and has corporate-sounding issuer, could be proxy
    if not issued_by_known_ca:
        # Check if issuer looks like a company internal CA
        internal_ca_hints = ["internal", "corp", "root ca", "enterprise ca", "private ca"]
        if any(hint in issuer_lower for hint in internal_ca_hints):
            return True

    return False


def test_ssl_handshake() -> SSLHandshakeResult:
    """Test SSL handshake with SEC.gov using system certificates."""
    # Get certificate chain first (this doesn't verify)
    cert_chain = get_certificate_chain(SEC_HOST, SEC_PORT)
    is_proxy = any(c.is_corporate_proxy for c in cert_chain)

    try:
        # Now try actual verification
        context = ssl.create_default_context()

        with socket.create_connection((SEC_HOST, SEC_PORT), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=SEC_HOST) as ssock:
                # SSL handshake succeeded
                return SSLHandshakeResult(
                    success=True,
                    certificate_chain=cert_chain,
                    is_corporate_proxy=is_proxy,
                )

    except ssl.SSLCertVerificationError as e:
        return SSLHandshakeResult(
            success=False,
            error_message=str(e),
            certificate_chain=cert_chain,
            is_corporate_proxy=is_proxy,
        )
    except ssl.SSLError as e:
        return SSLHandshakeResult(
            success=False,
            error_message=str(e),
            certificate_chain=cert_chain,
            is_corporate_proxy=is_proxy,
        )
    except Exception as e:
        return SSLHandshakeResult(
            success=False,
            error_message=str(e),
            certificate_chain=cert_chain,
            is_corporate_proxy=is_proxy,
        )


def test_http_request_raw() -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Test HTTP request to SEC.gov with default SSL settings (no user config).
    This tests the "raw" connection to show the actual SSL problem.
    Returns: (success, status_code, error_message)
    """
    try:
        import httpx

        from edgar.core import get_identity

        # Quick request to SEC.gov robots.txt (small file)
        # Uses default httpx settings (SSL verification enabled)
        headers = {"User-Agent": get_identity()}
        response = httpx.get(
            f"https://{SEC_HOST}/robots.txt",
            timeout=10.0,
            follow_redirects=True,
            headers=headers,
        )
        success = response.status_code in (200, 301, 302)
        return success, response.status_code, None
    except Exception as e:
        return False, None, str(e)


def test_http_request_configured() -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Test HTTP request using user's configured settings (verify_ssl, proxy).
    This tests whether their workaround actually works.
    Returns: (success, status_code, error_message)
    """
    try:
        import httpx

        from edgar.core import get_identity
        from edgar.httpclient import HTTP_MGR

        # Get user's configured settings
        verify = HTTP_MGR.httpx_params.get("verify", True)
        proxy = HTTP_MGR.httpx_params.get("proxy")
        timeout = HTTP_MGR.httpx_params.get("timeout", 10.0)

        headers = {"User-Agent": get_identity()}

        # Build request with user's settings
        response = httpx.get(
            f"https://{SEC_HOST}/robots.txt",
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
            verify=verify,
            proxy=proxy,
        )
        success = response.status_code in (200, 301, 302)
        return success, response.status_code, None
    except Exception as e:
        return False, None, str(e)


def run_network_tests(skip_http: bool = False) -> NetworkTestResults:
    """Run all network connectivity tests."""
    results = NetworkTestResults()

    # DNS resolution (now returns IPv4 and IPv6)
    results.dns_resolved, results.dns_ip, results.dns_ipv6 = test_dns_resolution()
    if not results.dns_resolved:
        return results

    # TCP connection
    results.tcp_connected = test_tcp_connection()
    if not results.tcp_connected:
        return results

    # SSL handshake
    results.ssl_handshake = test_ssl_handshake()

    # HTTP request tests
    if not skip_http:
        # Test 1: Raw request (default SSL settings) - shows the actual problem
        if results.ssl_handshake.success:
            results.http_request_ok, results.http_status_code, results.http_error_message = test_http_request_raw()

        # Test 2: Request with user's configured settings - shows if workaround works
        # Run this even if SSL handshake failed (user might have verify_ssl=False)
        results.configured_http_ok, results.configured_http_status, results.configured_http_error = test_http_request_configured()

    return results


def generate_checks(
    env: EnvironmentInfo,
    cert_config: CertificateConfig,
    client_state: HttpClientState,
    network: NetworkTestResults,
) -> List[CheckResult]:
    """Generate check results from diagnostic data."""
    checks = []

    # Environment checks
    checks.append(CheckResult(
        name="Python Version",
        status=CheckStatus.PASS,
        message=f"Python {env.python_version}",
    ))

    # Cryptography library check
    if env.cryptography_version:
        checks.append(CheckResult(
            name="Cryptography Library",
            status=CheckStatus.PASS,
            message=f"cryptography {env.cryptography_version} installed",
        ))
    else:
        checks.append(CheckResult(
            name="Cryptography Library",
            status=CheckStatus.WARN,
            message="cryptography library not installed",
            details="Certificate details unavailable. Install with: pip install cryptography",
        ))

    # Certificate bundle check
    if cert_config.bundle_exists:
        checks.append(CheckResult(
            name="Certificate Bundle",
            status=CheckStatus.PASS,
            message=f"certifi bundle found ({cert_config.bundle_size_kb} KB)",
            details=cert_config.certifi_path,
        ))
    else:
        checks.append(CheckResult(
            name="Certificate Bundle",
            status=CheckStatus.WARN,
            message="certifi bundle not found or not accessible",
        ))

    # Custom CA check
    if cert_config.requests_ca_bundle:
        bundle_path = Path(cert_config.requests_ca_bundle)
        if bundle_path.exists():
            checks.append(CheckResult(
                name="Custom CA Bundle",
                status=CheckStatus.PASS,
                message="REQUESTS_CA_BUNDLE is set",
                details=cert_config.requests_ca_bundle,
            ))
        else:
            checks.append(CheckResult(
                name="Custom CA Bundle",
                status=CheckStatus.FAIL,
                message="REQUESTS_CA_BUNDLE points to non-existent file",
                details=cert_config.requests_ca_bundle,
            ))

    # HTTP client state checks
    if client_state.client_created and not client_state.settings_match:
        checks.append(CheckResult(
            name="HTTP Client Settings",
            status=CheckStatus.WARN,
            message="Client settings mismatch detected",
            details=f"Configured verify={client_state.configured_verify}, "
                    f"Client verify={client_state.client_verify}",
        ))
    else:
        verify_status = "enabled" if client_state.configured_verify else "disabled"
        checks.append(CheckResult(
            name="SSL Verification",
            status=CheckStatus.PASS if client_state.configured_verify else CheckStatus.WARN,
            message=f"SSL verification is {verify_status}",
        ))

    # Network checks
    if network.dns_resolved:
        checks.append(CheckResult(
            name="DNS Resolution",
            status=CheckStatus.PASS,
            message=f"www.sec.gov resolved to {network.dns_ip}",
        ))
    else:
        checks.append(CheckResult(
            name="DNS Resolution",
            status=CheckStatus.FAIL,
            message="Failed to resolve www.sec.gov",
        ))

    if network.tcp_connected:
        checks.append(CheckResult(
            name="TCP Connection",
            status=CheckStatus.PASS,
            message="Connection to port 443 established",
        ))
    elif network.dns_resolved:
        checks.append(CheckResult(
            name="TCP Connection",
            status=CheckStatus.FAIL,
            message="Failed to connect to port 443",
            details="SEC.gov may be blocked by firewall",
        ))

    # SSL handshake check
    if network.ssl_handshake:
        if network.ssl_handshake.success:
            checks.append(CheckResult(
                name="SSL Handshake",
                status=CheckStatus.PASS,
                message="SSL handshake successful",
            ))
        else:
            status = CheckStatus.FAIL
            if network.ssl_handshake.is_corporate_proxy:
                message = "SSL handshake failed - Corporate proxy detected"
            else:
                message = f"SSL handshake failed: {network.ssl_handshake.error_message}"
            checks.append(CheckResult(
                name="SSL Handshake",
                status=status,
                message=message,
                details=network.ssl_handshake.error_message,
            ))

    # HTTP request check (raw - default SSL settings)
    if network.http_request_ok:
        checks.append(CheckResult(
            name="HTTP Request (Default)",
            status=CheckStatus.PASS,
            message=f"HTTPS request successful (status {network.http_status_code})",
        ))
    elif network.ssl_handshake and network.ssl_handshake.success:
        msg = "HTTP request failed despite successful SSL handshake"
        if network.http_error_message:
            msg = f"HTTP request failed: {network.http_error_message[:100]}"
        checks.append(CheckResult(
            name="HTTP Request (Default)",
            status=CheckStatus.FAIL,
            message=msg,
            details=network.http_error_message,
        ))

    # HTTP request check (with user's configured settings)
    if network.configured_http_ok:
        checks.append(CheckResult(
            name="HTTP Request (Configured)",
            status=CheckStatus.PASS,
            message=f"Request with your settings successful (status {network.configured_http_status})",
            details=f"verify_ssl={client_state.configured_verify}",
        ))
    elif network.configured_http_error:
        checks.append(CheckResult(
            name="HTTP Request (Configured)",
            status=CheckStatus.FAIL,
            message="Request with your settings failed",
            details=network.configured_http_error[:200] if network.configured_http_error else None,
        ))

    return checks


def generate_recommendations(
    cert_config: CertificateConfig,
    client_state: HttpClientState,
    network: NetworkTestResults,
) -> List[Recommendation]:
    """Generate recommendations based on diagnostic results."""
    recommendations = []

    # Check for settings mismatch
    if client_state.client_created and not client_state.settings_match:
        recommendations.append(Recommendation(
            title="Restart Python and call configure_http() first",
            description=(
                "The HTTP client was created before configure_http() was called. "
                "SSL settings were locked in when the first request was made."
            ),
            code_snippet="""# At the very start of your script, before any edgar imports:
from edgar import configure_http
configure_http(verify_ssl=False)

# Now use edgar normally
from edgar import Company
company = Company("AAPL")""",
            priority=1,
        ))

    # SSL handshake failure recommendations
    if network.ssl_handshake and not network.ssl_handshake.success:
        if network.ssl_handshake.is_corporate_proxy:
            # Corporate proxy detected
            recommendations.append(Recommendation(
                title="Quick Fix: Disable SSL verification",
                description=(
                    "Your network uses SSL inspection which replaces SEC.gov's certificate "
                    "with your organization's certificate. This is common in corporate networks."
                ),
                code_snippet="""from edgar import configure_http
configure_http(verify_ssl=False)""",
                priority=1,
            ))

            recommendations.append(Recommendation(
                title="Secure Fix: Add corporate CA to trust store",
                description=(
                    "Ask your IT department for your organization's root CA certificate, "
                    "then configure Python to trust it."
                ),
                code_snippet="""# Option 1: Environment variable
# export REQUESTS_CA_BUNDLE="/path/to/corporate-ca.pem"

# Option 2: Runtime configuration
import os
os.environ["REQUESTS_CA_BUNDLE"] = "/path/to/corporate-ca.pem"

# Then import edgar
from edgar import Company""",
                priority=2,
            ))

        else:
            # Generic SSL failure
            recommendations.append(Recommendation(
                title="Disable SSL verification",
                description="Try disabling SSL verification to see if that resolves the issue.",
                code_snippet="""from edgar import configure_http
configure_http(verify_ssl=False)""",
                priority=1,
            ))

    # DNS failure
    if not network.dns_resolved:
        recommendations.append(Recommendation(
            title="Check DNS configuration",
            description=(
                "DNS resolution for www.sec.gov failed. Check your network connection "
                "and DNS settings. You may need to contact IT if on a corporate network."
            ),
            priority=1,
        ))

    # TCP failure
    if network.dns_resolved and not network.tcp_connected:
        recommendations.append(Recommendation(
            title="Check firewall settings",
            description=(
                "TCP connection to SEC.gov port 443 failed. This may indicate a firewall "
                "is blocking the connection. Contact your IT department."
            ),
            priority=1,
        ))

    return recommendations


def run_diagnostics() -> DiagnosticResult:
    """Run all diagnostic checks and return results."""
    # Gather information
    env = get_environment_info()
    cert_config = get_certificate_config()
    proxy_config = get_proxy_config()
    client_state = get_http_client_state()
    network = run_network_tests()

    # Generate checks and recommendations
    checks = generate_checks(env, cert_config, client_state, network)
    recommendations = generate_recommendations(cert_config, client_state, network)

    return DiagnosticResult(
        environment=env,
        certificate_config=cert_config,
        http_client_state=client_state,
        network_tests=network,
        proxy_config=proxy_config,
        checks=checks,
        recommendations=recommendations,
    )
