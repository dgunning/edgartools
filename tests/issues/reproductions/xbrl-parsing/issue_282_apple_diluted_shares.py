"""
Issue #282 Reproduction: XBRL parsing code that was previously working

User reported that their code for extracting "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
from Apple's 10-K filings starting from 2014-01-01 stopped working.

The user mentions "it looks like the model changed" suggesting there may have been breaking
changes in the XBRL API or data structures.

Original code from the user:
"""

from edgar import *
from edgar.xbrl.xbrl import XBRL

# Set proper identity per SEC requirements
set_identity("edgartools-testing testing@edgartools.com")

key = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
c = Company("AAPL")
tenk = c.filings.filter("10-K", filing_date="2014-01-01:")  # get relevant filings

def shift_number(num, shift):
    return num * (10 ** shift)

print("Starting Apple 10-K analysis for diluted shares outstanding...")
print(f"Looking for concept: {key}")
print(f"Filing count: {len(tenk)}")

values = {}
errors = []

for i, filing in enumerate(tenk[:3]):  # Test with first 3 filings
    print(f"\n=== Processing Filing {i+1}: {filing} ===")
    try:
        xbrl = XBRL.from_filing(filing)  # parse with xbrl
        print(f"XBRL parsed successfully: {xbrl}")

        print("Getting all statements...")
        statements = xbrl.get_all_statements()
        print(f"Found {len(statements)} statements")

        # Print statement info for debugging
        for j, stmt in enumerate(statements[:5]):  # Show first 5 statements
            print(f"  Statement {j+1}: {stmt.get('definition', 'N/A')[:50]}...")

        for stmt in statements:
            definition = stmt['definition']
            print(f"\nProcessing statement: {definition[:50]}...")

            try:
                statement_data = xbrl.get_statement(definition)  # gets the statement data from definition
                print(f"Statement data items: {len(statement_data)}")

                for d in statement_data:
                    d_label = d['label']
                    d_values = d['values']
                    d_decimals = d['decimals']

                    # Check if our target concept is in all_names
                    if key in d['all_names']:
                        print(f"Found target concept in: {d_label}")
                        print(f"Available periods: {list(d_values.keys())}")

                        for duration in d_values:
                            original_value = d_values[duration]
                            decimals_value = d_decimals[duration]
                            adjusted_value = shift_number(original_value, decimals_value)

                            period_key = f"{filing.filing_date}_{duration}"
                            values[period_key] = adjusted_value

                            print(f"  {duration}: {original_value} -> {adjusted_value} (decimals: {decimals_value})")

            except Exception as stmt_error:
                print(f"Error processing statement '{definition}': {stmt_error}")
                errors.append(f"Statement error in {filing}: {stmt_error}")

    except Exception as filing_error:
        print(f"Error processing filing {filing}: {filing_error}")
        errors.append(f"Filing error: {filing_error}")

print(f"\n=== RESULTS ===")
print(f"Found values: {values}")
print(f"Total errors: {len(errors)}")

if errors:
    print("\nErrors encountered:")
    for error in errors:
        print(f"  - {error}")

if not values:
    print("\nNo values found! This indicates the API may have changed.")
    print("Attempting to debug...")

    # Try alternative approaches
    if len(tenk) > 0:
        filing = tenk[0]
        print(f"\nDebugging with filing: {filing}")

        try:
            xbrl = XBRL.from_filing(filing)
            print(f"XBRL object: {xbrl}")
            print(f"Facts count: {len(xbrl._facts)}")
            print(f"Contexts count: {len(xbrl.contexts)}")

            # Try the new facts query interface
            print("\nTrying new facts query interface...")
            facts = xbrl.facts
            diluted_shares_facts = facts.query().by_concept("WeightedAverageNumberOfDilutedSharesOutstanding").to_dataframe()
            print(f"Found {len(diluted_shares_facts)} facts with new query interface")

            if len(diluted_shares_facts) > 0:
                print("Sample fact data:")
                print(diluted_shares_facts.head())

        except Exception as debug_error:
            print(f"Debug error: {debug_error}")