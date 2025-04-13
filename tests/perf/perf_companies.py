from edgar import *
from pyinstrument import Profiler
from edgar.entity import public_companies
from edgar.reference.tickers import popular_us_stocks
from tqdm.auto import tqdm

def get_public_companies():
    for ticker in tqdm(['TSLA', 'AAPL', 'MSFT', "JPM"]):
        company = Company(ticker)
        filings = company.get_filings()


if __name__ == '__main__':
    with Profiler() as p:
        get_public_companies()
    p.print(timeline=True)