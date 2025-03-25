from edgar import *
from edgar.xbrl2 import *
from pyinstrument import Profiler

def main():
    filing = c.latest("10-K")
    xbrl = XBRL.from_filing(filing)
    income_statement = xbrl.statements['IncomeStatement']
    income_statement.to_dataframe()
    balance_sheet = xbrl.statements["BalanceSheet"]
    balance_sheet.to_dataframe()
    cash_flow = xbrl.statements["CashFlow"]
    cash_flow.to_dataframe()


if __name__ == "__main__":
    c = Company("AAPL")
    with Profiler() as p:
        main()
    p.print()