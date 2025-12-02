"""
Diagnostic result data structures for SSL troubleshooting.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class CheckStatus(Enum):
    """Status of a diagnostic check."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    @property
    def failed(self) -> bool:
        return self.status == CheckStatus.FAIL


@dataclass
class EnvironmentInfo:
    """Environment information gathered during diagnostics."""
    python_version: str
    platform: str
    edgartools_version: str
    httpx_version: str
    certifi_version: Optional[str] = None


@dataclass
class CertificateConfig:
    """Certificate configuration information."""
    requests_ca_bundle: Optional[str] = None
    ssl_cert_file: Optional[str] = None
    certifi_path: Optional[str] = None
    bundle_exists: bool = False
    bundle_size_kb: Optional[int] = None


@dataclass
class HttpClientState:
    """HTTP client state information."""
    client_created: bool = False
    client_verify: Optional[bool] = None
    configured_verify: bool = True
    settings_match: bool = True
    rate_limit_per_sec: int = 9


@dataclass
class CertificateInfo:
    """Information about a certificate in the chain."""
    subject: str
    issuer: str
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    is_corporate_proxy: bool = False


@dataclass
class SSLHandshakeResult:
    """Result of SSL handshake test."""
    success: bool
    error_message: Optional[str] = None
    certificate_chain: List[CertificateInfo] = field(default_factory=list)
    is_corporate_proxy: bool = False


@dataclass
class NetworkTestResults:
    """Results of network connectivity tests."""
    dns_resolved: bool = False
    dns_ip: Optional[str] = None
    tcp_connected: bool = False
    ssl_handshake: Optional[SSLHandshakeResult] = None
    http_request_ok: bool = False
    http_status_code: Optional[int] = None


@dataclass
class Recommendation:
    """A recommendation for fixing an issue."""
    title: str
    description: str
    code_snippet: Optional[str] = None
    priority: int = 1  # 1 = highest priority


@dataclass
class DiagnosticResult:
    """Complete diagnostic result."""
    environment: EnvironmentInfo
    certificate_config: CertificateConfig
    http_client_state: HttpClientState
    network_tests: NetworkTestResults
    checks: List[CheckResult] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)

    @property
    def ssl_ok(self) -> bool:
        """True if SSL is working correctly."""
        if self.network_tests.ssl_handshake:
            return self.network_tests.ssl_handshake.success
        return False

    @property
    def all_passed(self) -> bool:
        """True if all checks passed."""
        return all(c.passed for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        """True if any checks have warnings."""
        return any(c.status == CheckStatus.WARN for c in self.checks)

    @property
    def has_failures(self) -> bool:
        """True if any checks failed."""
        return any(c.failed for c in self.checks)

    @property
    def diagnosis(self) -> str:
        """Get a brief diagnosis summary."""
        if self.ssl_ok:
            return "SSL connectivity to SEC.gov is working correctly."

        if self.network_tests.ssl_handshake and self.network_tests.ssl_handshake.is_corporate_proxy:
            return "Corporate SSL inspection proxy detected. Your network intercepts HTTPS traffic."

        if not self.network_tests.dns_resolved:
            return "DNS resolution failed. Check your network connection."

        if not self.network_tests.tcp_connected:
            return "TCP connection failed. SEC.gov may be blocked by your firewall."

        if self.network_tests.ssl_handshake and self.network_tests.ssl_handshake.error_message:
            return f"SSL handshake failed: {self.network_tests.ssl_handshake.error_message}"

        return "Unable to determine the exact issue. Check the detailed results."