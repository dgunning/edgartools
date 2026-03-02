from tqdm import tqdm
from edgar import get_filings


def get_form_d():
    for filing in tqdm(get_filings(form=["D"], year=2024).sample(500)):
        try:
            filing.obj()
        except Exception as e:
            print(f"Failed to Form D {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    get_form_d()