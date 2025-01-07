from edgar import *
from edgar.reference.tickers import popular_us_stocks
from tqdm.auto import tqdm
import re


def check_company_filings():
    tickers = popular_us_stocks().sample(20).Ticker.tolist()
    for ticker in tqdm(tickers):
        company = Company(ticker)
        for filing in tqdm(company.filings):
            print(filing.acceptance_datetime)



if __name__ == '__main__':
    check_company_filings()
