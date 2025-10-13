"""
Issue #282 Fix: Updated XBRL parsing code for extracting diluted shares outstanding

This script demonstrates the corrected API usage for extracting
"us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" data from Apple's 10-K filings.

Key API changes identified:
1. Company.filings.filter() -> Company.get_filings()
2. XBRL.from_filing() import path has changed
3. New facts query interface available as alternative approach

Original code (broken):
    from edgar.xbrl2.xbrl import XBRL  # Wrong import
    tenk = c.filings.filter("10-K", filing_date="2014-01-01:")  # Wrong API

Updated code (working):
    from edgar.xbrl.xbrl import XBRL  # Correct import
    tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")  # Correct API
"""

from edgar import *
from edgar.xbrl.xbrl import XBRL  # Correct import path


key = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
c = Company("AAPL")

# Updated API: use get_filings() instead of filings.filter()
tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")  # Correct API

def shift_number(num, shift):
    """Apply decimal shift to get actual value"""
    return num * (10 ** shift)

print("Starting Apple 10-K analysis for diluted shares outstanding...")
print(f"Looking for concept: {key}")
print(f"Filing count: {len(tenk)}")

# Method 1: Original approach with API corrections
print("\n=== METHOD 1: Original Approach (Corrected) ===")
values_method1 = {}
errors = []

for i in range(min(2, len(tenk))):  # Test with first 2 filings
    filing = tenk[i]
    print(f"\n--- Processing Filing {i+1}: {filing} ---")
    try:
        xbrl = XBRL.from_filing(filing)  # This method exists and works
        print(f"XBRL parsed successfully")

        statements = xbrl.get_all_statements()
        print(f"Found {len(statements)} statements")

        found_concept = False
        for stmt in statements:
            definition = stmt['definition']

            try:
                statement_data = xbrl.get_statement(definition)

                for d in statement_data:
                    if key in d['all_names']:
                        print(f"Found concept in statement: {definition}")
                        found_concept = True

                        d_label = d['label']
                        d_values = d['values']
                        d_decimals = d['decimals']

                        print(f"Label: {d_label}")
                        print(f"Available periods: {list(d_values.keys())}")

                        for duration in d_values:
                            original_value = d_values[duration]
                            decimals_value = d_decimals[duration]
                            adjusted_value = shift_number(original_value, decimals_value)

                            period_key = f"{filing.filing_date}_{duration}"
                            values_method1[period_key] = adjusted_value

                            print(f"  {duration}: {original_value} -> {adjusted_value} (decimals: {decimals_value})")
                        break

            except Exception as stmt_error:
                print(f"Error processing statement '{definition}': {stmt_error}")

        if not found_concept:
            print(f"Concept {key} not found in any statement for {filing}")

    except Exception as filing_error:
        print(f"Error processing filing {filing}: {filing_error}")
        errors.append(f"Filing error: {filing_error}")

print(f"\nMethod 1 Results: {len(values_method1)} values found")
for k, v in values_method1.items():
    print(f"  {k}: {v:,.0f}")

# Method 2: New facts query interface (recommended)
print("\n=== METHOD 2: New Facts Query Interface (Recommended) ===")
values_method2 = {}

for i in range(min(2, len(tenk))):
    filing = tenk[i]
    print(f"\n--- Processing Filing {i+1}: {filing} ---")
    try:
        xbrl = XBRL.from_filing(filing)

        # Use the new facts query interface
        facts = xbrl.facts
        print(f"Total facts available: {len(facts.to_dataframe()) if hasattr(facts, 'to_dataframe') else 'N/A'}")

        # Search for diluted shares facts
        diluted_shares_query = facts.query().by_concept("WeightedAverageNumberOfDilutedSharesOutstanding")
        diluted_shares_df = diluted_shares_query.to_dataframe()

        print(f"Found {len(diluted_shares_df)} diluted shares facts")

        if len(diluted_shares_df) > 0:
            print("Sample facts:")
            print(diluted_shares_df[['period_key', 'value', 'label']].head())

            # Extract values by period
            for _, row in diluted_shares_df.iterrows():
                period_key = f"{filing.filing_date}_{row['period_key']}"
                value = row['value']
                values_method2[period_key] = value
                print(f"  {row['period_key']}: {value:,.0f}")
        else:
            print("No diluted shares facts found with new query interface")

    except Exception as e:
        print(f"Error with new facts interface: {e}")

print(f"\nMethod 2 Results: {len(values_method2)} values found")
for k, v in values_method2.items():
    print(f"  {k}: {v:,.0f}")

# Summary and recommendations
print("\n=== SUMMARY ===")
print(f"Method 1 (Original corrected): {len(values_method1)} values")
print(f"Method 2 (New facts query): {len(values_method2)} values")

if values_method1 or values_method2:
    print("\n✅ SUCCESS: Found diluted shares data!")
    print("\nRecommendations:")
    print("1. Use Method 2 (facts query interface) for new code - it's more robust")
    print("2. The key API changes are:")
    print("   - Company.filings.filter() -> Company.get_filings()")
    print("   - Use edgar.xbrl.xbrl import (not edgar.xbrl2.xbrl)")
    print("   - Consider using the new facts.query() interface")
else:
    print("\n❌ No values found - need further investigation")

if errors:
    print(f"\nErrors encountered: {len(errors)}")
    for error in errors:
        print(f"  - {error}")