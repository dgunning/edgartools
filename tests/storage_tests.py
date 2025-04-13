from edgar.storage import download_filings
from edgar import *

def download_n_filings(n=10):
    # Fetch the latest Form 4 filings
    filings = get_filings(filing_date='2025-01-16').sample(10)
    print(filings)

    # Download the filings
    download_filings(filings=filings, overwrite_existing=True)

def filings_downloads_itself():
    # Fetch the latest Form 4 filings
    filings = get_filings(filing_date='2025-01-16').sample(10)

    filings.download()


if __name__ == "__main__":
    #download_n_filings(10)
    filings_downloads_itself()