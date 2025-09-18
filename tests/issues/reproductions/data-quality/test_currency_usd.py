"""
Test to verify USD currency still works correctly
"""

from edgar import Company, set_identity
import os

# Use environment identity for tests
if not os.getenv('EDGAR_IDENTITY'):
    set_identity("EdgarTools Test test@edgartools.dev")

def test_usd_currency():
    """Test that Apple shows USD symbols correctly"""
    print("=== Testing USD Currency for Apple ===\n")

    # Get Apple company
    company = Company("AAPL")
    print(f"Company: {company.name}")

    # Get latest 10-K filing
    filing = company.get_filings(form="10-K", amendments=False).latest()
    print(f"Filing: {filing.accession_number}")

    # Get XBRL and cash flow statement
    xbrl = filing.xbrl()
    print(f"XBRL units available: {xbrl.units}")

    # Get cash flow statement
    cashflow = xbrl.statements.cashflow_statement()
    raw_data = cashflow.get_raw_data()

    print(f"\nFirst item with currency info:")
    for i, item in enumerate(raw_data):
        if item.get('has_values') and item.get('values'):
            print(f"  Label: {item['label']}")
            print(f"  Currencies: {item.get('currencies', 'N/A')}")
            break

    # Show a few lines of the rendered statement
    print(f"\nFirst few lines of cash flow statement:")
    statement_lines = str(cashflow).split('\n')
    for line in statement_lines[4:10]:  # Skip header lines
        if line.strip() and '$' in line:
            print(line)
            break

if __name__ == "__main__":
    test_usd_currency()