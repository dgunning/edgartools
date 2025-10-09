"""
Issue #282 Working Solution: Extract diluted shares outstanding from Apple 10-K filings

This script provides updated, working code for extracting
"us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" data from Apple's 10-K filings.

Key API changes and solutions:
1. Company.filings.filter() -> Company.get_filings()
2. XBRL import path: edgar.xbrl.xbrl (not edgar.xbrl2.xbrl)
3. New facts query interface with different column names
4. Data is available via both statement-level and facts-level APIs

Original user code (broken):
    from edgar.xbrl2.xbrl import XBRL
    tenk = c.filings.filter("10-K", filing_date="2014-01-01:")

Updated working code:
    from edgar.xbrl.xbrl import XBRL
    tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")
"""

from edgar import *
from edgar.xbrl.xbrl import XBRL

# Set proper identity per SEC requirements
set_identity("edgartools-testing testing@edgartools.com")

key = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
c = Company("AAPL")

# Updated API: use get_filings() instead of filings.filter()
print("Fetching Apple 10-K filings...")
tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")

print(f"Found {len(tenk)} 10-K filings from 2014 onwards")

def shift_number(num, shift):
    """Apply decimal shift to get actual value"""
    if shift is None or shift == 'INF':
        return num
    return num * (10 ** int(shift))

# Solution 1: Using the new facts query interface (RECOMMENDED)
print("\n=== SOLUTION 1: New Facts Query Interface (Recommended) ===")
values_solution1 = {}

for i in range(min(3, len(tenk))):  # Test with first 3 filings
    filing = tenk[i]
    print(f"\n--- Processing {filing.filing_date}: {filing.form} ---")

    try:
        xbrl = XBRL.from_filing(filing)
        facts = xbrl.facts

        # Query for diluted shares facts - the exact concept name works
        diluted_shares_df = facts.query().by_concept(key, exact=True).to_dataframe()

        print(f"Found {len(diluted_shares_df)} diluted shares facts")

        if len(diluted_shares_df) > 0:
            for _, row in diluted_shares_df.iterrows():
                # Use period_start and period_end to create period identifier
                period_start = row['period_start']
                period_end = row['period_end']
                numeric_value = row['numeric_value']
                decimals = row['decimals']

                # Create period key from start and end dates
                period_key = f"{period_start}_{period_end}"

                # Apply decimal adjustment if needed
                adjusted_value = shift_number(numeric_value, decimals)

                filing_period_key = f"{filing.filing_date}_{period_key}"
                values_solution1[filing_period_key] = adjusted_value

                print(f"  Period: {period_start} to {period_end}")
                print(f"  Value: {numeric_value:,.0f} -> {adjusted_value:,.0f} (decimals: {decimals})")
        else:
            print("  No diluted shares facts found")

    except Exception as e:
        print(f"  Error: {e}")

print(f"\nSolution 1 Results: {len(values_solution1)} values found")
for k, v in sorted(values_solution1.items()):
    print(f"  {k}: {v:,.0f}")

# Solution 2: Using statement-level API (Original approach, corrected)
print("\n=== SOLUTION 2: Statement-Level API (Original Approach) ===")
values_solution2 = {}

for i in range(min(2, len(tenk))):  # Test with first 2 filings
    filing = tenk[i]
    print(f"\n--- Processing {filing.filing_date}: {filing.form} ---")

    try:
        xbrl = XBRL.from_filing(filing)
        statements = xbrl.get_all_statements()

        found_concept = False
        for stmt in statements:
            if 'income' in stmt['definition'].lower() or 'operation' in stmt['definition'].lower():
                print(f"Checking statement: {stmt['definition']}")

                try:
                    statement_data = xbrl.get_statement(stmt['definition'])

                    for d in statement_data:
                        # Check if this line item contains our target concept
                        all_names = d.get('all_names', [])
                        if key in all_names or any(key.replace(':', '_') in name for name in all_names):
                            print(f"Found concept in statement:")
                            print(f"  Label: {d['label']}")
                            print(f"  Concept: {d['concept']}")

                            d_values = d.get('values', {})
                            d_decimals = d.get('decimals', {})

                            for duration, value in d_values.items():
                                decimals_value = d_decimals.get(duration)
                                adjusted_value = shift_number(value, decimals_value)

                                period_key = f"{filing.filing_date}_{duration}"
                                values_solution2[period_key] = adjusted_value

                                print(f"    {duration}: {value:,.0f} -> {adjusted_value:,.0f} (decimals: {decimals_value})")

                            found_concept = True
                            break

                except Exception as stmt_error:
                    print(f"  Error processing statement: {stmt_error}")

                if found_concept:
                    break

        if not found_concept:
            print("  Concept not found in income statements")

    except Exception as e:
        print(f"  Error: {e}")

