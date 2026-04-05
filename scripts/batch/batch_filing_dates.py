from edgar import *
from tqdm.auto import tqdm
import re


def check_filing_dates():
    filings = get_filings(year=[2012,2020,2024]).sample(40)
    for filing in tqdm(filings):
        homepage = filing.homepage
        filing_date, acceptance_datetime, period_of_report = homepage.get_filing_dates()
        print(period_of_report)
        assert period_of_report is None or re.match('\d{4}-\d{2}-\d{2}', filing_date),\
            f"Invalid period of report {period_of_report} for {filing}"



if __name__ == '__main__':
    check_filing_dates()



