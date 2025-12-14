"""
Validation script for Issue #504: Dimensional filtering fix

Tests that dimensional data is correctly included in balance sheets across
diverse companies from different industries.
"""

from edgar import Company

# Test companies across different industries
TEST_COMPANIES = [
    ("JPM", "Banking"),
    ("WMT", "Retail"),
    ("MSFT", "Technology"),
    ("XOM", "Energy"),
    ("UNH", "Healthcare"),
    ("DUK", "Utilities"),
    ("BA", "Manufacturing/Aerospace"),
    ("PG", "Consumer Goods"),
    ("APD", "Industrial Gases"),  # Original issue company
]

def validate_dimensional_filtering(ticker, industry):
    """Validate that dimensional data appears in balance sheet"""
    print(f"\n{'='*80}")
    print(f"Testing: {ticker} ({industry})")
    print(f"{'='*80}")

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest(1)
        print(f"Filing: {filing.form} filed on {filing.filing_date}")

        xbrl = filing.xbrl()
        balance_sheet = xbrl.statements.balance_sheet()

        if balance_sheet is None:
            print(f"⚠️  WARNING: Could not load balance sheet for {ticker}")
            return None

        df = balance_sheet.to_dataframe()

        # Check dimensional column exists
        if 'dimension' not in df.columns:
            print("❌ FAIL: 'dimension' column missing from dataframe")
            return {
                'ticker': ticker,
                'industry': industry,
                'status': 'FAIL',
                'error': 'dimension column missing'
            }

        # Count dimensional rows
        total_rows = len(df)
        dimensional_rows = df['dimension'].sum()
        pct_dimensional = (dimensional_rows / total_rows * 100) if total_rows > 0 else 0

        print(f"Total rows: {total_rows}")
        print(f"Dimensional rows: {dimensional_rows} ({pct_dimensional:.1f}%)")

        # Show some examples of dimensional data if present
        if dimensional_rows > 0:
            print("\nSample dimensional rows:")
            dim_rows = df[df['dimension'] == True].head(3)
            for idx, row in dim_rows.iterrows():
                concept = row['concept']
                label = row['label']
                print(f"  - {label} ({concept})")

        # Determine status
        status = "✅ PASS"
        if dimensional_rows == 0:
            status = "⚠️  INFO: No dimensional data (may be expected for this company)"

        print(f"\nStatus: {status}")

        return {
            'ticker': ticker,
            'industry': industry,
            'status': status,
            'total_rows': total_rows,
            'dimensional_rows': dimensional_rows,
            'pct_dimensional': pct_dimensional
        }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ticker': ticker,
            'industry': industry,
            'status': 'ERROR',
            'error': str(e)
        }

def main():
    print("="*80)
    print("VALIDATION: Issue #504 - Dimensional Filtering Fix")
    print("="*80)
    print("\nTesting that dimensional data is included in balance sheets by default.")
    print("Expected: dimensional column present, some companies have dimensional rows\n")

    results = []
    for ticker, industry in TEST_COMPANIES:
        result = validate_dimensional_filtering(ticker, industry)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(1 for r in results if '✅' in r['status'])
    info = sum(1 for r in results if '⚠️' in r['status'])
    failed = sum(1 for r in results if 'FAIL' in r['status'])
    errors = sum(1 for r in results if 'ERROR' in r['status'])

    print(f"\nTotal companies tested: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"⚠️  Info (no dimensional data): {info}")
    print(f"❌ Failed: {failed}")
    print(f"❌ Errors: {errors}")

    # Detailed results table
    print("\n" + "-"*80)
    print(f"{'Ticker':<8} {'Industry':<25} {'Total':<8} {'Dim':<8} {'%':<8} {'Status'}")
    print("-"*80)
    for r in results:
        ticker = r['ticker']
        industry = r['industry'][:24]
        if 'total_rows' in r:
            total = r['total_rows']
            dim = r['dimensional_rows']
            pct = f"{r['pct_dimensional']:.1f}%"
            status = r['status']
        else:
            total = dim = pct = "N/A"
            status = r['status']

        print(f"{ticker:<8} {industry:<25} {str(total):<8} {str(dim):<8} {pct:<8} {status}")

    print("\n" + "="*80)
    print("Validation complete!")
    print("="*80)

    if failed > 0 or errors > 0:
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
