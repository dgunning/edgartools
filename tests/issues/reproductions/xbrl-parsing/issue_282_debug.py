"""
Debug script for issue #282 - investigate the data structure and facts interface
"""

from edgar import *
from edgar.xbrl.xbrl import XBRL

# Set proper identity per SEC requirements
set_identity("edgartools-testing testing@edgartools.com")

c = Company("AAPL")
tenk = c.get_filings(form="10-K", filing_date="2020-01-01:")  # Get recent filings

print(f"Found {len(tenk)} 10-K filings")

# Let's debug with one filing
filing = tenk[0]
print(f"\nDebugging with: {filing}")

xbrl = XBRL.from_filing(filing)
print(f"XBRL parsed successfully")
print(f"Facts count: {len(xbrl._facts)}")

# Debug the facts interface
facts = xbrl.facts
print(f"Facts object type: {type(facts)}")

# Try to get diluted shares facts and see the structure
diluted_shares_query = facts.query().by_concept("WeightedAverageNumberOfDilutedSharesOutstanding")
diluted_shares_df = diluted_shares_query.to_dataframe()

print(f"Found {len(diluted_shares_df)} diluted shares facts")
print(f"DataFrame columns: {list(diluted_shares_df.columns)}")

if len(diluted_shares_df) > 0:
    print("\nFirst few rows:")
    print(diluted_shares_df.head())

    print("\nData types:")
    print(diluted_shares_df.dtypes)

# Also try searching for the exact concept name
print("\n=== Trying exact concept match ===")
exact_query = facts.query().by_concept("us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding", exact=True)
exact_df = exact_query.to_dataframe()
print(f"Exact match found {len(exact_df)} facts")

if len(exact_df) > 0:
    print("Exact match results:")
    print(exact_df.head())

# Let's also see what concepts are available
print("\n=== Available concepts related to shares ===")
all_facts_df = facts.to_dataframe()
share_related = all_facts_df[all_facts_df['concept'].str.contains('Shares|Share', case=False, na=False)]
print(f"Found {len(share_related)} share-related facts")
print("Sample share concepts:")
print(share_related['concept'].unique()[:10])

# Check if the concept exists with a different name
diluted_concepts = all_facts_df[all_facts_df['concept'].str.contains('Diluted', case=False, na=False)]
print(f"\nFound {len(diluted_concepts)} diluted-related facts")
print("Diluted concepts:")
print(diluted_concepts['concept'].unique())

# Let's also check the statement level approach
print("\n=== Statement Level Debug ===")
statements = xbrl.get_all_statements()
print(f"Found {len(statements)} statements")

# Look at income statement specifically
for stmt in statements:
    definition = stmt['definition'].lower()
    if 'income' in definition or 'operation' in definition:
        print(f"\nIncome-related statement: {stmt['definition']}")
        try:
            statement_data = xbrl.get_statement(stmt['definition'])
            print(f"Statement has {len(statement_data)} line items")

            # Check if any line items have diluted shares concept
            for item in statement_data:
                if 'diluted' in item['label'].lower() or 'WeightedAverageNumberOfDilutedSharesOutstanding' in str(item.get('all_names', [])):
                    print(f"Found diluted shares in statement:")
                    print(f"  Label: {item['label']}")
                    print(f"  Concept: {item['concept']}")
                    print(f"  All names: {item.get('all_names', [])}")
                    print(f"  Values: {item.get('values', {})}")
                    break
        except Exception as e:
            print(f"Error processing statement: {e}")
        break  # Just check one income statement