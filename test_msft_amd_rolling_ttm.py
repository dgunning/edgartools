"""
Rolling TTM Validation for MSFT and AMD
Shows TTM calculated for every quarter, not just the latest
"""
from edgar import Company
from datetime import date, timedelta

def test_rolling_ttm(ticker, num_periods=12):
    print("=" * 100)
    print(f"Company: {ticker}")
    print("=" * 100)

    try:
        company = Company(ticker)
        facts = company.get_facts()

        print(f"\nCompany Name: {company.name}")
        print(f"CIK: {company.cik}")

        # Get the TTM trend which gives us rolling TTM for multiple periods
        print(f"\nCalculating Rolling TTM for last {num_periods} quarters...")

        try:
            trend_df = facts.get_ttm_revenue_trend(periods=num_periods)

            print(f"\nTotal periods with TTM data: {len(trend_df)}")
            print("=" * 100)

            # Display rolling TTM in table format
            print(f"\n{'#':<4} {'As of Quarter':<15} {'Fiscal Year':>12} {'Fiscal Period':>14} {'TTM Revenue':>14} {'YoY Growth':>12} {'Quarters Used':<40}")
            print("-" * 120)

            for idx, (_, row) in enumerate(trend_df.head(num_periods).iterrows(), 1):
                quarter = row['as_of_quarter']
                fiscal_year = row['fiscal_year']
                fiscal_period = row['fiscal_period']
                ttm_val = row['ttm_value'] / 1e9
                yoy = row['yoy_growth']
                periods_included = row.get('periods_included', row.get('periods', []))

                yoy_str = f"{yoy*100:+.1f}%" if yoy is not None and not pd.isna(yoy) else "N/A"
                periods_str = ", ".join([f"{fy} {fp}" for fy, fp in periods_included]) if periods_included else "N/A"

                print(f"{idx:<4} {quarter:<15} {fiscal_year:>12} {fiscal_period:>14} ${ttm_val:>12.2f}B {yoy_str:>12} {periods_str:<40}")

            # Show detailed breakdown for the most recent TTM
            print("\n" + "=" * 100)
            print("DETAILED BREAKDOWN - Most Recent TTM")
            print("=" * 100)

            # Get the most recent TTM with full details
            latest_ttm = facts.get_ttm_revenue()

            print(f"\nTTM as of: {latest_ttm.as_of_date}")
            print(f"TTM Value: ${latest_ttm.value/1e9:.2f}B")
            print(f"Periods: {latest_ttm.periods}")

            print(f"\nQuarterly Components:")
            print(f"{'#':<3} {'Period':<12} {'Value':>12} {'Dates':<30} {'Days':>5} {'Source':<25}")
            print("-" * 100)

            for i, fact in enumerate(latest_ttm.period_facts, 1):
                days = (fact.period_end - fact.period_start).days
                period = f"{fact.fiscal_period} {fact.fiscal_year}"
                value = f"${fact.numeric_value/1e9:.2f}B"
                dates = f"{fact.period_start} to {fact.period_end}"

                if fact.calculation_context and 'derived' in fact.calculation_context:
                    if 'ytd6_minus_q1' in fact.calculation_context:
                        source = "DERIVED (YTD_6M - Q1)"
                    elif 'ytd9_minus_ytd6' in fact.calculation_context:
                        source = "DERIVED (YTD_9M - YTD_6M)"
                    elif 'fy_minus_ytd9' in fact.calculation_context:
                        source = "DERIVED (FY - YTD_9M)"
                    else:
                        source = f"DERIVED ({fact.calculation_context})"
                else:
                    source = "REPORTED (discrete)"

                print(f"{i:<3} {period:<12} {value:>12} {dates:<30} {days:>5} {source:<25}")

            # Verify sum
            total = sum(f.numeric_value for f in latest_ttm.period_facts)
            print(f"\nMath Verification:")
            print(f"  Sum of 4 quarters: ${total/1e9:.2f}B")
            print(f"  TTM value:         ${latest_ttm.value/1e9:.2f}B")
            print(f"  Match: {'[OK]' if abs(total - latest_ttm.value) < 1e6 else '[ERROR]'}")

            # Show warnings if any
            if latest_ttm.warning:
                print(f"\nWarnings:")
                for line in latest_ttm.warning.split('. '):
                    if line.strip():
                        print(f"  - {line.strip()}")

        except Exception as e:
            print(f"\n[ERROR] Could not calculate TTM trend: {str(e)[:200]}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n[ERROR] Failed to load company data: {str(e)[:200]}")
        import traceback
        traceback.print_exc()

    print("\n")

# Import pandas for NaN checking
import pandas as pd

# Test both companies with 12 periods
print("\n" + "=" * 100)
print("ROLLING TTM VALIDATION - Microsoft and AMD")
print("=" * 100)
print("\n")

test_rolling_ttm("MSFT", num_periods=12)
test_rolling_ttm("AMD", num_periods=12)

print("=" * 100)
print("VALIDATION COMPLETE")
print("=" * 100)
