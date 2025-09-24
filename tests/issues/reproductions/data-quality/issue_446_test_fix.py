#!/usr/bin/env python3
"""
Test the fix for GitHub Issue #446: Missing values in 20-F filings

This script tests if the fix to add IFRS patterns to statement_resolver.py
resolves the issue with 20-F statements returning empty data.

Created: 2025-09-23
Related to Issue #446
"""

from edgar import Company, set_identity
import traceback


def test_statement_resolution_fix():
    """Test if statements are now properly resolved with IFRS patterns."""

    print("Testing IFRS Statement Resolution Fix")
    print("="*50)

    try:
        # Test with BioNTech 20-F
        bntx = Company('0001776985')
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()

        print(f"Testing {filing_20f.company} 20-F filing")
        print(f"Filing: {filing_20f.accession_number} from {filing_20f.filing_date}")

        xbrl = filing_20f.xbrl()

        # Test statement resolution at XBRL level
        print(f"\n1. STATEMENT RESOLUTION TEST:")

        # Check if statements are found in all_statements
        all_statements = xbrl.get_all_statements()
        print(f"   Total statements found: {len(all_statements)}")

        # Look for income statement patterns
        income_statements = []
        balance_statements = []

        for s in all_statements:
            stmt_type = s.get('type', '')
            stmt_role = s.get('role', '')

            # Safe string operations
            type_str = str(stmt_type).lower() if stmt_type else ''
            role_str = str(stmt_role).lower() if stmt_role else ''

            if 'income' in type_str or 'income' in role_str:
                income_statements.append(s)

            if 'balance' in type_str or 'position' in type_str:
                balance_statements.append(s)

        print(f"   Income-related statements: {len(income_statements)}")
        for stmt in income_statements[:3]:  # Show first 3
            print(f"     - {stmt.get('type', 'Unknown')}: {stmt.get('role', 'No role')}")

        print(f"   Balance sheet-related statements: {len(balance_statements)}")
        for stmt in balance_statements[:3]:  # Show first 3
            print(f"     - {stmt.get('type', 'Unknown')}: {stmt.get('role', 'No role')}")

        # Test direct statement retrieval
        print(f"\n2. DIRECT STATEMENT RETRIEVAL TEST:")

        # Try to get income statement directly
        try:
            income_data = xbrl.get_statement("IncomeStatement")
            print(f"   Income statement data: {len(income_data) if income_data else 0} items")
            if income_data and len(income_data) > 0:
                print(f"   Sample item: {income_data[0].get('concept', 'Unknown')}")
        except Exception as e:
            print(f"   Income statement error: {e}")

        # Try to get balance sheet directly
        try:
            balance_data = xbrl.get_statement("BalanceSheet")
            print(f"   Balance sheet data: {len(balance_data) if balance_data else 0} items")
            if balance_data and len(balance_data) > 0:
                print(f"   Sample item: {balance_data[0].get('concept', 'Unknown')}")
        except Exception as e:
            print(f"   Balance sheet error: {e}")

        # Test Statement objects
        print(f"\n3. STATEMENT OBJECTS TEST:")

        statements = xbrl.statements

        try:
            income_stmt = statements.income_statement()
            print(f"   Income statement object: {income_stmt is not None}")
            if income_stmt:
                raw_data = income_stmt.get_raw_data()
                print(f"   Income statement raw data: {len(raw_data)} items")

                # Check if values are populated now
                values_count = sum(1 for item in raw_data if item.get('values', {}))
                print(f"   Items with values: {values_count}")

        except Exception as e:
            print(f"   Income statement object error: {e}")
            traceback.print_exc()

        try:
            balance_stmt = statements.balance_sheet()
            print(f"   Balance sheet object: {balance_stmt is not None}")
            if balance_stmt:
                raw_data = balance_stmt.get_raw_data()
                print(f"   Balance sheet raw data: {len(raw_data)} items")

                # Check if values are populated now
                values_count = sum(1 for item in raw_data if item.get('values', {}))
                print(f"   Items with values: {values_count}")

        except Exception as e:
            print(f"   Balance sheet object error: {e}")
            traceback.print_exc()

        return True

    except Exception as e:
        print(f"Test failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Set proper identity for SEC API
    set_identity("Edgar Research Team research@edgartools.ai")

    success = test_statement_resolution_fix()

    print(f"\n{'='*50}")
    print(f"FIX TEST RESULT: {'SUCCESS' if success else 'FAILED'}")
    print(f"{'='*50}")