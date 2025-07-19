from edgar.storage import download_filings
from edgar import *
import os

os.environ['EDGAR_LOCAL_DATA_DIR'] = '/Volumes/T9/.edgar'
use_local_storage()


def download_filings():
    filings = get_filings(form=['10-K', '10-Q'], filing_date='2024-07-08')
    filings.download()

if __name__ == '__main__':
    download_filings()