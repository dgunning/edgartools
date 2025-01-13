from edgar import *
from edgar.sgml import *
from tqdm.auto import tqdm


if __name__ == '__main__':
    filings = get_filings(filing_date="2025-01-06")
    for filing in filings:
        print(filing)
        if filing.accession_no.startswith("9"):
            continue
            sg = filing.sgml()
            assert sg