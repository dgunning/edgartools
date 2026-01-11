from edgar import *
from edgar.xbrl import XBRL

def run_tenq_financials(num):
    filings = get_filings(form='10-Q', year=2025)
    for filing in filings.sample(min(num, len(filings))):
        xbrl = XBRL.from_filing(filing)
        if xbrl:
            income_statement = xbrl.statements.income_statement()
            balance_sheet = xbrl.statements.balance_sheet()
            cashflow_statement = xbrl.statements.cashflow_statement()
            print(income_statement)
            print(balance_sheet)
            print(cashflow_statement)


if __name__ == '__main__':
    run_tenq_financials(100)