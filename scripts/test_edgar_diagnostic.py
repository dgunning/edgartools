#!/usr/bin/env python3
"""
SSL Diagnostic Script for EdgarTools

This script runs comprehensive diagnostics to identify SSL/certificate issues
when connecting to SEC.gov. Particularly useful for troubleshooting:
- Corporate VPN issues
- SSL inspection proxies
- Certificate verification failures
- Network connectivity problems

Usage:
    python test_edgar_diagnostic.py

The script will:
1. Check your Python environment
2. Test network connectivity to SEC.gov
3. Identify SSL certificate issues
4. Provide specific recommendations for your situation

If you've already called configure_http(verify_ssl=False), run this AFTER
to verify your configuration is working.
"""

print("EdgarTools SSL Diagnostic Tool")
print("=" * 60)
print("\nRunning comprehensive SSL diagnostics...")
print("This may take 10-15 seconds...\n")

from edgar import diagnose_ssl

# Run diagnostics (displays results automatically)
result = diagnose_ssl()

# Programmatic check for recommendations
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if result.network_tests.configured_http_ok:
    print("\n✓ Your SSL configuration is WORKING!")
    print("\nNext steps:")
    print("  1. Test with real code: python scripts/test_edgar_ssl.py")
    print("  2. Use configure_http(verify_ssl=False) at the start of your scripts")
    print("  3. For Jupyter notebooks, call configure_http() in your first cell")
else:
    print("\n✗ SSL configuration issues detected")
    print("\nReview the recommendations above for specific fixes.")
    print("\nCommon solutions:")
    print("  - Disable SSL verification: configure_http(verify_ssl=False)")
    print("  - Configure proxy if required: configure_http(proxy='http://proxy:8080')")
    print("  - Contact IT if SEC.gov appears blocked")

print("\n" + "=" * 60)
print("\nFor more help, see:")
print("  https://github.com/dgunning/edgartools/blob/main/docs/guides/ssl_verification.md")
