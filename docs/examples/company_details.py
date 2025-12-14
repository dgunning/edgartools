from edgar import *

if __name__ == '__main__':
    c:Company = Company("AAPL")
    filings = c.get_filings(form="4")
    ticker = c.tickers
    print(filings)
    print(c.data.mailing_address)
    print(c)
