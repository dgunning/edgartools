import argparse

from tqdm import tqdm

from edgar import get_filings, use_local_storage



def main():
    # '2015-02-13', '2025-02-13' These dates are downloaded locally
    filings = get_filings(filing_date='2015-02-13')
    for filing in tqdm(filings):
        try:
            #attachments = filing.attachments
            filing.sgml()
        except Exception as e:
            print(f"Failed to get SGML for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    use_local_storage(True)
    main()