print(f"\nSolution 2 Results: {len(values_solution2)} values found")
for k, v in sorted(values_solution2.items()):
    print(f"  {k}: {v:,.0f}")

# Solution 3: Direct concept search across all statements (Alternative)
print("\n=== SOLUTION 3: Direct Concept Search (Alternative) ===")
values_solution3 = {}

filing = tenk[0]  # Just test with most recent filing
print(f"\n--- Processing {filing.filing_date}: {filing.form} ---")

try:
    xbrl = XBRL.from_filing(filing)

    # Search all facts directly for our concept
    all_facts_df = xbrl.facts.to_dataframe()

    # Filter for our specific concept
    diluted_facts = all_facts_df[all_facts_df['concept'] == key]

    if len(diluted_facts) > 0:
        print(f"Found {len(diluted_facts)} facts for {key}")
        print("\nAll matching facts:")
        print(diluted_facts[['period_start', 'period_end', 'numeric_value', 'decimals', 'statement_type']].to_string())

        for _, row in diluted_facts.iterrows():
            period_key = f"{row['period_start']}_{row['period_end']}"
            value = row['numeric_value']
            decimals = row['decimals']
            adjusted_value = shift_number(value, decimals)

            filing_period_key = f"{filing.filing_date}_{period_key}"
            values_solution3[filing_period_key] = adjusted_value
    else:
        print("No facts found for this concept")

except Exception as e:
    print(f"Error: {e}")

print(f"\nSolution 3 Results: {len(values_solution3)} values found")
for k, v in sorted(values_solution3.items()):
    print(f"  {k}: {v:,.0f}")

# Summary and recommendations
print("\n" + "="*60)
print("SUMMARY AND RECOMMENDATIONS")
print("="*60)

total_values = len(values_solution1) + len(values_solution2) + len(values_solution3)

if total_values > 0:
    print("✅ SUCCESS: Found diluted shares outstanding data!")

    print(f"\nResults summary:")
    print(f"  Solution 1 (Facts Query): {len(values_solution1)} values")
    print(f"  Solution 2 (Statement API): {len(values_solution2)} values")
    print(f"  Solution 3 (Direct Search): {len(values_solution3)} values")

    print(f"\n📝 KEY API CHANGES IDENTIFIED:")
    print(f"  1. Import: 'from edgar.xbrl.xbrl import XBRL' (not edgar.xbrl2)")
    print(f"  2. Filings: 'Company.get_filings()' (not Company.filings.filter())")
    print(f"  3. Facts API: DataFrame columns are 'period_start', 'period_end', 'numeric_value'")
    print(f"  4. Concept names: Use exact string 'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding'")

    print(f"\n🚀 RECOMMENDED APPROACH:")
    print(f"  Use Solution 1 (Facts Query Interface) - it's the most robust and future-proof")

    # Show the recommended code pattern
    print(f"\n💻 RECOMMENDED CODE PATTERN:")
    print("""
from edgar import Company
from edgar.xbrl.xbrl import XBRL

company = Company("AAPL")
filings = company.get_filings(form="10-K", filing_date="2014-01-01:")

for filing in filings:
    xbrl = XBRL.from_filing(filing)
    facts = xbrl.facts

    diluted_shares = facts.query().by_concept(
        "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
        exact=True
    ).to_dataframe()

    for _, row in diluted_shares.iterrows():
        period = f"{row['period_start']} to {row['period_end']}"
        value = row['numeric_value']
        print(f"{period}: {value:,.0f} shares")
""")

else:
    print("❌ No values found - this may indicate a deeper issue")
    print("   Please check the filing dates and ensure XBRL data is available")

print("\n" + "="*60)