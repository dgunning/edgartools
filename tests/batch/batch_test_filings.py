from tqdm import tqdm
from edgar import get_filings


def view_filing_text():
    for filing in tqdm(get_filings(year=2024).sample(200)):
        try:
            filing.text()
            filing.view()
            filing.markdown()
            filing.obj()
        except Exception as e:
            print(f"Failed to get text for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    view_filing_text()
