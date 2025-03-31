from edgar import *
from pyinstrument import Profiler

def main(filing):
    financials = Financials.extract(filing)
    balance_sheet = financials.get_balance_sheet()
    balance_sheet.to_dataframe()
    income_statement = financials.get_income_statement()
    income_statement.to_dataframe()
    cash_flow = financials.get_cash_flow_statement()
    cash_flow.to_dataframe()


if __name__ == '__main__':
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    Financials.extract(filing)
    with Profiler(async_mode=True) as p:
        main(filing)
    p.print()

