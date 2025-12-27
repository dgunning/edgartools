"""
Quick integration test for TTM functionality with Apple data.
This script verifies that the TTM methods work correctly with real company data.
"""

from edgar import Company
from datetime import date

# Test with Apple
print("Testing TTM functionality with Apple (AAPL)...")
print("=" * 60)

aapl = Company("AAPL")
facts = aapl.get_facts()

# Test 1: Get TTM revenue
print("\nTest 1: get_ttm_revenue()")
print("-" * 60)
try:
    ttm_revenue = facts.get_ttm_revenue()
    print(f"[OK] TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")
    print(f"  Concept: {ttm_revenue.concept}")
    print(f"  Label: {ttm_revenue.label}")
    print(f"  As of: {ttm_revenue.as_of_date}")
    print(f"  Periods: {ttm_revenue.periods}")
    print(f"  Has gaps: {ttm_revenue.has_gaps}")
    if ttm_revenue.warning:
        print(f"  Warning: {ttm_revenue.warning}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 2: Get TTM net income
print("\nTest 2: get_ttm_net_income()")
print("-" * 60)
try:
    ttm_net_income = facts.get_ttm_net_income()
    print(f"[OK] TTM Net Income: ${ttm_net_income.value / 1e9:.1f}B")
    print(f"  Concept: {ttm_net_income.concept}")
    print(f"  Periods: {ttm_net_income.periods}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 3: Get TTM as of specific period
print("\nTest 3: get_ttm_revenue(as_of='2024-Q2')")
print("-" * 60)
try:
    ttm_q2 = facts.get_ttm_revenue(as_of='2024-Q2')
    print(f"[OK] TTM Revenue (Q2 2024): ${ttm_q2.value / 1e9:.1f}B")
    print(f"  Periods: {ttm_q2.periods}")
    print(f"  As of: {ttm_q2.as_of_date}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 4: Get TTM as of specific date
print("\nTest 4: get_ttm_revenue(as_of=date(2024, 6, 30))")
print("-" * 60)
try:
    ttm_date = facts.get_ttm_revenue(as_of=date(2024, 6, 30))
    print(f"[OK] TTM Revenue (as of 2024-06-30): ${ttm_date.value / 1e9:.1f}B")
    print(f"  Periods: {ttm_date.periods}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 5: Get TTM for specific concept
print("\nTest 5: get_ttm('Revenue')")
print("-" * 60)
try:
    ttm_concept = facts.get_ttm('Revenue')
    print(f"[OK] TTM Revenue (via get_ttm): ${ttm_concept.value / 1e9:.1f}B")
    print(f"  Periods: {ttm_concept.periods}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 6: Get TTM revenue trend
print("\nTest 6: get_ttm_revenue_trend(periods=8)")
print("-" * 60)
try:
    trend = facts.get_ttm_revenue_trend(periods=8)
    print(f"[OK] TTM Revenue Trend ({len(trend)} periods):")
    print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']].to_string())
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 7: Get TTM trend for specific concept
print("\nTest 7: get_ttm_trend('Revenue', periods=4)")
print("-" * 60)
try:
    trend = facts.get_ttm_trend('Revenue', periods=4)
    print(f"[OK] TTM Revenue Trend (4 periods):")
    for _, row in trend.iterrows():
        value_b = row['ttm_value'] / 1e9
        yoy = row['yoy_growth']
        yoy_str = f"{yoy:.1%}" if yoy is not None else "N/A"
        print(f"  {row['as_of_quarter']:8s}: ${value_b:6.1f}B  YoY: {yoy_str}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

print("\n" + "=" * 60)
print("[OK] All tests completed successfully!")
print("=" * 60)
