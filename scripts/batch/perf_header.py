from edgar import *
from tqdm import tqdm
import pandas as pd


def check_filing_headers():
    filings = get_filings(form=4).head(100)
    data = []
    for filing in tqdm(filings):
        record = {'accession_no': filing.accession_no, 'form': filing.form, 'company': filing.company}
        header = filing.header
        record['filers'] = len(header.filers)
        record['owners'] = len(header.reporting_owners)
        record['filenumbers'] = len(set([o.filing_information.file_number for o in header.reporting_owners]))
        data.append(record)
    df = pd.DataFrame(data)
    print(df.query("owners > 1"))
    print(df.describe())


def check_file_numbers():
    filings = get_filings().sample(500)
    for filing in tqdm(filings):
        if not filing.header.file_number:
            print(filing.accession_no, filing.form, filing.company, filing.homepage_url)
            raise ValueError(f"No file number for {filing.form} {filing.accession_no}")


if __name__ == '__main__':
    check_filing_headers()
