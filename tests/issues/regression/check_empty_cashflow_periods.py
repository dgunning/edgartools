from edgar import *

filings = ["0000320193-17-000009",
"0001628280-17-004790",
"0001628280-16-017809"]


def show_cashflow(accession_number):
    """Display the cash flow statement for a given filing accession number."""
    filing = find(accession_number)
    cashflow_stmt = filing.xbrl().statements.cashflow_statement()
    print(cashflow_stmt)


if __name__ == '__main__':
    for acc_no in filings:
        print(f"=== Cash Flow Statement for Filing {acc_no} ===")
        show_cashflow(acc_no)
        print("\n")