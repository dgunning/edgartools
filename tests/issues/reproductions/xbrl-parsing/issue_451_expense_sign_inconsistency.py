"""
Issue #451: Inconsistent Sign for Cost/Expense Metrics

Reproduction script for inconsistent signs in expense metrics:
- Operating Expense is positive (correct)
- Income Tax Expense is negative in 10-Q but positive in 10-K (inconsistent)
- Cost of Goods Sold is negative (should be positive)

Reporter: @Velikolay
Filing: Apple Inc. (AAPL)
Forms: 10-K (0000320193-20-000062), 10-Q (0000320193-20-000052)
"""

from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL
import pandas as pd


def reproduce_issue_451():
    """Reproduce the expense sign inconsistency issue with Apple filings."""

    # Set proper identity for SEC API
    set_identity("Research Team research@edgartools.dev")

    print("=== Issue #451: Expense Sign Inconsistency Reproduction ===\n")

    # Test cases from the issue report
    test_cases = [
        {
            "form": "10-K",
            "accession": "0000320193-20-000062",
            "description": "Apple 10-K for 2020"
        },
        {
            "form": "10-Q",
            "accession": "0000320193-20-000052",
            "description": "Apple 10-Q for 2020"
        }
    ]

    company = Company("AAPL")
    results = []

    for test_case in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {test_case['description']}")
        print(f"Accession: {test_case['accession']}")
        print(f"{'='*60}\n")

        try:
            # Get the specific filing
            filing = company.get_filings(accession_number=test_case['accession']).latest()

            # Parse XBRL and get income statement
            xbrl = XBRL.from_filing(filing)
            stmt = xbrl.statements.income_statement()
            df = stmt.to_dataframe()

            print(f"Income Statement has {len(df)} rows")
            print(f"Columns: {df.columns.tolist()}\n")

            # Metrics to check
            metrics_to_check = [
                ("OperatingExpenses", "Operating Expenses"),
                ("IncomeTaxExpense", "Income Tax Expense"),
                ("CostOfGoodsAndServicesSold", "Cost of Goods and Services Sold"),
                ("CostOfGoodsSold", "Cost of Goods Sold"),
                ("CostOfRevenue", "Cost of Revenue")
            ]

            case_results = {
                'form': test_case['form'],
                'accession': test_case['accession'],
                'filing_date': filing.filing_date,
                'period': filing.period_of_report
            }

            for concept_pattern, metric_name in metrics_to_check:
                # Find entries matching this concept
                rows = df[df['concept'].str.contains(concept_pattern, case=False, na=False)]

                if not rows.empty:
                    # Get main entry (non-dimensional)
                    # Filter for rows where dimension is False (not a dimensional fact)
                    dimension_col = rows.get('dimension')

                    if dimension_col is not None:
                        main_entry = rows[dimension_col == False]
                    else:
                        main_entry = rows

                    if not main_entry.empty:
                        # Find most recent period column (date columns)
                        # Look for columns that are dates (YYYY-MM-DD format) but NOT quarters (Q#)
                        import re
                        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
                        date_columns = [col for col in df.columns
                                      if isinstance(col, str) and date_pattern.match(col)]

                        if date_columns:
                            latest_col = max(date_columns)

                            # Find a row that has a non-empty numeric value
                            value = None
                            for idx, row in main_entry.iterrows():
                                val = row.get(latest_col, None)
                                if val is not None and isinstance(val, (int, float)):
                                    value = val
                                    break

                            if value is not None and isinstance(value, (int, float)):
                                sign = "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "ZERO"
                                sign_symbol = "✅" if value > 0 else "❌"

                                print(f"{metric_name:30s}: {value:>20,.0f} ({sign}) {sign_symbol}")

                                case_results[f"{metric_name}_value"] = value
                                case_results[f"{metric_name}_sign"] = sign
                            else:
                                print(f"{metric_name:30s}: {'N/A':>20s}")
                                case_results[f"{metric_name}_value"] = None
                                case_results[f"{metric_name}_sign"] = "N/A"
                        else:
                            print(f"{metric_name:30s}: No date columns found")
                    else:
                        print(f"{metric_name:30s}: No main entry (all dimensional)")
                else:
                    print(f"{metric_name:30s}: Not found in statement")
                    case_results[f"{metric_name}_value"] = None
                    case_results[f"{metric_name}_sign"] = "NOT_FOUND"

            results.append(case_results)

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Summary comparison
    print("\n" + "="*60)
    print("SUMMARY: Sign Consistency Analysis")
    print("="*60)

    if len(results) >= 2:
        # Compare 10-K vs 10-Q
        tenk_result = next((r for r in results if r['form'] == '10-K'), None)
        tenq_result = next((r for r in results if r['form'] == '10-Q'), None)

        if tenk_result and tenq_result:
            print("\nSign Comparison: 10-K vs 10-Q\n")

            for metric in ["Operating Expenses", "Income Tax Expense", "Cost of Goods and Services Sold", "Cost of Goods Sold", "Cost of Revenue"]:
                tenk_sign = tenk_result.get(f"{metric}_sign", "N/A")
                tenq_sign = tenq_result.get(f"{metric}_sign", "N/A")

                consistent = "✅ CONSISTENT" if tenk_sign == tenq_sign else "❌ INCONSISTENT"

                print(f"{metric:30s}: 10-K={tenk_sign:10s} | 10-Q={tenq_sign:10s} | {consistent}")

    print("\n" + "="*60)
    print("EXPECTED BEHAVIOR:")
    print("="*60)
    print("All expense/cost metrics should be POSITIVE across all filing types")
    print("  - Operating Expenses: POSITIVE ✅")
    print("  - Income Tax Expense: POSITIVE ✅")
    print("  - Cost of Goods and Services Sold: POSITIVE ✅")
    print("  - Cost of Goods Sold: POSITIVE ✅")
    print("  - Cost of Revenue: POSITIVE ✅")

    return results


if __name__ == "__main__":
    try:
        results = reproduce_issue_451()
        print("\n✓ Reproduction completed successfully")
    except Exception as e:
        print(f"\n✗ Error during reproduction: {e}")
        import traceback
        traceback.print_exc()
