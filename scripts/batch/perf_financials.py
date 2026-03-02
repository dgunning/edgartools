from edgar import *
from functools import lru_cache

tickers = ['AAPL', 'NFLX', 'TSLA']

@lru_cache(maxsize=16)
def get_xbrl(ticker):
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    return xbrl


xbrls = {ticker: get_xbrl(ticker) for ticker in tickers}


def show_income_statement():
    for ticker in tickers:
        xbrl = get_xbrl(ticker)
        print(f"{ticker} Consolidated Statement")
        print(IncomeStatement(xbrl.facts))
        print()

def show_balance_sheet():
    for ticker in tickers:
        xbrl = get_xbrl(ticker)
        print(f"{ticker} Balance Sheet")

        balance_sheet = BalanceSheet(xbrl.facts)

        print(balance_sheet.facts)
        print(balance_sheet)
        print()

def show_cashflow_statement():
    for ticker in tickers:
        xbrl = get_xbrl(ticker)
        print(f"{ticker} Cash Flow Statement")
        print(CashFlowStatement(xbrl.facts))
        print()


if __name__ == '__main__':
    #show_balance_sheet()
    #show_income_statement()
    show_cashflow_statement()
