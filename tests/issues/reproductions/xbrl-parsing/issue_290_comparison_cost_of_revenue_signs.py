"""
Issue #290: Cost of Revenue Sign Comparison Across Companies

Compare Cost of Revenue signs across multiple companies to see if the issue is systematic.
"""

from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL
import pandas as pd

def compare_cost_of_revenue_signs():
    """Compare Cost of Revenue signs across multiple major companies."""

    # Set proper identity for SEC API
    set_identity("Research Team research@edgartools.dev")

    print("=== Cost of Revenue Sign Comparison Across Companies ===\n")

    # Test companies with recent 10-K filings
    companies = [
        ("IBM", "IBM"),
        ("AAPL", "Apple Inc."),
        ("MSFT", "Microsoft Corp"),
        ("GOOGL", "Alphabet Inc"),
        ("AMZN", "Amazon.com Inc")
    ]

    results = []

    for ticker, name in companies:
        try:
            print(f"Analyzing {name} ({ticker})...")

            # Get most recent 10-K filing
            company = Company(ticker)
            filings = company.get_filings(form="10-K").latest(1)

            if not filings:
                print(f"   No 10-K filings found for {ticker}")
                continue

            filing = filings
            print(f"   Filing: {filing.form} for {filing.period_of_report}")
            print(f"   Accession: {filing.accession_number}")

            # Parse XBRL and get income statement
            xbrl = XBRL.from_filing(filing)
            stmt = xbrl.statements.income_statement()
            df = stmt.to_dataframe()

            # Find Cost of Revenue entries
            cost_of_revenue_rows = df[df['concept'].str.contains('CostOfRevenue', case=False, na=False)]

            if not cost_of_revenue_rows.empty:
                # Get the main Cost of Revenue entry (not dimensional)
                main_entry = cost_of_revenue_rows[cost_of_revenue_rows['dimension'] == False]

                if not main_entry.empty:
                    row = main_entry.iloc[0]
                    year_columns = [col for col in df.columns if col.endswith('-12-31') or col.endswith('-09-30')]
                    latest_year = max(year_columns) if year_columns else '2024-12-31'

                    value = row.get(latest_year, 'N/A')
                    sign = "positive" if isinstance(value, (int, float)) and value > 0 else "negative" if isinstance(value, (int, float)) and value < 0 else "N/A"

                    results.append({
                        'company': name,
                        'ticker': ticker,
                        'value': value,
                        'sign': sign,
                        'period': latest_year,
                        'filing_date': filing.filing_date,
                        'accession': filing.accession_number
                    })

                    print(f"   Cost of Revenue: {value} ({sign})")
                else:
                    print(f"   No main Cost of Revenue entry found")
            else:
                print(f"   No Cost of Revenue entries found")

        except Exception as e:
            print(f"   Error analyzing {ticker}: {e}")

        print()

    # Summary
    print("=== SUMMARY ===")
    print(f"Companies analyzed: {len(results)}")

    if results:
        df_results = pd.DataFrame(results)
        print("\nResults:")
        print(df_results[['company', 'ticker', 'value', 'sign', 'period']].to_string(index=False))

        # Count signs
        sign_counts = df_results['sign'].value_counts()
        print(f"\nSign distribution:")
        for sign, count in sign_counts.items():
            print(f"  {sign}: {count} companies")

        # Check if IBM is an outlier
        ibm_result = df_results[df_results['ticker'] == 'IBM']
        if not ibm_result.empty:
            ibm_sign = ibm_result.iloc[0]['sign']
            other_signs = df_results[df_results['ticker'] != 'IBM']['sign'].tolist()

            if ibm_sign != 'N/A' and other_signs:
                is_outlier = all(sign != ibm_sign for sign in other_signs if sign != 'N/A')
                print(f"\nIBM sign pattern: {'Outlier' if is_outlier else 'Consistent with others'}")
                print(f"IBM: {ibm_sign}, Others: {set(other_signs)}")

    return results

if __name__ == "__main__":
    try:
        results = compare_cost_of_revenue_signs()
        print("✓ Comparison completed successfully")
    except Exception as e:
        print(f"✗ Error during comparison: {e}")
        import traceback
        traceback.print_exc()