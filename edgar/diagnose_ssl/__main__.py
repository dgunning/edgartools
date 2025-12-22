"""
CLI entry point for SSL diagnostics.

Usage:
    python -m edgar.diagnose_ssl
"""
import sys


def main() -> int:
    """Run SSL diagnostics from command line."""
    from . import diagnose_ssl

    print("Running SSL diagnostics...")
    print("")

    result = diagnose_ssl(display=True)

    # Return exit code based on results
    if result.ssl_ok:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
