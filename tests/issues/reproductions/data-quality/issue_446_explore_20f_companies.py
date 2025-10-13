#!/usr/bin/env python3
"""
Exploration script to find 20-F filing companies and check form patterns.

This script helps us understand what companies file 20-F forms and what the
filing patterns look like compared to 10-K forms.

Created: 2025-09-23
Related to Issue #446
"""

from edgar import Company, get_filings
import traceback


def explore_company_forms(company_cik, company_name):
    """Explore what forms a company files."""
    print(f"\n{'='*60}")
    print(f"EXPLORING {company_name} (CIK: {company_cik})")
    print(f"{'='*60}")

    try:
        company = Company(company_cik)

        # Check recent filings of all types
        all_filings = company.get_filings()
        print(f"Recent filings for {company_name}: {len(all_filings)} total filings")

        # Take first 20 for analysis
        recent_filings = all_filings[:20] if len(all_filings) > 20 else all_filings

        form_counts = {}
        for filing in recent_filings:
            form = filing.form
            form_counts[form] = form_counts.get(form, 0) + 1
            if form in ['20-F', '10-K', '10-Q']:
                print(f"  {filing.form} - {filing.filing_date} - {filing.accession_number}")

        print(f"\nForm type counts (from last 20 filings):")
        for form, count in sorted(form_counts.items()):
            print(f"  {form}: {count}")

        # Check for 20-F specifically
        filings_20f = company.get_filings(form="20-F")
        if filings_20f:
            print(f"\nFound {len(filings_20f)} 20-F filings")
            latest = filings_20f.latest()
            print(f"Latest 20-F: {latest.filing_date} - {latest.accession_number}")
            return latest
        else:
            print("\nNo 20-F filings found")
            return None

    except Exception as e:
        print(f"Error exploring {company_name}: {e}")
        traceback.print_exc()
        return None


def find_known_20f_companies():
    """Find companies that are known to file 20-F forms."""

    # Some well-known foreign companies that should file 20-F
    known_companies = [
        ('0001776985', 'BioNTech SE'),           # German biotech
        ('0001707432', 'Zoom Video Communications'),  # May have foreign subsidiary
        ('0001034054', 'American Depositary Receipts'), # May be related
        ('0001018724', 'Amazon.com Inc'),        # Let's see what they file
        ('0001090872', 'Baidu Inc'),             # Chinese company with ADRs
        ('0001614717', 'Moderna Inc'),           # Biotech similar to BioNTech
        ('0001477932', 'Astrazeneca PLC'),       # British pharmaceutical
    ]

    results = {}

    for cik, name in known_companies:
        try:
            latest_20f = explore_company_forms(cik, name)
            results[name] = latest_20f
        except Exception as e:
            print(f"Failed to process {name}: {e}")
            results[name] = None

    return results


def test_20f_with_working_company():
    """Test 20-F parsing with a company that definitely has good data."""

    print(f"\n{'='*80}")
    print("TESTING 20-F PARSING WITH KNOWN GOOD COMPANY")
    print(f"{'='*80}")

    # Try to find companies with 20-F forms through search
    try:
        recent_20fs = get_filings(form="20-F")
        print(f"Found {len(recent_20fs)} recent 20-F filings")

        for filing in recent_20fs[:3]:  # Test first 3
            print(f"\nTesting {filing.company} - {filing.filing_date}")
            try:
                xbrl = filing.xbrl()
                statements = xbrl.statements

                # Try to get balance sheet
                bs = statements.balance_sheet()
                if bs and hasattr(bs, 'data') and len(bs.data) > 0:
                    print(f"  ✓ Balance sheet: {len(bs.data)} rows")
                else:
                    print(f"  ✗ Balance sheet: Empty")

                # Try income statement
                income = statements.income_statement()
                if income and hasattr(income, 'data') and len(income.data) > 0:
                    print(f"  ✓ Income statement: {len(income.data)} rows")
                else:
                    print(f"  ✗ Income statement: Empty")

                # Try cash flow
                cf = statements.cashflow_statement()
                if cf and hasattr(cf, 'data') and len(cf.data) > 0:
                    print(f"  ✓ Cash flow: {len(cf.data)} rows")
                else:
                    print(f"  ✗ Cash flow: Empty")

            except Exception as e:
                print(f"  Error parsing XBRL: {e}")

    except Exception as e:
        print(f"Error getting recent 20-F filings: {e}")
        traceback.print_exc()


if __name__ == "__main__":

    print("Exploring 20-F filing patterns for Issue #446")
    print("="*80)

    # First explore the companies from the issue
    print("\n1. EXPLORING COMPANIES FROM ISSUE #446")
    issue_companies = [
        ('0001468554', 'Shell plc'),
        ('0001104659', 'Deutsche Bank AG'),
        ('0001776985', 'BioNTech SE')
    ]

    for cik, name in issue_companies:
        explore_company_forms(cik, name)

    # Find other known 20-F companies
    print("\n\n2. FINDING OTHER 20-F COMPANIES")
    find_known_20f_companies()

    # Test with recent 20-F filings
    print("\n\n3. TESTING RECENT 20-F FILINGS")
    test_20f_with_working_company()