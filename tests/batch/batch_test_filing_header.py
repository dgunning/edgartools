from tqdm import tqdm
from edgar import get_filings, Filing


def inspect_filings():
    for filing in tqdm(get_filings(year=[1996,1997,1998, 1999, 2000, 2024]).sample(200)):
        try:
            print(filing.header)
        except Exception as e:
            print(f"Failed to get text for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    inspect_filings()
