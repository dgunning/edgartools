"""
Diagnostic result data structures for SSL troubleshooting.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from edgar.richtools import repr_rich


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
    cryptography_version: Optional[str] = None  # None means not installed


@dataclass
class CertificateConfig:
    """Certificate configuration information."""
    requests_ca_bundle: Optional[str] = None
    ssl_cert_file: Optional[str] = None
    curl_ca_bundle: Optional[str] = None
    certifi_path: Optional[str] = None
    bundle_exists: bool = False
    bundle_size_kb: Optional[int] = None


@dataclass
class ProxyConfig:
    """Proxy configuration from environment variables."""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    no_proxy: Optional[str] = None
    configured_proxy: Optional[str] = None  # From configure_http()


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
    dns_ipv6: Optional[str] = None  # IPv6 address if available
    tcp_connected: bool = False
    ssl_handshake: Optional[SSLHandshakeResult] = None
    http_request_ok: bool = False
    http_status_code: Optional[int] = None
    http_error_message: Optional[str] = None  # Capture actual error
    # Test with user's configured settings (verify_ssl, proxy)
    configured_http_ok: bool = False
    configured_http_status: Optional[int] = None
    configured_http_error: Optional[str] = None


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
    proxy_config: Optional[ProxyConfig] = None
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

    def __rich__(self):
        """Rich Panel display for SSL diagnostic results."""
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        sections = []

        # Overall status header
        if self.ssl_ok:
            status_text = Text("✓ SSL connectivity to SEC.gov is working correctly", style="bold green")
        else:
            status_text = Text("✗ SSL issues detected", style="bold red")
        sections.append(status_text)
        sections.append(Text(""))  # Spacer

        # Environment section
        env_table = Table(show_header=False, box=None, padding=(0, 1))
        env_table.add_column(style="dim", width=20)
        env_table.add_column()
        env_table.add_row("Python:", self.environment.python_version)
        env_table.add_row("Platform:", self.environment.platform)
        env_table.add_row("edgartools:", self.environment.edgartools_version)
        env_table.add_row("httpx:", self.environment.httpx_version)
        if self.environment.certifi_version:
            env_table.add_row("certifi:", self.environment.certifi_version)
        crypto = self.environment.cryptography_version or "[yellow]Not installed[/yellow]"
        env_table.add_row("cryptography:", crypto)

        sections.append(Panel(env_table, title="[bold]Environment[/bold]", border_style="dim", padding=(0, 1)))

        # Network Tests section
        tests_table = Table(show_header=False, box=None, padding=(0, 1))
        tests_table.add_column(width=30)
        tests_table.add_column()

        # DNS
        if self.network_tests.dns_resolved:
            dns_text = f"[green]PASS[/green] IPv4: {self.network_tests.dns_ip}"
            if self.network_tests.dns_ipv6:
                dns_text += f", IPv6: {self.network_tests.dns_ipv6}"
        else:
            dns_text = "[red]FAIL[/red] Could not resolve"
        tests_table.add_row("1. DNS Resolution:", dns_text)

        # TCP
        if self.network_tests.tcp_connected:
            tests_table.add_row("2. TCP Connection:", "[green]PASS[/green] Connected to port 443")
        elif self.network_tests.dns_resolved:
            tests_table.add_row("2. TCP Connection:", "[red]FAIL[/red] Could not connect")
        else:
            tests_table.add_row("2. TCP Connection:", "[blue]SKIP[/blue] DNS failed")

        # SSL Handshake
        if self.network_tests.ssl_handshake:
            if self.network_tests.ssl_handshake.success:
                tests_table.add_row("3. SSL Handshake:", "[green]PASS[/green] Handshake successful")
            else:
                error_msg = self.network_tests.ssl_handshake.error_message or "Failed"
                if self.network_tests.ssl_handshake.is_corporate_proxy:
                    tests_table.add_row("3. SSL Handshake:", "[red]FAIL[/red] Corporate proxy detected")
                else:
                    tests_table.add_row("3. SSL Handshake:", f"[red]FAIL[/red] {error_msg[:50]}")
        elif self.network_tests.tcp_connected:
            tests_table.add_row("3. SSL Handshake:", "[blue]SKIP[/blue] Not tested")
        else:
            tests_table.add_row("3. SSL Handshake:", "[blue]SKIP[/blue] TCP failed")

        # HTTP Request (default)
        if self.network_tests.http_request_ok:
            tests_table.add_row("4. HTTP (default SSL):", f"[green]PASS[/green] Status {self.network_tests.http_status_code}")
        elif self.network_tests.ssl_handshake and self.network_tests.ssl_handshake.success:
            tests_table.add_row("4. HTTP (default SSL):", "[red]FAIL[/red] Request failed")
        else:
            tests_table.add_row("4. HTTP (default SSL):", "[blue]SKIP[/blue] SSL failed")

        # HTTP Request (configured)
        verify = "enabled" if self.http_client_state.configured_verify else "disabled"
        if self.network_tests.configured_http_ok:
            tests_table.add_row(f"5. HTTP (verify={verify}):", f"[green]PASS[/green] Status {self.network_tests.configured_http_status}")
        elif self.network_tests.configured_http_error:
            tests_table.add_row(f"5. HTTP (verify={verify}):", "[red]FAIL[/red] Request failed")
        else:
            tests_table.add_row(f"5. HTTP (verify={verify}):", "[blue]SKIP[/blue] Not tested")

        sections.append(Panel(tests_table, title="[bold]Network Tests[/bold]", border_style="dim", padding=(0, 1)))

        # Recommendations section (if any)
        if self.recommendations:
            rec_table = Table(show_header=False, box=None, padding=(0, 1))
            rec_table.add_column()
            for i, rec in enumerate(self.recommendations, 1):
                rec_table.add_row(f"[bold]{i}. {rec.title}[/bold]")
                rec_table.add_row(f"   {rec.description}")
                if rec.code_snippet:
                    # Show first line of code snippet
                    first_line = rec.code_snippet.strip().split('\n')[0]
                    rec_table.add_row(f"   [dim]{first_line}[/dim]")
                rec_table.add_row("")

            sections.append(Panel(rec_table, title="[bold yellow]Recommendations[/bold yellow]", border_style="yellow", padding=(0, 1)))

        return Panel(
            Group(*sections),
            title="[bold]EdgarTools SSL Diagnostic[/bold]",
            border_style="green" if self.ssl_ok else "red",
            padding=(1, 2)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
