"""
Investigation script to understand why Q3 2025 appears twice.

This script examines the raw facts data to see what's causing
the duplicate period.
"""

from edgar import Company
from collections import defaultdict
from datetime import date

print("Investigating duplicate Q3 2025 periods...")
print("=" * 80)

c = Company("AAPL")
facts = c.get_facts()

# Get all balance sheet facts
balance_sheet_facts = [f for f in facts if f.statement_type == 'BalanceSheet']

# Group by fiscal_year and fiscal_period
q3_2025_facts = [f for f in balance_sheet_facts if f.fiscal_year == 2025 and f.fiscal_period == 'Q3']

print(f"\nFound {len(q3_2025_facts)} facts for Q3 2025")

# Group by period_end to see the different period_end dates
facts_by_period_end = defaultdict(list)
for fact in q3_2025_facts:
    facts_by_period_end[fact.period_end].append(fact)

print(f"\nNumber of unique period_end dates for Q3 2025: {len(facts_by_period_end)}")
print("\nDetails of each period_end:")
print("-" * 80)

for period_end, facts_list in sorted(facts_by_period_end.items()):
    print(f"\nPeriod End: {period_end}")
    print(f"  Number of facts: {len(facts_list)}")

    # Sample a few facts to see the details
    sample_facts = facts_list[:3]
    for fact in sample_facts:
        print(f"  - {fact.concept}: {fact.value}")
        print(f"    Period: {fact.period_start} to {fact.period_end}")
        print(f"    Filing: {fact.form_type} on {fact.filing_date}")
        print(f"    Accession: {fact.accession}")
        if fact.period_start and fact.period_end:
            duration = (fact.period_end - fact.period_start).days
            print(f"    Duration: {duration} days")
        print()

# Check for Assets concept specifically
print("\n" + "=" * 80)
print("Checking 'Assets' concept specifically:")
print("-" * 80)

assets_facts = [f for f in q3_2025_facts if 'Assets' in f.concept and f.concept == 'Assets']
print(f"\nFound {len(assets_facts)} 'Assets' facts for Q3 2025")

for fact in assets_facts:
    print(f"\nAssets value: ${fact.numeric_value:,.0f}")
    print(f"  Period End: {fact.period_end}")
    print(f"  Period: {fact.period_start} to {fact.period_end}")
    print(f"  Filing: {fact.form_type} on {fact.filing_date}")
    print(f"  Accession: {fact.accession}")
