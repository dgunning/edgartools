"""
Check Assets values for Q3 2025 to confirm which period_end dates
correspond to the duplicate values shown in the balance sheet.
"""

from edgar import Company

c = Company("AAPL")
facts = c.get_facts()

# Get all balance sheet facts for Q3 2025
balance_sheet_facts = [f for f in facts if f.statement_type == 'BalanceSheet']
q3_2025_facts = [f for f in balance_sheet_facts if f.fiscal_year == 2025 and f.fiscal_period == 'Q3']

print("Checking Assets values for fiscal Q3 2025:")
print("=" * 80)

# Look for Assets concept (try various names)
assets_concepts = ['Assets', 'us-gaap:Assets']
for concept_name in assets_concepts:
    assets_facts = [f for f in q3_2025_facts if f.concept == concept_name]
    if assets_facts:
        print(f"\nFound {len(assets_facts)} facts for concept '{concept_name}':")
        for fact in sorted(assets_facts, key=lambda f: f.period_end or ""):
            print(f"\n  ${fact.numeric_value/1e9:.1f}B")
            print(f"    Period End: {fact.period_end}")
            print(f"    Filing: {fact.form_type} on {fact.filing_date}")
            print(f"    Accession: {fact.accession}")

# Also check by looking at all concepts in Q3 2025 to see which ones have Assets-related names
print("\n" + "=" * 80)
print("All unique concepts in fiscal Q3 2025:")
unique_concepts = sorted(set(f.concept for f in q3_2025_facts))
assets_related = [c for c in unique_concepts if 'asset' in c.lower()]
print(f"\nAssets-related concepts ({len(assets_related)}):")
for concept in assets_related:
    facts_count = len([f for f in q3_2025_facts if f.concept == concept])
    print(f"  - {concept}: {facts_count} facts")
