"""Debug why we get multiple Assets values for same period."""

from edgar import Company, set_identity, use_local_storage
import pandas as pd

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

# Test with AAPL TotalAssets
company = Company('AAPL')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()

# Get Assets facts
concept_name = 'Assets'
facts = xbrl.facts
df = facts.get_facts_by_concept(concept_name)

# Filter for non-dimensioned values with the latest period
non_dimensioned = df[df['full_dimension_label'].isna()].copy()
numeric = non_dimensioned[non_dimensioned['numeric_value'].notna()].copy()
latest_period = numeric.sort_values('period_key', ascending=False).iloc[0]['period_key']

print(f"Latest period: {latest_period}")
print(f"\nAll non-dimensioned Assets values for {latest_period}:")
print("="*80)

same_period = numeric[numeric['period_key'] == latest_period].copy()
same_period = same_period.sort_values('numeric_value', ascending=False)

# Show all columns for these rows to understand the difference
for idx, row in same_period.iterrows():
    val = row['numeric_value'] / 1e9
    print(f"\nValue: ${val:.2f}B")
    print(f"  Concept: {row['concept']}")
    print(f"  Label: {row.get('label', 'N/A')}")
    print(f"  Statement Type: {row.get('statement_type', 'N/A')}")
    print(f"  Statement Name: {row.get('statement_name', 'N/A')}")
    print(f"  Context: {row.get('context_ref', 'N/A')}")
    print(f"  Balance: {row.get('balance', 'N/A')}")
    print(f"  Period: {row.get('period_key', 'N/A')}")

print(f"\n{'='*80}")
print("ANALYSIS:")
print("All these rows have the SAME concept ('us-gaap:Assets') but different values.")
print("This means they come from different contexts/statements in the XBRL.")
print("\nWe want the LARGEST value (consolidated total) = $359.24B")
print("Currently getting the first after sorting by period = $14.59B")
