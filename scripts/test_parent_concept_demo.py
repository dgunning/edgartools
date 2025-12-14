"""
Demo script for Issue #514: parent_concept column in XBRL statement DataFrames

This script demonstrates the new parent_concept column that exposes XBRL
hierarchy relationships for programmatic analysis.
"""
from edgar import Company

# Use the example from the GitHub issue
company = Company("NFLX")
filing = company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()
xbrl = filing.xbrl()

# Get income statement
statement = xbrl.statements.income_statement()
df = statement.to_dataframe()

print("=" * 80)
print("Parent Concept Column Demo (Issue #514)")
print("=" * 80)
print("\nFiling: Netflix 10-Q (Accession: 0001065280-25-000406)")
print("Statement: Income Statement")
print(f"\nTotal rows in DataFrame: {len(df)}")
print(f"\nDataFrame columns: {list(df.columns)}")

# Show key columns including parent_concept
key_cols = ['concept', 'parent_concept', 'label', 'weight']
available_cols = [col for col in key_cols if col in df.columns]

print(f"\n\nHierarchy Information (showing: {', '.join(available_cols)}):")
print("-" * 80)

# Filter to non-abstract items with values
items_with_values = df[~df.get('abstract', False) & df[available_cols].notna().any(axis=1)]

# Show first 20 items
display_df = items_with_values[available_cols].head(20)
print(display_df.to_string(index=False))

# Show parent-child relationships
print("\n\nExample Parent-Child Relationships:")
print("-" * 80)

# Find items that have parents
items_with_parents = df[df['parent_concept'].notna()][['concept', 'parent_concept', 'label', 'weight']]
print(f"\nTotal items with parents: {len(items_with_parents)}")

# Show a few examples
if len(items_with_parents) > 0:
    print("\nFirst 10 parent-child relationships:")
    for idx, row in items_with_parents.head(10).iterrows():
        child_concept = row['concept'].split(':')[-1] if ':' in row['concept'] else row['concept']
        parent_concept = row['parent_concept'].split(':')[-1] if ':' in str(row['parent_concept']) else row['parent_concept']
        print(f"  {child_concept:40s} → parent: {parent_concept:40s} (weight: {row['weight']})")

# Show root items (no parent)
root_items = df[df['parent_concept'].isna()][['concept', 'label']]
print(f"\n\nRoot items (no parent): {len(root_items)}")
if len(root_items) > 0:
    for idx, row in root_items.head(5).iterrows():
        concept_name = row['concept'].split(':')[-1] if ':' in row['concept'] else row['concept']
        print(f"  {concept_name:40s} - {row['label']}")

print("\n" + "=" * 80)
print("✓ parent_concept column successfully added!")
print("=" * 80)
