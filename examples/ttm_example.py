"""
TTM (Trailing Twelve Months) Calculation Examples
==================================================

This example demonstrates how to use EdgarTools' TTM calculation features
to analyze rolling 12-month financial metrics from quarterly data.

TTM calculations provide a smoothed view of financial performance by
aggregating 4 consecutive quarters, eliminating seasonal variations.
"""

from edgar import Company
from datetime import date
import pandas as pd

# ==============================================================================
# Basic TTM Calculations
# ==============================================================================

print("=" * 70)
print("TTM (Trailing Twelve Months) Calculation Examples")
print("=" * 70)

# Get company and facts
aapl = Company("AAPL")
facts = aapl.get_facts()

# Example 1: Get most recent TTM revenue
print("\n1. Most Recent TTM Revenue")
print("-" * 70)
ttm_revenue = facts.get_ttm_revenue()
print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")
print(f"Concept: {ttm_revenue.concept}")
print(f"As of date: {ttm_revenue.as_of_date}")
print(f"Periods included: {ttm_revenue.periods}")
if ttm_revenue.warning:
    print(f"Warning: {ttm_revenue.warning}")

# Example 2: Get TTM net income
print("\n2. TTM Net Income")
print("-" * 70)
ttm_net_income = facts.get_ttm_net_income()
print(f"TTM Net Income: ${ttm_net_income.value / 1e9:.1f}B")
print(f"Periods: {ttm_net_income.periods}")

# Example 3: Calculate TTM profit margin
print("\n3. TTM Profit Margin")
print("-" * 70)
profit_margin = (ttm_net_income.value / ttm_revenue.value) * 100
print(f"TTM Profit Margin: {profit_margin:.1f}%")

# ==============================================================================
# Historical TTM Calculations
# ==============================================================================

# Example 4: Get TTM as of specific quarter
print("\n4. Historical TTM (as of Q2 2024)")
print("-" * 70)
ttm_q2_2024 = facts.get_ttm_revenue(as_of='2024-Q2')
print(f"TTM Revenue (Q2 2024): ${ttm_q2_2024.value / 1e9:.1f}B")
print(f"Periods: {ttm_q2_2024.periods}")

# Example 5: Get TTM as of specific date
print("\n5. Historical TTM (as of specific date)")
print("-" * 70)
ttm_date = facts.get_ttm_revenue(as_of=date(2023, 12, 31))
print(f"TTM Revenue (as of 2023-12-31): ${ttm_date.value / 1e9:.1f}B")
print(f"Periods: {ttm_date.periods}")

# ==============================================================================
# TTM for Specific Concepts
# ==============================================================================

# Example 6: Get TTM for any concept
print("\n6. TTM for Specific Concepts")
print("-" * 70)
try:
    # Operating income
    ttm_op_income = facts.get_ttm('OperatingIncomeLoss')
    print(f"TTM Operating Income: ${ttm_op_income.value / 1e9:.1f}B")

    # Operating margin
    op_margin = (ttm_op_income.value / ttm_revenue.value) * 100
    print(f"TTM Operating Margin: {op_margin:.1f}%")
except Exception as e:
    print(f"Could not calculate: {e}")

# ==============================================================================
# TTM Trend Analysis
# ==============================================================================

# Example 7: Get TTM revenue trend
print("\n7. TTM Revenue Trend (8 quarters)")
print("-" * 70)
trend = facts.get_ttm_revenue_trend(periods=8)
print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']].to_string())

# Example 8: Visualize TTM growth
print("\n8. TTM Year-over-Year Growth Analysis")
print("-" * 70)
# Get trend with YoY growth
trend_df = facts.get_ttm_revenue_trend(periods=12)

# Filter to rows with YoY growth data
growth_df = trend_df[trend_df['yoy_growth'].notna()]

if not growth_df.empty:
    print(f"\nAverage YoY Growth: {growth_df['yoy_growth'].mean():.1%}")
    print(f"Latest YoY Growth: {growth_df.iloc[0]['yoy_growth']:.1%}")
    print(f"Highest YoY Growth: {growth_df['yoy_growth'].max():.1%}")
    print(f"Lowest YoY Growth: {growth_df['yoy_growth'].min():.1%}")

