"""
SSL diagnostic tool for EdgarTools.

Provides tools to diagnose SSL certificate verification issues,
particularly in corporate network environments with SSL inspection proxies.

Usage:
    # From command line:
    python -m edgar.diagnose_ssl

    # From Python/Jupyter:
    from edgar import diagnose_ssl
    result = diagnose_ssl()

    # Check if SSL is working
    if not result.ssl_ok:
        print(result.diagnosis)
"""
from .checks import run_diagnostics
from .output import display_result
from .report import (
    CheckResult,
    CheckStatus,
    DiagnosticResult,
)

__all__ = [
    "diagnose_ssl",
    "run_diagnostics",
    "DiagnosticResult",
    "CheckResult",
    "CheckStatus",
]


def diagnose_ssl(display: bool = True) -> DiagnosticResult:
    """
    Run SSL diagnostics and optionally display results.

    This function checks your environment's ability to connect to SEC.gov
    and identifies common SSL issues such as corporate proxy interference.

    Args:
        display: If True, display formatted results (auto-detects terminal vs notebook).
                 If False, only return the result object for programmatic use.

    Returns:
        DiagnosticResult: Complete diagnostic information including:
            - environment: Python/package versions
            - certificate_config: CA bundle configuration
            - http_client_state: Current HTTP client settings
            - network_tests: Results of connectivity tests
            - checks: List of individual check results
            - recommendations: Suggested fixes for any issues

    Examples:
        >>> from edgar import diagnose_ssl
        >>> result = diagnose_ssl()  # Runs diagnostics and displays results

        >>> # For programmatic use
        >>> result = diagnose_ssl(display=False)
        >>> if not result.ssl_ok:
        ...     print(f"Issue: {result.diagnosis}")
        ...     for rec in result.recommendations:
        ...         print(f"- {rec.title}")
    """
    result = run_diagnostics()

    if display:
        display_result(result)

    return result
