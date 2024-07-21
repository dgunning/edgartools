from pathlib import Path
from tqdm import tqdm
import pandas as pd
import asyncio
from edgar import *
from edgar.xbrl.parser import *
from edgar.xbrl.financials import *
use_local_storage(True)
popular_tickers = pd.read_csv('data/popular_us_stocks.csv')


async def run_xbrl_tests(num_stocks:int=100):
    for ticker in tqdm(popular_tickers.tail(num_stocks).Ticker.tolist()):
        company:Company = Company(ticker)
        if company:
            print(company)
            tenk_filing = company.get_filings(form="10-K").latest(1)
            print(tenk_filing)
            if tenk_filing:
                xbrl_data:XBRLData = await XBRLData.from_filing(tenk_filing)
                financials = Financials(xbrl_data)
                balance_sheet = financials.get_balance_sheet()
                assert financials.get_income_statement()
                assert financials.get_cash_flow_statement()
                assert financials.get_balance_sheet()
                print(balance_sheet)

        print("*"*80)

if __name__ == '__main__':
    asyncio.run(run_xbrl_tests())


