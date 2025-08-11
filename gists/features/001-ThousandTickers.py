from edgar import *
from edgar.reference.tickers import get_company_tickers

tickers = get_company_tickers().head(5000).ticker.tolist()
forms = ['10-K', '10-Q', '8-K']
filings = (get_filings(year=2024, quarter=1,
                      form=forms,
                       amendments=True)
           .filter(ticker=tickers))
use_local_storage('/Volumes/T9/.edgar')
filings.download()
