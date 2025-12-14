"""
Debug script to understand why parent_concept isn't showing up
"""
from edgar import Company

company = Company("NFLX")
filing = company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()
xbrl = filing.xbrl()

# Get income statement
statement = xbrl.statements.income_statement()

# Check raw data
raw_data = statement.get_raw_data()

print("Raw data structure (first 5 items):")
print("=" * 80)
for i, item in enumerate(raw_data[:5]):
    print(f"\nItem {i}:")
    print(f"  concept: {item.get('concept')}")
    print(f"  label: {item.get('label')}")
    print(f"  parent: {item.get('parent')}")
    print(f"  children: {item.get('children')[:2] if item.get('children') else None}...")
    print(f"  level: {item.get('level')}")
    print(f"  keys: {list(item.keys())}")

# Now get the DataFrame
df = statement.to_dataframe()

print("\n" + "=" * 80)
print(f"DataFrame columns: {list(df.columns)}")
print(f"DataFrame has parent_concept: {'parent_concept' in df.columns}")
