from edgar import *
from tqdm.auto import tqdm



if __name__ == '__main__':
    filings = get_filings(form='N-PX', year=[2024, 2025]).sample(500)
    index = 1
    for filing in tqdm(filings):
        print(index)
        try:
            npx= filing.obj()
        except AttributeError as e:
            print(f"Error processing filing {filing.accession_number}: {e}")
            raise

