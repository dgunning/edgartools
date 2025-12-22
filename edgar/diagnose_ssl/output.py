"""
Output formatting for SSL diagnostics - supports terminal and Jupyter notebook.
"""

from .report import CheckStatus, DiagnosticResult


def is_notebook() -> bool:
    """Check if running in a Jupyter notebook."""
    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        # ZMQInteractiveShell = Jupyter notebook/lab
        # TerminalInteractiveShell = IPython in terminal (NOT a notebook)
        return shell == "ZMQInteractiveShell"
    except NameError:
        return False


def supports_color() -> bool:
    """Check if terminal supports color output."""
    import os
    import sys

    # Check for NO_COLOR environment variable
    if os.environ.get("NO_COLOR"):
        return False

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    return True


class TerminalFormatter:
    """Format diagnostic output for terminal display."""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and supports_color()

    def _color(self, text: str, color: str) -> str:
        """Apply ANSI color to text."""
        if not self.use_color:
            return text

        colors = {
            "green": "\033[92m",
            "red": "\033[91m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def _status_icon(self, status: CheckStatus) -> str:
        """Get icon for check status."""
        icons = {
            CheckStatus.PASS: self._color("PASS", "green"),
            CheckStatus.FAIL: self._color("FAIL", "red"),
            CheckStatus.WARN: self._color("WARN", "yellow"),
            CheckStatus.SKIP: self._color("SKIP", "blue"),
        }
        return icons.get(status, "?")

    def format(self, result: DiagnosticResult) -> str:
        """Format diagnostic result for terminal display."""
        lines = []

        # Header
        lines.append("")
        lines.append(self._color("EdgarTools SSL Diagnostic Report", "bold"))
        lines.append("=" * 40)
        lines.append("")

        # Environment section
        lines.append(self._color("Environment:", "bold"))
        lines.append(f"  Python version:     {result.environment.python_version}")
        lines.append(f"  Platform:           {result.environment.platform}")
        lines.append(f"  edgartools version: {result.environment.edgartools_version}")
        lines.append(f"  httpx version:      {result.environment.httpx_version}")
        if result.environment.certifi_version:
            lines.append(f"  certifi version:    {result.environment.certifi_version}")
        if result.environment.cryptography_version:
            lines.append(f"  cryptography:       {result.environment.cryptography_version}")
        else:
            lines.append(f"  cryptography:       {self._color('Not installed', 'yellow')}")
        lines.append("")

        # Certificate configuration
        lines.append(self._color("Certificate Configuration:", "bold"))
        ca_bundle = result.certificate_config.requests_ca_bundle or "Not set"
        ssl_cert = result.certificate_config.ssl_cert_file or "Not set"
        curl_ca = result.certificate_config.curl_ca_bundle or "Not set"
        lines.append(f"  REQUESTS_CA_BUNDLE: {ca_bundle}")
        lines.append(f"  SSL_CERT_FILE:      {ssl_cert}")
        lines.append(f"  CURL_CA_BUNDLE:     {curl_ca}")
        if result.certificate_config.certifi_path:
            lines.append(f"  certifi bundle:     {result.certificate_config.certifi_path}")
            if result.certificate_config.bundle_exists:
                lines.append(f"  Bundle exists:      Yes ({result.certificate_config.bundle_size_kb} KB)")
            else:
                lines.append("  Bundle exists:      No")
        lines.append("")

        # Proxy configuration
        if result.proxy_config:
            has_proxy = (result.proxy_config.http_proxy or result.proxy_config.https_proxy or
                        result.proxy_config.configured_proxy)
            if has_proxy:
                lines.append(self._color("Proxy Configuration:", "bold"))
                if result.proxy_config.http_proxy:
                    lines.append(f"  HTTP_PROXY:         {result.proxy_config.http_proxy}")
                if result.proxy_config.https_proxy:
                    lines.append(f"  HTTPS_PROXY:        {result.proxy_config.https_proxy}")
                if result.proxy_config.no_proxy:
                    lines.append(f"  NO_PROXY:           {result.proxy_config.no_proxy}")
                if result.proxy_config.configured_proxy:
                    lines.append(f"  Runtime proxy:      {result.proxy_config.configured_proxy}")
                lines.append("")

        # HTTP Client State
        lines.append(self._color("HTTP Client State:", "bold"))
        client_status = "Yes" if result.http_client_state.client_created else "No"
        lines.append(f"  Client created:     {client_status}")
        verify_config = "True" if result.http_client_state.configured_verify else "False"
        lines.append(f"  Configured verify:  {verify_config}")
        if result.http_client_state.client_created:
            if result.http_client_state.client_verify is not None:
                client_verify = "True" if result.http_client_state.client_verify else "False"
                lines.append(f"  Client verify:      {client_verify}")
            match_status = "Yes" if result.http_client_state.settings_match else self._color("No (MISMATCH)", "red")
            lines.append(f"  Settings match:     {match_status}")
        lines.append(f"  Rate limit:         {result.http_client_state.rate_limit_per_sec}/sec")
        lines.append("")

        # Network Tests
        lines.append(self._color("Network Tests:", "bold"))
        lines.append("")

        # DNS
        if result.network_tests.dns_resolved:
            lines.append("  1. DNS Resolution:")
            dns_info = f"IPv4: {result.network_tests.dns_ip}" if result.network_tests.dns_ip else "IPv4: None"
            if result.network_tests.dns_ipv6:
                dns_info += f", IPv6: {result.network_tests.dns_ipv6}"
            lines.append(f"     {self._color('PASS', 'green')} www.sec.gov resolves ({dns_info})")
        else:
            lines.append("  1. DNS Resolution:")
            lines.append(f"     {self._color('FAIL', 'red')} Could not resolve www.sec.gov")
        lines.append("")

        # TCP
        if result.network_tests.tcp_connected:
            lines.append("  2. TCP Connection (port 443):")
            lines.append(f"     {self._color('PASS', 'green')} Connection established")
        elif result.network_tests.dns_resolved:
            lines.append("  2. TCP Connection (port 443):")
            lines.append(f"     {self._color('FAIL', 'red')} Could not connect")
        else:
            lines.append("  2. TCP Connection (port 443):")
            lines.append(f"     {self._color('SKIP', 'blue')} Skipped (DNS failed)")
        lines.append("")

        # SSL Handshake
        if result.network_tests.ssl_handshake:
            ssl_result = result.network_tests.ssl_handshake
            lines.append("  3. SSL Handshake:")
            if ssl_result.success:
                lines.append(f"     {self._color('PASS', 'green')} Handshake successful")
            else:
                lines.append(f"     {self._color('FAIL', 'red')} {ssl_result.error_message or 'Handshake failed'}")

                if ssl_result.is_corporate_proxy:
                    lines.append("")
                    lines.append(f"     {self._color('Diagnosis:', 'yellow')} Corporate SSL inspection proxy detected")

                if ssl_result.certificate_chain:
                    lines.append("")
                    lines.append("     Server certificate:")
                    for cert in ssl_result.certificate_chain:
                        marker = " <- Corporate proxy!" if cert.is_corporate_proxy else ""
                        lines.append(f"       Subject: {cert.subject[:60]}...{self._color(marker, 'yellow')}")
                        lines.append(f"       Issuer:  {cert.issuer[:60]}...")
        elif result.network_tests.tcp_connected:
            lines.append("  3. SSL Handshake:")
            lines.append(f"     {self._color('SKIP', 'blue')} Not tested")
        else:
            lines.append("  3. SSL Handshake:")
            lines.append(f"     {self._color('SKIP', 'blue')} Skipped (TCP failed)")
        lines.append("")

        # HTTP Request (default settings)
        if result.network_tests.http_request_ok:
            lines.append("  4. HTTP Request (default SSL):")
            lines.append(f"     {self._color('PASS', 'green')} Request successful (status {result.network_tests.http_status_code})")
        elif result.network_tests.ssl_handshake and result.network_tests.ssl_handshake.success:
            lines.append("  4. HTTP Request (default SSL):")
            error_msg = result.network_tests.http_error_message or "Request failed"
            lines.append(f"     {self._color('FAIL', 'red')} {error_msg[:80]}")
        else:
            lines.append("  4. HTTP Request (default SSL):")
            lines.append(f"     {self._color('SKIP', 'blue')} Skipped (SSL handshake failed)")
        lines.append("")

        # HTTP Request (with user's configured settings)
        verify_setting = "enabled" if result.http_client_state.configured_verify else "disabled"
        lines.append(f"  5. HTTP Request (your settings, verify={verify_setting}):")
        if result.network_tests.configured_http_ok:
            lines.append(f"     {self._color('PASS', 'green')} Request successful (status {result.network_tests.configured_http_status})")
        elif result.network_tests.configured_http_error:
            error_msg = result.network_tests.configured_http_error[:80] if result.network_tests.configured_http_error else "Request failed"
            lines.append(f"     {self._color('FAIL', 'red')} {error_msg}")
        else:
            lines.append(f"     {self._color('SKIP', 'blue')} Not tested")
        lines.append("")

        # Summary
        lines.append(self._color("Summary:", "bold"))
        lines.append("-" * 40)
        if result.ssl_ok:
            lines.append(self._color("SSL connectivity to SEC.gov is working correctly.", "green"))
        else:
            lines.append(self._color(result.diagnosis, "red"))
        lines.append("")

        # Recommendations
        if result.recommendations:
            lines.append(self._color("Recommendations:", "bold"))
            lines.append("-" * 40)
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"\n{i}. {self._color(rec.title, 'bold')}")
                lines.append(f"   {rec.description}")
                if rec.code_snippet:
                    lines.append("")
                    lines.append(self._color("   Code:", "blue"))
                    for code_line in rec.code_snippet.strip().split("\n"):
                        lines.append(f"   {code_line}")
            lines.append("")

        # Documentation link
        lines.append("For more information:")
        lines.append("  https://github.com/dgunning/edgartools/blob/main/docs/guides/ssl_verification.md")
        lines.append("")

        return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


