"""Debug dimensional filtering in XBRL value extraction."""

from edgar import Company, set_identity, use_local_storage

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

print(f"Total facts for {concept_name}: {len(df)}")
print(f"\nColumns: {list(df.columns)}")

# Check dimension column
if 'full_dimension_label' in df.columns:
    print(f"\nDimension analysis:")
    print(f"  Total rows: {len(df)}")
    print(f"  Rows with no dimension (isna): {len(df[df['full_dimension_label'].isna()])}")
    print(f"  Rows with dimension: {len(df[df['full_dimension_label'].notna()])}")

    # Show sample dimensional values
    dimensioned = df[df['full_dimension_label'].notna()]
    if len(dimensioned) > 0:
        print(f"\nSample dimensioned values:")
        for idx, row in dimensioned.head(5).iterrows():
            val = row['numeric_value'] / 1e9 if row['numeric_value'] else 0
            print(f"  Dimension: {row['full_dimension_label']}")
            print(f"    Value: ${val:.2f}B")
            print(f"    Period: {row.get('period_key', 'N/A')}")

    # Show non-dimensioned values
    non_dimensioned = df[df['full_dimension_label'].isna()]
    if len(non_dimensioned) > 0:
        print(f"\nNon-dimensioned (consolidated) values:")
        numeric = non_dimensioned[non_dimensioned['numeric_value'].notna()]
        if len(numeric) > 0:
            for idx, row in numeric.head(5).iterrows():
                val = row['numeric_value'] / 1e9 if row['numeric_value'] else 0
                print(f"  Value: ${val:.2f}B")
                print(f"  Period: {row.get('period_key', 'N/A')}")
        else:
            print("  No numeric values in non-dimensioned rows!")
else:
    print("\nNo 'full_dimension_label' column found!")

# Check for other dimension-related columns
dimension_cols = [col for col in df.columns if 'dimension' in col.lower() or 'segment' in col.lower() or 'axis' in col.lower()]
if dimension_cols:
    print(f"\nOther dimension-related columns: {dimension_cols}")

# Show all unique values for numeric_value column to see what we have
numeric_df = df[df['numeric_value'].notna()].copy()
if len(numeric_df) > 0:
    numeric_df = numeric_df.sort_values('numeric_value', ascending=False)
    print(f"\nTop 10 numeric values (all dimensions):")
    for idx, row in numeric_df.head(10).iterrows():
        val = row['numeric_value'] / 1e9
        dim = row.get('full_dimension_label', 'NO DIMENSION')
        period = row.get('period_key', 'N/A')
        print(f"  ${val:.2f}B - Dim: {dim} - Period: {period}")
