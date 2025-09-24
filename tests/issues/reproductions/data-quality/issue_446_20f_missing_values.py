#!/usr/bin/env python3
"""
Reproduction script for GitHub Issue #446: Missing values in 20-F filings

This script reproduces the issue where 20-F filings from foreign companies
show missing or incomplete financial statement data:

- SHEL: Balance sheet shows values, but cashflow and income statements are empty
- DB (Deutsche Bank): Balance sheet is empty, cashflow and income statement only contain few values
- BNTX (BioNTech): All statements show no numbers

Created: 2025-09-23
Issue: https://github.com/dgunning/edgartools/issues/446
"""

from edgar import Company, set_identity
import pandas as pd
import traceback


def analyze_statements(company_ticker, filing):
    """Analyze the three main financial statements for data completeness."""
    print(f"\n{'='*60}")
    print(f"ANALYZING {company_ticker} - {filing}")
    print(f"{'='*60}")

    results = {}

    try:
        xbrl = filing.xbrl()
        statements = xbrl.statements

        # Test Balance Sheet
        print("\n1. BALANCE SHEET:")
        try:
            bs = statements.balance_sheet()
            if bs is not None:
                try:
                    # Get raw data from statement
                    raw_data = bs.get_raw_data()
                    if raw_data and len(raw_data) > 0:
                        row_count = len(raw_data)
                        # Count items with values
                        non_null_values = sum(1 for item in raw_data if item.get('values', {}))
                        print(f"   ✓ Found {row_count} rows, {non_null_values} with non-zero values")
                        results['balance_sheet'] = {'rows': row_count, 'with_values': non_null_values}
                    else:
                        print("   ✗ Empty or None")
                        results['balance_sheet'] = {'rows': 0, 'with_values': 0}
                except Exception as e:
                    print(f"   ✗ Error accessing data: {e}")
                    results['balance_sheet'] = {'error': str(e)}
            else:
                print("   ✗ Empty or None")
                results['balance_sheet'] = {'rows': 0, 'with_values': 0}
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results['balance_sheet'] = {'error': str(e)}

        # Test Income Statement
        print("\n2. INCOME STATEMENT:")
        try:
            income = statements.income_statement()
            if income is not None:
                try:
                    # Get raw data from statement
                    raw_data = income.get_raw_data()
                    if raw_data and len(raw_data) > 0:
                        row_count = len(raw_data)
                        # Count items with values
                        non_null_values = sum(1 for item in raw_data if item.get('values', {}))
                        print(f"   ✓ Found {row_count} rows, {non_null_values} with non-zero values")
                        results['income_statement'] = {'rows': row_count, 'with_values': non_null_values}
                    else:
                        print("   ✗ Empty or None")
                        results['income_statement'] = {'rows': 0, 'with_values': 0}
                except Exception as e:
                    print(f"   ✗ Error accessing data: {e}")
                    results['income_statement'] = {'error': str(e)}
            else:
                print("   ✗ Empty or None")
                results['income_statement'] = {'rows': 0, 'with_values': 0}
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results['income_statement'] = {'error': str(e)}

        # Test Cash Flow Statement
        print("\n3. CASH FLOW STATEMENT:")
        try:
            cf = statements.cashflow_statement()
            if cf is not None:
                try:
                    # Get raw data from statement
                    raw_data = cf.get_raw_data()
                    if raw_data and len(raw_data) > 0:
                        row_count = len(raw_data)
                        # Count items with values
                        non_null_values = sum(1 for item in raw_data if item.get('values', {}))
                        print(f"   ✓ Found {row_count} rows, {non_null_values} with non-zero values")
                        results['cashflow_statement'] = {'rows': row_count, 'with_values': non_null_values}
                    else:
                        print("   ✗ Empty or None")
                        results['cashflow_statement'] = {'rows': 0, 'with_values': 0}
                except Exception as e:
                    print(f"   ✗ Error accessing data: {e}")
                    results['cashflow_statement'] = {'error': str(e)}
            else:
                print("   ✗ Empty or None")
                results['cashflow_statement'] = {'rows': 0, 'with_values': 0}
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results['cashflow_statement'] = {'error': str(e)}

        return results

    except Exception as e:
        print(f"Failed to get XBRL data: {e}")
        traceback.print_exc()
        return {'error': str(e)}


def reproduce_issue():
    """Reproduce the 20-F missing values issue."""

    # Companies mentioned in the issue - using CIK numbers to avoid ticker lookup issues
    test_companies = [
        ('SHEL', '0001468554'),    # Shell - Balance sheet shows values, but cashflow and income statements are empty
        ('DB', '0001104659'),      # Deutsche Bank - Balance sheet is empty, cashflow and income statement only contain few values
        ('BNTX', '0001776985')     # BioNTech - All statements show no numbers
    ]

    all_results = {}

    for ticker, cik in test_companies:
        print(f"\n{'='*80}")
        print(f"TESTING COMPANY: {ticker} (CIK: {cik})")
        print(f"{'='*80}")

        try:
            company = Company(cik)

            # Get latest 20-F filing
            filings = company.get_filings(form="20-F", amendments=False)
            if not filings:
                print(f"No 20-F filings found for {ticker}")
                all_results[ticker] = {'error': 'No 20-F filings found'}
                continue

            latest_filing = filings.latest()
            print(f"Latest 20-F filing: {latest_filing.accession_number} from {latest_filing.filing_date}")

            # Analyze statements
            results = analyze_statements(ticker, latest_filing)
            all_results[ticker] = results

        except Exception as e:
            print(f"Failed to process {ticker}: {e}")
            traceback.print_exc()
            all_results[ticker] = {'error': str(e)}

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY OF RESULTS")
    print(f"{'='*80}")

    for ticker, results in all_results.items():
        print(f"\n{ticker}:")
        if 'error' in results:
            print(f"  ERROR: {results['error']}")
        else:
            for stmt_type, data in results.items():
                if 'error' in data:
                    print(f"  {stmt_type}: ERROR - {data['error']}")
                else:
                    print(f"  {stmt_type}: {data['rows']} rows, {data['with_values']} with values")

    return all_results


if __name__ == "__main__":
    # Set proper identity for SEC API
    set_identity("Edgar Research Team research@edgartools.ai")

    print("Reproducing GitHub Issue #446: Missing values in 20-F filings")
    print("="*80)

    results = reproduce_issue()

    print(f"\n{'='*80}")
    print("ISSUE REPRODUCTION COMPLETE")
    print("Expected behavior: All statements should show values")
    print("Actual behavior: Missing/incomplete values in foreign company 20-F filings")
    print(f"{'='*80}")