# Example 9: Custom TTM trend analysis
print("\n9. Custom TTM Trend for Multiple Concepts")
print("-" * 70)
concepts = {
    'Revenue': 'RevenueFromContractWithCustomerExcludingAssessedTax',
    'Gross Profit': 'GrossProfit',
    'Operating Income': 'OperatingIncomeLoss'
}

results = {}
for label, concept in concepts.items():
    try:
        trend = facts.get_ttm_trend(concept, periods=4)
        if not trend.empty:
            latest_ttm = trend.iloc[0]['ttm_value']
            results[label] = latest_ttm / 1e9  # Convert to billions
    except Exception as e:
        print(f"Could not get TTM for {label}: {e}")

if results:
    print("\nLatest TTM Values (Billions):")
    for label, value in results.items():
        print(f"  {label:20s}: ${value:8.1f}B")

# ==============================================================================
# TTM Statements
# ==============================================================================

# Example 10: Build complete TTM income statement
print("\n10. TTM Income Statement")
print("-" * 70)
try:
    ttm_income_stmt = facts.get_ttm_income_statement()
    print(f"Statement Type: {ttm_income_stmt.statement_type}")
    print(f"As of: {ttm_income_stmt.as_of_date}")
    print(f"Number of line items: {len(ttm_income_stmt.items)}")

    # Convert to DataFrame for easy viewing
    df = ttm_income_stmt.to_dataframe()
    print("\nSample line items:")
    print(df.head(10).to_string())
except Exception as e:
    print(f"Could not build TTM income statement: {e}")

# Example 11: Build TTM cash flow statement
print("\n11. TTM Cash Flow Statement")
print("-" * 70)
try:
    ttm_cf_stmt = facts.get_ttm_cashflow_statement()
    print(f"Statement Type: {ttm_cf_stmt.statement_type}")
    print(f"Number of line items: {len(ttm_cf_stmt.items)}")

    df = ttm_cf_stmt.to_dataframe()
    print("\nSample line items:")
    print(df.head(10).to_string())
except Exception as e:
    print(f"Could not build TTM cash flow statement: {e}")

# ==============================================================================
# Advanced TTM Analysis
# ==============================================================================

# Example 12: Compare TTM vs Annual
print("\n12. Compare TTM vs Most Recent Annual Results")
print("-" * 70)
try:
    # Get most recent annual income statement
    annual_stmt = facts.income_statement(periods=1, annual=True)

    # Get TTM
    ttm = facts.get_ttm_revenue()

    print(f"TTM Revenue (most recent): ${ttm.value / 1e9:.1f}B")
    print(f"TTM as of: {ttm.as_of_date}")
    print(f"TTM periods: {ttm.periods}")

    print(f"\nThis shows current run-rate vs last annual report.")
except Exception as e:
    print(f"Could not compare: {e}")

# Example 13: Multi-company TTM comparison
print("\n13. Multi-Company TTM Comparison")
print("-" * 70)
companies = ['AAPL', 'MSFT', 'GOOGL']
ttm_comparison = {}

for ticker in companies:
    try:
        company = Company(ticker)
        company_facts = company.get_facts()
        ttm = company_facts.get_ttm_revenue()
        ttm_comparison[ticker] = {
            'revenue_b': ttm.value / 1e9,
            'as_of': ttm.as_of_date,
            'periods': ttm.periods
        }
    except Exception as e:
        print(f"Could not get TTM for {ticker}: {e}")

if ttm_comparison:
    print("\nTTM Revenue Comparison:")
    for ticker, data in sorted(ttm_comparison.items(),
                               key=lambda x: x[1]['revenue_b'],
                               reverse=True):
        print(f"  {ticker}: ${data['revenue_b']:8.1f}B (as of {data['as_of']})")

print("\n" + "=" * 70)
print("Examples completed successfully!")
print("=" * 70)
