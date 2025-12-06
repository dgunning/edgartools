#!/usr/bin/env python3
"""
Simple test script for edgartools SSL configuration.

This script tests whether edgartools can connect to SEC.gov with your
network configuration. It's especially useful for troubleshooting VPN
and corporate proxy issues.

Usage:
    python test_edgar_ssl.py

If this script fails, run test_edgar_diagnostic.py to diagnose the issue.
"""

print("EdgarTools SSL Configuration Test")
print("=" * 60)

# STEP 1: Configure HTTP settings FIRST, before any other imports
print("\n[1/3] Configuring HTTP with verify_ssl=False...")
from edgar import configure_http
configure_http(verify_ssl=False)
print("      ✓ HTTP client configured")

# STEP 2: Import edgar classes
print("\n[2/3] Importing edgar classes...")
from edgar import Company
print("      ✓ Imports successful")

# STEP 3: Test fetching company data
print("\n[3/3] Fetching Apple (AAPL) data from SEC.gov...")
try:
    company = Company("AAPL")
    print(f"      ✓ Company name: {company.name}")
    print(f"      ✓ CIK: {company.cik}")
    print(f"      ✓ Exchange: {company.get_exchanges()}")

    print("\n" + "=" * 60)
    print("SUCCESS! EdgarTools is working correctly.")
    print("=" * 60)
    print("\nYou can now use edgartools in your code.")
    print("Remember to call configure_http(verify_ssl=False)")
    print("at the start of your script, before other edgar imports.")

except Exception as e:
    print(f"      ✗ FAILED: {e}")

    print("\n" + "=" * 60)
    print("TROUBLESHOOTING")
    print("=" * 60)
    print("\nThe test failed. Try running the diagnostic script:")
    print("  python scripts/test_edgar_diagnostic.py")
    print("\nOr from Python:")
    print("  from edgar import diagnose_ssl")
    print("  diagnose_ssl()")
    print("\nThe diagnostic will help identify the specific issue.")