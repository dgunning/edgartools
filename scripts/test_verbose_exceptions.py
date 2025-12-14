"""
Test script to verify VERBOSE_EXCEPTIONS configuration.

This script tests that:
1. By default (VERBOSE_EXCEPTIONS=False), caught exceptions don't log errors
2. When VERBOSE_EXCEPTIONS=True, errors are logged for debugging
"""
import os

print("=" * 80)
print("TEST 1: Default behavior (VERBOSE_EXCEPTIONS not set)")
print("=" * 80)
print("Expected: No error logs when StatementNotFound is caught\n")

# First, ensure the environment variable is not set
if 'EDGAR_VERBOSE_EXCEPTIONS' in os.environ:
    del os.environ['EDGAR_VERBOSE_EXCEPTIONS']

# Import after ensuring env var is not set
from edgar import find

try:
    # Get a recent Apple 10-Q filing (quarterly report)
    filings = find(ticker="AAPL", form="10-Q").latest(1)
    if filings:
        filing = filings[0]
        print(f"Using filing: {filing.form} filed on {filing.filing_date}")
        xbrl = filing.xbrl()

        # Try to access current period view
        current = xbrl.current_period
        print(f"Current period: {current.period_label}\n")

        # Try various statements - some might fail
        for stmt_name, stmt_method in [
            ("Balance Sheet", lambda: current.balance_sheet()),
            ("Income Statement", lambda: current.income_statement()),
            ("Cash Flow", lambda: current.cashflow_statement()),
        ]:
            try:
                stmt = stmt_method()
                print(f"✓ {stmt_name}: Found")
            except Exception as e:
                print(f"✓ {stmt_name}: Exception caught - {type(e).__name__}")
    else:
        print("✗ No filings found")

except Exception as e:
    print(f"✗ Unexpected error: {e}")

print("\n" + "=" * 80)
print("TEST 2: Verbose mode (EDGAR_VERBOSE_EXCEPTIONS=true)")
print("=" * 80)
print("Expected: Error logs should appear when StatementNotFound is caught\n")

# Set the environment variable
os.environ['EDGAR_VERBOSE_EXCEPTIONS'] = 'true'

# Need to reload the config module to pick up the new env var
import importlib

import edgar.config

importlib.reload(edgar.config)

from edgar.config import VERBOSE_EXCEPTIONS

print(f"VERBOSE_EXCEPTIONS is now: {VERBOSE_EXCEPTIONS}\n")

try:
    # Get the same filing
    filings = find(ticker="AAPL", form="10-Q").latest(1)
    if filings:
        filing = filings[0]
        print(f"Using filing: {filing.form} filed on {filing.filing_date}")

        # Force reload of xbrl modules to pick up new config
        import edgar.xbrl.current_period
        import edgar.xbrl.statement_resolver
        importlib.reload(edgar.xbrl.current_period)
        importlib.reload(edgar.xbrl.statement_resolver)

        xbrl = filing.xbrl()

        # Try to access current period view
        current = xbrl.current_period
        print(f"Current period: {current.period_label}\n")

        # Try various statements - some might fail
        for stmt_name, stmt_method in [
            ("Balance Sheet", lambda: current.balance_sheet()),
            ("Income Statement", lambda: current.income_statement()),
            ("Cash Flow", lambda: current.cashflow_statement()),
        ]:
            try:
                stmt = stmt_method()
                print(f"✓ {stmt_name}: Found")
            except Exception as e:
                print(f"✓ {stmt_name}: Exception caught - {type(e).__name__}")
    else:
        print("✗ No filings found")

except Exception as e:
    print(f"✗ Unexpected error: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nNOTE: In TEST 1, you should NOT see 'ERROR' log messages.")
print("      In TEST 2, you SHOULD see 'ERROR' log messages if exceptions occurred.")
print("      Compare the output above to verify the configuration works correctly.")
