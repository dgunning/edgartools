from tqdm import tqdm
from edgar import get_filings, Filing


def inspect_filings():
    #for filing in tqdm(get_filings(year=[1996,1997,1998]).sample(200)):
    for filing in tqdm(get_filings(year=2024).sample(200)):
        try:
            filing.attachments
            filing.text()
            filing.view()
            filing.markdown()
            filing.obj()
            print(filing.header)
        except Exception as e:
            print(f"Failed to get text for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    inspect_filings()
