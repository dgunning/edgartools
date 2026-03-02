from edgar.reference.tickers import popular_us_stocks
from edgar import *
from tqdm.auto import tqdm

def load_management_discussions():
    for cik in tqdm(popular_us_stocks().index):
        company = Company(cik)
        tenk = company.latest_tenk
        if tenk:
            mda = tenk['Item 7']
            if not mda:
                print(f"No MDA found for {company.tickers}")
                print(tenk.items)

if __name__ == '__main__':
    load_management_discussions()


