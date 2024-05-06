
from tqdm import tqdm

from edgar import get_filings
import time


def sample_and_test_filings(years, sample_size):
    print(f"Sampling {sample_size} filings from {years}")
    for filing in tqdm(get_filings(year=years, form=['10-K']).sample(sample_size)):
        try:
            obj = filing.obj()
            print(obj.__repr__())
            time.sleep(3)
        except Exception as e:
            print(f"Failed to get text for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    sample_and_test_filings([2020, 2021], 50)