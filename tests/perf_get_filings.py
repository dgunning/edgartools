from edgar import *
import os


def get_filing_for_year_and_quarter():
    filings = get_filings(year=2022, quarter=1)
    print(filings)


if __name__ == '__main__':
    # print(os.environ.get('EDGAR_IDENTITY'))
    get_filing_for_year_and_quarter()
