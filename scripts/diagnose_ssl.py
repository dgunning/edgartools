#!/usr/bin/env python3
"""
Standalone SSL Diagnostic Script for EdgarTools
================================================

This script helps diagnose SSL/certificate issues when connecting to SEC.gov
through corporate networks, VPNs, or environments with SSL inspection.

Usage:
    python diagnose_ssl.py

This script has NO dependencies on edgartools - you can run it even if
edgartools imports are failing due to SSL issues.

Requirements: Python 3.8+, httpx (pip install httpx)
"""

import os
import platform
import socket
import ssl
import sys
from typing import Optional, Tuple

# Check for httpx
try:
    import httpx
    HTTPX_VERSION = httpx.__version__
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx")
    sys.exit(1)

SEC_HOST = "www.sec.gov"
SEC_URL = f"https://{SEC_HOST}/robots.txt"


def print_header(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_status(test_name: str, passed: bool, message: str):
    """Print test result with color-like formatting."""
    status = "PASS" if passed else "FAIL"
    symbol = "[OK]" if passed else "[X]"
    print(f"  {symbol} {test_name}: {message}")


def get_environment_info():
    """Gather environment information."""
    print_header("Environment Information")
    print(f"  Python:     {sys.version.split()[0]}")
    print(f"  Platform:   {platform.platform()}")
    print(f"  httpx:      {HTTPX_VERSION}")

    # Check for cryptography (optional but helpful)
    try:
        import cryptography
        print(f"  cryptography: {cryptography.__version__}")
    except ImportError:
        print("  cryptography: NOT INSTALLED (certificate details unavailable)")

    # Check for certifi
    try:
        import certifi
        print(f"  certifi:    {certifi.__version__}")
        print(f"  CA bundle:  {certifi.where()}")
    except ImportError:
        print("  certifi:    NOT INSTALLED")


def get_proxy_config():
    """Check proxy environment variables."""
    print_header("Proxy Configuration")

    proxy_vars = {
        'HTTP_PROXY': os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy'),
        'HTTPS_PROXY': os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'),
        'NO_PROXY': os.environ.get('NO_PROXY') or os.environ.get('no_proxy'),
    }

    has_proxy = any(proxy_vars.values())

    if has_proxy:
        for name, value in proxy_vars.items():
            if value:
                print(f"  {name}: {value}")
    else:
        print("  No proxy environment variables detected.")
        print("  (If your network requires a proxy, ask IT for the proxy URL)")


def get_certificate_config():
    """Check certificate configuration."""
    print_header("Certificate Configuration")

    cert_vars = {
        'REQUESTS_CA_BUNDLE': os.environ.get('REQUESTS_CA_BUNDLE'),
        'SSL_CERT_FILE': os.environ.get('SSL_CERT_FILE'),
        'CURL_CA_BUNDLE': os.environ.get('CURL_CA_BUNDLE'),
    }

    has_custom = any(cert_vars.values())

    for name, value in cert_vars.items():
        if value:
            print(f"  {name}: {value}")
            if os.path.exists(value):
                size_kb = os.path.getsize(value) // 1024
                print(f"    (file exists, {size_kb} KB)")
            else:
                print("    WARNING: File does not exist!")

    if not has_custom:
        print("  No custom certificate bundles configured.")


def test_dns_resolution() -> Tuple[bool, Optional[str], Optional[str]]:
    """Test DNS resolution for SEC.gov."""
    print_header("Network Tests")

    ipv4 = None
    ipv6 = None

    try:
        # Get IPv4
        results = socket.getaddrinfo(SEC_HOST, 443, socket.AF_INET, socket.SOCK_STREAM)
        if results:
            ipv4 = results[0][4][0]
    except Exception:
        pass

    try:
        # Get IPv6
        results = socket.getaddrinfo(SEC_HOST, 443, socket.AF_INET6, socket.SOCK_STREAM)
        if results:
            ipv6 = results[0][4][0]
    except Exception:
        pass

    if ipv4 or ipv6:
        addr_str = f"IPv4: {ipv4}" if ipv4 else ""
        if ipv6:
            addr_str += f", IPv6: {ipv6}" if addr_str else f"IPv6: {ipv6}"
        print_status("DNS Resolution", True, addr_str)
        return True, ipv4, ipv6
    else:
        print_status("DNS Resolution", False, "Could not resolve www.sec.gov")
        return False, None, None


def test_tcp_connection(ip: str) -> bool:
    """Test TCP connection to SEC.gov."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, 443))
        sock.close()
        print_status("TCP Connection", True, "Connected to port 443")
        return True
    except Exception as e:
        print_status("TCP Connection", False, f"Could not connect: {e}")
        return False


def test_ssl_handshake(host: str) -> Tuple[bool, bool, Optional[str]]:
    """
    Test SSL handshake and check certificate.
    Returns: (success, is_corporate_proxy, error_message)
    """
    is_corporate_proxy = False
    error_message = None

    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()

                # Extract certificate info
                subject = dict(x[0] for x in cert.get('subject', []))
                issuer = dict(x[0] for x in cert.get('issuer', []))

                issuer_cn = issuer.get('commonName', '')
                issuer_org = issuer.get('organizationName', '')

                # Check for corporate proxy signatures
                proxy_indicators = [
                    'zscaler', 'bluecoat', 'forcepoint', 'websense',
                    'palo alto', 'fortiguard', 'fortigate', 'checkpoint',
                    'barracuda', 'sophos', 'mcafee', 'symantec ssl',
                    'cisco umbrella', 'netskope', 'proxy', 'firewall',
                    'mitm', 'inspection', 'intercept'
                ]

                combined = (issuer_cn + issuer_org).lower()
                if any(ind in combined for ind in proxy_indicators):
                    is_corporate_proxy = True

                # Check for internal CA (not a well-known CA)
                known_cas = [
                    'digicert', "let's encrypt", 'globalsign', 'comodo',
                    'godaddy', 'amazon', 'entrust', 'sectigo', 'verisign'
                ]
                if not any(ca in combined for ca in known_cas):
                    internal_hints = ['internal', 'corp', 'root ca', 'enterprise', 'private']
                    if any(hint in combined for hint in internal_hints):
                        is_corporate_proxy = True

                if is_corporate_proxy:
                    print_status("SSL Handshake", False, "CORPORATE PROXY DETECTED")
                    print(f"       Certificate issuer: {issuer_cn or issuer_org}")
                    print("       Your network intercepts HTTPS traffic.")
                else:
                    print_status("SSL Handshake", True, f"Certificate valid (issuer: {issuer_cn or issuer_org})")

                return True, is_corporate_proxy, None

    except ssl.SSLCertVerificationError as e:
        error_message = str(e)
        # Even if verification fails, try to get cert info
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # Can't get cert details without cryptography in this mode
                    pass
        except Exception:
            pass

        print_status("SSL Handshake", False, "Certificate verification failed")
        print(f"       Error: {error_message[:100]}")
        return False, False, error_message

    except Exception as e:
        error_message = str(e)
        print_status("SSL Handshake", False, f"Failed: {error_message[:80]}")
        return False, False, error_message


def test_http_with_verify(verify: bool) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Test HTTP request with specified SSL verification setting.
    """
    try:
        response = httpx.get(
            SEC_URL,
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "EdgarTools SSL Diagnostic"},
            verify=verify
        )
        return True, response.status_code, None
    except Exception as e:
        return False, None, str(e)


