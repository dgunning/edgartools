"""
Simple test to verify currency fix for Deutsche Bank
"""
import pytest

from edgar import Company
import os


@pytest.mark.regression
def test_currency_fix():
    """Test that Deutsche Bank shows EUR symbols instead of USD"""
    print("=== Testing Currency Fix for Deutsche Bank ===\n")

    # Get Deutsche Bank company
    company = Company("DB")
    print(f"Company: {company.name}")

    # Get latest 20-F filing
    filing = company.get_filings(form="20-F", amendments=False).latest()
    print(f"Filing: {filing.accession_number}")

    # Get XBRL and cash flow statement
    xbrl = filing.xbrl()
    print(f"XBRL units available: {xbrl.units}")

    # Get raw statement data to check if currencies are captured
    cashflow = xbrl.statements.cashflow_statement()
    raw_data = cashflow.get_raw_data()

    print(f"\nFirst few raw data items with currency info:")
    for i, item in enumerate(raw_data[:3]):
        print(f"Item {i}:")
        print(f"  Label: {item['label']}")
        print(f"  Has values: {item.get('has_values', False)}")
        print(f"  Currencies: {item.get('currencies', 'N/A')}")
        print(f"  Values: {item.get('values', {})}")
        print()

    # Check if currencies field exists in items that have values
    print(f"\nAnalyzing currency data structure:")
    for i, item in enumerate(raw_data):
        if item.get('has_values') and item.get('values'):
            print(f"Item {i} with values:")
            print(f"  Label: {item['label']}")
            print(f"  Keys: {item.keys()}")
            if 'currencies' in item:
                print(f"  Currencies: {item['currencies']}")
            else:
                print(f"  No currencies field found")
            break

    # Let's check what facts look like in detail
    print(f"\nLet's examine facts directly to understand the structure...")

    # Try to access a fact to see its attributes
    try:
        facts_df = xbrl.facts.to_dataframe()
        print(f"Facts dataframe columns: {facts_df.columns.tolist()}")

        # Filter for financial facts that have unit_ref
        monetary_facts = facts_df[facts_df['unit_ref'].notna()]
        print(f"Facts with unit_ref: {len(monetary_facts)}")

        if len(monetary_facts) > 0:
            sample_fact = monetary_facts.iloc[0]
            print(f"Sample fact attributes:")
            for col in ['concept', 'unit_ref', 'value', 'numeric_value']:
                if col in sample_fact:
                    print(f"  {col}: {sample_fact[col]}")

            # Check what unit this maps to
            unit_ref = sample_fact['unit_ref']
            if unit_ref in xbrl.units:
                print(f"  Unit info: {xbrl.units[unit_ref]}")

    except Exception as e:
        print(f"Error examining facts: {e}")

    # Show the current rendered statement
    print(f"\nCurrent cash flow statement:")
    print(cashflow)

if __name__ == "__main__":
    test_currency_fix()