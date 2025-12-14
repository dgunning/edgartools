"""
Validation script for Issue #503: Statement selection fix

Tests that complete balance sheets are selected instead of fragments,
especially for pre-2020 filings where fragment selection was common.
"""

from edgar import Company

# Test companies with focus on pre-2020 filings and diverse industries
TEST_CASES = [
    # (ticker, industry, year, expected_min_rows)
    ("WST", "Medical Devices", 2015, 50),  # Original issue company
    ("BSX", "Medical Devices", 2017, 50),  # Mentioned in issue
    ("JPM", "Banking", 2016, 100),
    ("WMT", "Retail", 2018, 40),
    ("XOM", "Energy", 2015, 50),
    ("GE", "Industrial", 2017, 50),
    ("PG", "Consumer Goods", 2019, 40),
    ("MSFT", "Technology", 2016, 50),
    ("BA", "Aerospace", 2018, 50),
]

# Essential concepts that should appear in a complete balance sheet
ESSENTIAL_CONCEPTS = [
    'assets',
    'liabilities',
    'equity',
    'cash',
    'receivable',
]

# Fragment indicators that shouldn't dominate a complete balance sheet
FRAGMENT_INDICATORS = [
    'pension',
    'retirement',
    'postretirement',
    'benefit',
    'schedule',
    'supplemental',
    'disclosure'
]

def validate_statement_selection(ticker, industry, year, expected_min_rows):
    """Validate that complete balance sheet is selected, not a fragment"""
    print(f"\n{'='*80}")
    print(f"Testing: {ticker} ({industry}) - Year {year}")
    print(f"{'='*80}")

    try:
        company = Company(ticker)
        filings = company.get_filings(form="10-K")

        # Find filing for specific year
        filing = None
        for f in filings:
            if f.filing_date.year == year:
                filing = f
                break

        if filing is None:
            print(f"⚠️  WARNING: Could not find {year} 10-K filing for {ticker}")
            return {
                'ticker': ticker,
                'year': year,
                'status': 'SKIP',
                'reason': f'No {year} filing found'
            }

        print(f"Filing: {filing.form} filed on {filing.filing_date}")

        xbrl = filing.xbrl()
        balance_sheet = xbrl.statements.balance_sheet()

        if balance_sheet is None:
            print(f"❌ FAIL: Could not load balance sheet for {ticker} {year}")
            return {
                'ticker': ticker,
                'year': year,
                'status': 'FAIL',
                'reason': 'Balance sheet not found'
            }

        df = balance_sheet.to_dataframe()
        total_rows = len(df)

        print(f"Total rows: {total_rows} (expected >= {expected_min_rows})")

        # Check row count (complete sheets should have reasonable number of rows)
        if total_rows < expected_min_rows:
            print("⚠️  WARNING: Row count below expected minimum")
            status = "⚠️  WARN: Low row count"
        else:
            status = "✅ PASS"

        # Check for essential balance sheet concepts
        labels = df['label'].str.lower().tolist()
        found_concepts = []
        for concept in ESSENTIAL_CONCEPTS:
            if any(concept in label for label in labels):
                found_concepts.append(concept)

        essential_count = len(found_concepts)
        print(f"Essential concepts found: {essential_count}/{len(ESSENTIAL_CONCEPTS)}")
        print(f"  Found: {found_concepts}")

        if essential_count < 4:
            print("❌ FAIL: Missing essential balance sheet concepts")
            print(f"  Expected at least 4 of: {ESSENTIAL_CONCEPTS}")
            status = "❌ FAIL: Missing essential concepts"

        # Check for fragment indicators in first few non-abstract concepts
        non_abstract_df = df[df['abstract'] == False]
        if len(non_abstract_df) > 0:
            first_concepts = non_abstract_df.head(5)
            fragment_found = False

            for _, row in first_concepts.iterrows():
                concept_lower = row['concept'].lower()
                label_lower = row['label'].lower()

                for indicator in FRAGMENT_INDICATORS:
                    if indicator in concept_lower or indicator in label_lower:
                        print(f"⚠️  Fragment indicator '{indicator}' found in: {row['label']}")
                        fragment_found = True
                        break

            if fragment_found and essential_count < 4:
                print("❌ FAIL: Appears to be a fragment, not complete balance sheet")
                status = "❌ FAIL: Fragment selected"

        # Show first few line items
        print("\nFirst 5 line items:")
        for idx, (_, row) in enumerate(non_abstract_df.head(5).iterrows(), 1):
            label = row['label'][:60]
            print(f"  {idx}. {label}")

        print(f"\nStatus: {status}")

        return {
            'ticker': ticker,
            'industry': industry,
            'year': year,
            'status': status,
            'total_rows': total_rows,
            'essential_concepts': essential_count,
            'expected_min_rows': expected_min_rows
        }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ticker': ticker,
            'year': year,
            'status': 'ERROR',
            'error': str(e)
        }

def main():
    print("="*80)
    print("VALIDATION: Issue #503 - Statement Selection Fix")
    print("="*80)
    print("\nTesting that complete balance sheets are selected instead of fragments.")
    print("Focus on pre-2020 filings where fragment selection was problematic.\n")

    results = []
    for ticker, industry, year, min_rows in TEST_CASES:
        result = validate_statement_selection(ticker, industry, year, min_rows)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(1 for r in results if '✅' in r['status'])
    warnings = sum(1 for r in results if '⚠️' in r['status'])
    failed = sum(1 for r in results if 'FAIL' in r['status'])
    errors = sum(1 for r in results if 'ERROR' in r['status'])
    skipped = sum(1 for r in results if 'SKIP' in r['status'])

    print(f"\nTotal test cases: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"❌ Failed: {failed}")
    print(f"❌ Errors: {errors}")
    print(f"⏭️  Skipped: {skipped}")

    # Detailed results table
    print("\n" + "-"*80)
    print(f"{'Ticker':<8} {'Year':<6} {'Rows':<8} {'Essential':<10} {'Status'}")
    print("-"*80)
    for r in results:
        ticker = r['ticker']
        year = r['year']
        if 'total_rows' in r:
            rows = r['total_rows']
            essential = f"{r['essential_concepts']}/5"
            status = r['status']
        else:
            rows = "N/A"
            essential = "N/A"
            status = r['status']

        print(f"{ticker:<8} {year:<6} {str(rows):<8} {essential:<10} {status}")

    print("\n" + "="*80)
    print("Validation complete!")
    print("="*80)

    if failed > 0 or errors > 0:
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
