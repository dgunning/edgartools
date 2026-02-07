from edgar import *
from tqdm.auto import tqdm
from rich import print


if __name__ == '__main__':
    filings = get_filings(form='NPORT-P', year=[2025]).sample(500)
    index = 1
    for filing in tqdm(filings):
        print(index)
        try:
            fund_report:FundReport = filing.obj()
            print(fund_report)
        except AttributeError as e:
            print(f"Error processing filing {filing.accession_number}: {e}")
            raise

