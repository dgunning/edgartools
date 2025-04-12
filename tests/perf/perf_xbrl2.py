from edgar import *
from edgar.xbrl import *
from pyinstrument import Profiler

def main(filing):
    xbrl = XBRL.from_filing(filing)
    income_statement = xbrl.statements['IncomeStatement']
    income_statement.to_dataframe()
    balance_sheet = xbrl.statements["BalanceSheet"]
    balance_sheet.to_dataframe()
    cash_flow = xbrl.statements["CashFlow"]
    cash_flow.to_dataframe()


if __name__ == "__main__":
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    with Profiler() as p:
        main(filing)
    p.print()