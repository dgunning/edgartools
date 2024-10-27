from edgar.xbrl import XBRLData
from edgar.financials import Financials
from edgar import *
from pyinstrument import Profiler

if __name__ == '__main__':
    filing = Filing(company='Tesla, Inc.', cik=1318605,
                    form='10-K', filing_date='2024-01-29',
                    accession_no='0001628280-24-002390')
    Financials.extract(filing)
    with Profiler(async_mode=True) as p:
        financials = Financials.extract(filing)
        balance_sheet = financials.get_balance_sheet()
        income_statement = financials.get_income_statement()
        cash_flow = financials.get_cash_flow_statement()
        financials.get_statement_of_changes_in_equity()
        financials.get_statement_of_comprehensive_income()

    p.print()

