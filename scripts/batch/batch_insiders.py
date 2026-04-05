from tqdm import tqdm
from edgar import get_filings
from edgar.ownership import Ownership

if __name__ == '__main__':
    for filing in tqdm(get_filings(form=[3,4,5], year=2024).sample(200)):
        try:
            ownership:Ownership = filing.obj()
            df = ownership.to_dataframe()
            df2 = ownership.to_dataframe(detailed=False)
            print()
            print(ownership)
            ownership.to_html()
        except Exception as e:
            print(f"Failed to create Ownership {filing}")
            filing.open()
            print(e)
            raise