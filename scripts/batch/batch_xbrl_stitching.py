import time
from tqdm import tqdm
from rich import print
from edgar import *
from financials import *
import pandas as pd
use_local_storage(True)
popular_tickers = pd.read_csv('data/popular_us_stocks.csv')


def get_financials_for_popular_stocks(num_stocks: int = 100, sleep_time: int = None):
    for ticker in tqdm(popular_tickers.tail(num_stocks).Ticker.tolist()):

        print()
        company: Company = Company(ticker)
        if company:
            filings = company.get_filings(form="10-K", amendments=False).head(5)
            print(ticker, company.name)
            if len(filings) > 0:
                get_financials_for_filing(filings)
        if sleep_time:
            time.sleep(sleep_time)


def get_financials_for_recent_filings(num_filings: int = 100, sleep_time: int = None):
    filings = get_filings(form="10-K").head(num_filings)
    for filing in tqdm(filings):
        print()
        #print(str(filing))
        get_financials_for_filing(filing)
        if sleep_time:
            time.sleep(sleep_time)


def get_financials_for_filing(filings):
    xbs = XBRLS.from_filings(filings)
    income_statement = xbs.statements.income_statement()

    if income_statement:
        print(income_statement)
    balance_sheet  = xbs.statements.balance_sheet()
    if balance_sheet:
        print(balance_sheet)
    assert len(balance_sheet.periods) == len(xbs.xbrl_list)

    cashflow_statement = xbs.statements.cashflow_statement()
    if cashflow_statement:
        print(cashflow_statement)
    assert len(cashflow_statement.periods) == len(xbs.xbrl_list)

    print("*" * 80)


if __name__ == '__main__':
    get_financials_for_popular_stocks(sleep_time=1)
    #get_financials_for_recent_filings(sleep_time=1)
