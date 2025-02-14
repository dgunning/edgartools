import argparse

from tqdm import tqdm

from edgar import get_filings



def main():
    filings = get_filings(year=[2000, 2005, 2010, 2014, 2018, 2022, 2025]).sample(1000)
    for filing in tqdm(filings):
        try:
            #attachments = filing.attachments
            filing.sgml()
        except Exception as e:
            print(f"Failed to get SGML attachments for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    main()
