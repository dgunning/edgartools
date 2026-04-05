"""
Find the Missing $11.58B in JPM's Balance Sheet

Search for ANY concept with a value near $11.58B that could explain the gap.
"""

from edgar import Company, set_identity, use_local_storage
import yfinance as yf

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

print("="*80)
print("FINDING THE MISSING $11.58B")
print("="*80)

# Get JPM data
company = Company('JPM')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()

# Target value
gap_value = 11.58e9  # $11.58B
tolerance = 3e9  # ±$3B

print(f"\n🎯 Searching for values near ${gap_value/1e9:.2f}B (±${tolerance/1e9:.0f}B)")

# Get ALL facts
all_facts_df = xbrl.facts.query().to_dataframe()

print(f"\nTotal facts: {len(all_facts_df)}")

# Filter for instant periods (balance sheet items)
instant_facts = all_facts_df[all_facts_df['period_key'].str.startswith('instant_', na=False)]

print(f"Instant period facts: {len(instant_facts)}")

# Get most recent instant period
if len(instant_facts) > 0:
    latest_period = instant_facts['period_key'].max()
    print(f"Latest instant period: {latest_period}")

    # Filter for latest period
    latest_facts = instant_facts[instant_facts['period_key'] == latest_period]

    # Filter for non-dimensioned (total) values
    if 'full_dimension_label' in latest_facts.columns:
        total_facts = latest_facts[latest_facts['full_dimension_label'].isna()]
    else:
        total_facts = latest_facts

    print(f"Latest period total (non-dimensioned) facts: {len(total_facts)}")

    # Filter for numeric values
    numeric_facts = total_facts[total_facts['numeric_value'].notna()]
    print(f"Numeric facts: {len(numeric_facts)}")

    # Find values near the gap
    print(f"\n" + "="*80)
    print(f"CONCEPTS WITH VALUES NEAR ${gap_value/1e9:.2f}B")
    print("="*80)

    matches = []

    for idx, row in numeric_facts.iterrows():
        value = row['numeric_value']
        diff = abs(value - gap_value)

        if diff <= tolerance:
            matches.append({
                'concept': row['concept'],
                'value': value,
                'diff': diff,
                'value_b': value / 1e9,
                'diff_b': diff / 1e9
            })

    # Sort by difference
    matches.sort(key=lambda x: x['diff'])

    if matches:
        print(f"\n✨ Found {len(matches)} concept(s) with values near ${gap_value/1e9:.2f}B:\n")

        for i, match in enumerate(matches[:10], 1):
            concept = match['concept']
            value_b = match['value_b']
            diff_b = match['diff_b']

            # Highlight exact matches
            if diff_b < 0.5:
                print(f"  ⭐⭐ #{i}. {concept}")
                print(f"       Value: ${value_b:.2f}B (diff: ${diff_b:.2f}B) - PERFECT MATCH!")
            elif diff_b < 1.0:
                print(f"  ⭐ #{i}. {concept}")
                print(f"       Value: ${value_b:.2f}B (diff: ${diff_b:.2f}B) - VERY CLOSE!")
            else:
                print(f"  💡 #{i}. {concept}")
                print(f"       Value: ${value_b:.2f}B (diff: ${diff_b:.2f}B)")

            print()
    else:
        print(f"\n❌ No concepts found with values near ${gap_value/1e9:.2f}B")

        # Show distribution of values
        print(f"\n📊 Value distribution (top 20 largest):")
        largest = numeric_facts.nlargest(20, 'numeric_value')

        for idx, row in largest.iterrows():
            concept = row['concept']
            value = row['numeric_value'] / 1e9
            print(f"  ${value:>8.2f}B - {concept}")

# Check CommercialPaper specifically
print(f"\n" + "="*80)
print("CHECKING CommercialPaper SPECIFICALLY")
print("="*80)

cp_facts = all_facts_df[all_facts_df['concept'].str.contains('CommercialPaper', case=False, na=False)]

print(f"\nFound {len(cp_facts)} CommercialPaper facts")

if len(cp_facts) > 0:
    print("\nCommercialPaper fact details:")
    for idx, row in cp_facts.iterrows():
        concept = row['concept']
        period = row.get('period_key', 'N/A')
        value = row.get('numeric_value', None)
        dim = row.get('full_dimension_label', None)

        print(f"\n  Concept: {concept}")
        print(f"  Period: {period}")
        print(f"  Value: {value/1e9 if value else 'None':.2f}B" if value else "  Value: None")
        print(f"  Dimension: {dim if dim else 'Total (no dimension)'}")

print("\n" + "="*80)