class NotebookFormatter:
    """Format diagnostic output for Jupyter notebook display."""

    def format(self, result: DiagnosticResult) -> str:
        """Format diagnostic result as HTML for notebook display."""
        html_parts = []

        # Header
        html_parts.append("<h2>EdgarTools SSL Diagnostic Report</h2>")

        # Environment table
        html_parts.append("<h3>Environment</h3>")
        html_parts.append("<table style='border-collapse: collapse; margin: 10px 0;'>")
        env_rows = [
            ("Python version", result.environment.python_version),
            ("Platform", result.environment.platform),
            ("edgartools version", result.environment.edgartools_version),
            ("httpx version", result.environment.httpx_version),
        ]
        if result.environment.certifi_version:
            env_rows.append(("certifi version", result.environment.certifi_version))
        crypto_ver = result.environment.cryptography_version or "<span style='color: orange;'>Not installed</span>"
        env_rows.append(("cryptography", crypto_ver))

        for label, value in env_rows:
            html_parts.append(
                f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>{label}:</td>"
                f"<td style='padding: 4px;'>{value}</td></tr>"
            )
        html_parts.append("</table>")

        # Certificate Configuration
        html_parts.append("<h3>Certificate Configuration</h3>")
        html_parts.append("<table style='border-collapse: collapse; margin: 10px 0;'>")
        ca_bundle = result.certificate_config.requests_ca_bundle or "<em>Not set</em>"
        ssl_cert = result.certificate_config.ssl_cert_file or "<em>Not set</em>"
        curl_ca = result.certificate_config.curl_ca_bundle or "<em>Not set</em>"
        cert_rows = [
            ("REQUESTS_CA_BUNDLE", ca_bundle),
            ("SSL_CERT_FILE", ssl_cert),
            ("CURL_CA_BUNDLE", curl_ca),
        ]
        if result.certificate_config.certifi_path:
            cert_rows.append(("certifi bundle", result.certificate_config.certifi_path))
            status = f"Yes ({result.certificate_config.bundle_size_kb} KB)" if result.certificate_config.bundle_exists else "No"
            cert_rows.append(("Bundle exists", status))

        for label, value in cert_rows:
            html_parts.append(
                f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>{label}:</td>"
                f"<td style='padding: 4px;'>{value}</td></tr>"
            )
        html_parts.append("</table>")

        # Proxy Configuration (if any)
        if result.proxy_config:
            has_proxy = (result.proxy_config.http_proxy or result.proxy_config.https_proxy or
                        result.proxy_config.configured_proxy)
            if has_proxy:
                html_parts.append("<h3>Proxy Configuration</h3>")
                html_parts.append("<table style='border-collapse: collapse; margin: 10px 0;'>")
                if result.proxy_config.http_proxy:
                    html_parts.append(f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>HTTP_PROXY:</td>"
                                     f"<td style='padding: 4px;'>{_escape_html(result.proxy_config.http_proxy)}</td></tr>")
                if result.proxy_config.https_proxy:
                    html_parts.append(f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>HTTPS_PROXY:</td>"
                                     f"<td style='padding: 4px;'>{_escape_html(result.proxy_config.https_proxy)}</td></tr>")
                if result.proxy_config.no_proxy:
                    html_parts.append(f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>NO_PROXY:</td>"
                                     f"<td style='padding: 4px;'>{_escape_html(result.proxy_config.no_proxy)}</td></tr>")
                if result.proxy_config.configured_proxy:
                    html_parts.append(f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Runtime proxy:</td>"
                                     f"<td style='padding: 4px;'>{_escape_html(str(result.proxy_config.configured_proxy))}</td></tr>")
                html_parts.append("</table>")

        # Check Results
        html_parts.append("<h3>Check Results</h3>")
        html_parts.append("<table style='border-collapse: collapse; margin: 10px 0;'>")
        html_parts.append("<tr style='background: #f0f0f0;'><th style='padding: 8px; text-align: left;'>Check</th>"
                         "<th style='padding: 8px; text-align: left;'>Status</th>"
                         "<th style='padding: 8px; text-align: left;'>Message</th></tr>")

        for check in result.checks:
            status_colors = {
                CheckStatus.PASS: ("green", "PASS"),
                CheckStatus.FAIL: ("red", "FAIL"),
                CheckStatus.WARN: ("orange", "WARN"),
                CheckStatus.SKIP: ("gray", "SKIP"),
            }
            color, text = status_colors.get(check.status, ("black", "?"))
            # Escape user-derived content to prevent HTML injection
            escaped_message = _escape_html(check.message)
            html_parts.append(
                f"<tr><td style='padding: 6px;'>{check.name}</td>"
                f"<td style='padding: 6px; color: {color}; font-weight: bold;'>{text}</td>"
                f"<td style='padding: 6px;'>{escaped_message}</td></tr>"
            )
        html_parts.append("</table>")

        # Summary
        if result.ssl_ok:
            summary_color = "green"
            summary_text = "SSL connectivity to SEC.gov is working correctly."
        else:
            summary_color = "red"
            summary_text = _escape_html(result.diagnosis)

        html_parts.append(f"<div style='padding: 12px; margin: 10px 0; background: #{'e8f5e9' if result.ssl_ok else 'ffebee'}; "
                         f"border-left: 4px solid {summary_color}; border-radius: 4px;'>")
        html_parts.append(f"<strong>Summary:</strong> {summary_text}")
        html_parts.append("</div>")

        # Recommendations
        if result.recommendations:
            html_parts.append("<h3>Recommendations</h3>")
            for i, rec in enumerate(result.recommendations, 1):
                html_parts.append("<div style='margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 4px;'>")
                html_parts.append(f"<strong>{i}. {rec.title}</strong>")
                html_parts.append(f"<p>{rec.description}</p>")
                if rec.code_snippet:
                    html_parts.append(f"<pre style='background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;'>"
                                     f"<code>{rec.code_snippet}</code></pre>")
                html_parts.append("</div>")

        # Documentation link
        html_parts.append("<p><em>For more information: ")
        html_parts.append("<a href='https://github.com/dgunning/edgartools/blob/main/docs/guides/ssl_verification.md'>")
        html_parts.append("SSL Verification Guide</a></em></p>")

        return "\n".join(html_parts)


def display_result(result: DiagnosticResult, force_terminal: bool = False) -> None:
    """Display diagnostic result in appropriate format."""
    if is_notebook() and not force_terminal:
        from IPython.display import HTML, display

        formatter = NotebookFormatter()
        html_output = formatter.format(result)
        display(HTML(html_output))
    else:
        formatter = TerminalFormatter()
        print(formatter.format(result))