def test_http_requests():
    """Test HTTP requests with different SSL settings."""

    # Test 1: With SSL verification (default)
    print("\n  Testing HTTP with SSL verification ENABLED (default)...")
    ok, status, error = test_http_with_verify(verify=True)
    if ok:
        print_status("HTTP (verify=True)", True, f"Status {status}")
    else:
        print_status("HTTP (verify=True)", False, f"{error[:80] if error else 'Failed'}")

    # Test 2: Without SSL verification (workaround)
    print("\n  Testing HTTP with SSL verification DISABLED (workaround)...")
    ok2, status2, error2 = test_http_with_verify(verify=False)
    if ok2:
        print_status("HTTP (verify=False)", True, f"Status {status2}")
    else:
        print_status("HTTP (verify=False)", False, f"{error2[:80] if error2 else 'Failed'}")

    return ok, ok2


def print_recommendations(ssl_ok: bool, verify_true_ok: bool, verify_false_ok: bool, is_proxy: bool):
    """Print recommendations based on test results."""
    print_header("Recommendations")

    if verify_true_ok:
        print("  Your SSL connection is working correctly!")
        print("  You should be able to use edgartools without any special configuration.")
        return

    if verify_false_ok:
        print("  GOOD NEWS: Disabling SSL verification works!")
        print("")
        print("  Add this to your code BEFORE using edgartools:")
        print("")
        print("    from edgar import configure_http, Company")
        print("")
        print("    # Disable SSL verification")
        print("    configure_http(verify_ssl=False)")
        print("")
        print("    # Now you can use edgartools")
        print("    company = Company('AAPL')")
        print("")

        if is_proxy:
            print("  NOTE: Corporate SSL inspection proxy detected.")
            print("  This is why SSL verification fails - your network")
            print("  intercepts HTTPS traffic for security scanning.")

        print("")
        print("  SECURITY NOTE: Disabling SSL verification means you won't")
        print("  detect if someone intercepts your traffic. This is generally")
        print("  acceptable for reading public SEC data.")
        return

    # Neither worked
    print("  Both SSL verification modes failed.")
    print("")
    print("  Possible causes:")
    print("    1. Your network requires a proxy server")
    print("    2. SEC.gov is blocked by your firewall")
    print("    3. Network connectivity issues")
    print("")
    print("  Try asking your IT department:")
    print("    - 'Do we use a proxy server for internet access?'")
    print("    - 'Is www.sec.gov accessible from our network?'")
    print("")
    print("  If you get a proxy URL, try:")
    print("")
    print("    from edgar import configure_http")
    print("    configure_http(verify_ssl=False, proxy='http://proxy.example.com:8080')")


def main():
    """Run all diagnostic tests."""
    print("\n" + "="*60)
    print("  EdgarTools SSL Diagnostic Tool (Standalone)")
    print("="*60)

    # Gather info
    get_environment_info()
    get_proxy_config()
    get_certificate_config()

    # Run network tests
    dns_ok, ipv4, ipv6 = test_dns_resolution()

    if not dns_ok:
        print("\n  DNS resolution failed. Check your network connection.")
        return

    tcp_ok = test_tcp_connection(ipv4)

    if not tcp_ok:
        print("\n  TCP connection failed. SEC.gov may be blocked by your firewall.")
        return

    ssl_ok, is_proxy, ssl_error = test_ssl_handshake(SEC_HOST)

    # HTTP tests
    verify_true_ok, verify_false_ok = test_http_requests()

    # Recommendations
    print_recommendations(ssl_ok, verify_true_ok, verify_false_ok, is_proxy)

    print("\n" + "="*60)
    print("  Diagnostic complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
