from tqdm import tqdm
from edgar import get_filings
from edgar.ownership import Form4

if __name__ == '__main__':
    for filing in tqdm(get_filings(form=[4], year=2024).sample(100)):
        try:
            form4:Form4 = filing.obj()
            print(form4)
        except Exception as e:
            print(f"Failed to Form 4 {filing}")
            filing.open()
            print(e)
            raise