from edgar import *
from edgar.xbrl import XBRLData, XBRLInstance, Statement, Statements, Financials
import time
from rich import print as rprint

def run_tenq_financials(num):
    filings = get_filings(form='10-Q').sample(num)
    for filing in filings:
        print(str(filing))
        xbrl_data = XBRLData.extract(filing)
        financials = Financials(xbrl_data)
        income_statement = financials.get_income_statement()
        rprint(income_statement)
        time.sleep(13)


if __name__ == '__main__':
    run_tenq_financials(100)