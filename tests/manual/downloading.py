from edgar.storage import download_filings
from edgar import *
import os

os.environ['EDGAR_LOCAL_DATA_DIR'] = '/Volumes/T9/.edgar'
use_local_storage()


def download_filings():
    filings = get_filings(form=['10-K', '10-Q'], filing_date='2024-04-30')
    filings.download()

if __name__ == '__main__':
    filing = Filing(form='10-K/A', filing_date='2024-04-30', company='KORE Group Holdings, Inc.', cik=1855457, accession_no='0001855457-24-000028')
    sgml = filing.sgml()
    print(sgml)