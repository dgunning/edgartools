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
            #print(company)
            tenk_filing = company.get_filings(form="10-K").latest(1)
            print(str(tenk_filing))
            if tenk_filing:
                get_financials_for_filing(tenk_filing)
        if sleep_time:
            time.sleep(sleep_time)


def get_financials_for_recent_filings(num_filings: int = 100, sleep_time: int = None):
    filings = get_filings(form="10-K").head(num_filings)
    for filing in tqdm(filings):
        print()
        print(str(filing))
        get_financials_for_filing(filing)
        if sleep_time:
            time.sleep(sleep_time)


def get_financials_for_filing(filing):
    xbrl_data = filing.xbrl()
    if not xbrl_data:
        print("No XBRL data found for filing")
        return
    financials = Financials(xbrl_data)
    balance_sheet = financials.get_balance_sheet()
    financials.get_income_statement()
    financials.get_cash_flow_statement()
    repr(financials.get_cover_page())
    if balance_sheet:
        print(balance_sheet)
        print(balance_sheet.get_dataframe(include_concept=True, include_format=True))
        assert not '_' in balance_sheet.labels[0]
    else:
        print(xbrl_data.list_statement_definitions())
    print("*" * 80)


if __name__ == '__main__':
    get_financials_for_popular_stocks(sleep_time=1)
    #get_financials_for_recent_filings(sleep_time=1)
