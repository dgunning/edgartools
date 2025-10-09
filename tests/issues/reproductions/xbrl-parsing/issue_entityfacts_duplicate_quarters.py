"""
Reproduction for duplicate quarterly periods in EntityFacts balance sheet.

Issue: When calling Company("AAPL").balance_sheet(annual=False),
Q3 2025 appears twice with different values.

Root Cause: Period keys use (fiscal_year, fiscal_period, period_end),
so facts with same fiscal period but different period_end dates
(from amendments or different filings) appear as separate columns.

Expected: One Q3 2025 column with the most recent/authoritative data
Actual: Two Q3 2025 columns with different values
"""

from edgar import Company

print("Testing quarterly balance sheet for duplicate periods...")
print("=" * 80)

c = Company("AAPL")
bs = c.balance_sheet(annual=False)

print(f"\nPeriods shown: {bs.periods}")
print(f"Period count: {len(bs.periods)}")

# Check for duplicates
from collections import Counter
period_counts = Counter(bs.periods)
duplicates = {period: count for period, count in period_counts.items() if count > 1}

if duplicates:
    print(f"\n🔴 DUPLICATE PERIODS FOUND: {duplicates}")
    print("\nThis is the bug - same fiscal period appearing multiple times!")
else:
    print("\n✅ No duplicate periods found")

print("\n" + "=" * 80)
print("Displaying the balance sheet:")
print(bs)
