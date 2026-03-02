from tqdm import tqdm
from edgar import get_filings


def get_form_c():
    for filing in tqdm(get_filings(form=["C", "C-U", "C-AR", "C-TR"], year=2023).sample(500)):
        try:
            filing.obj()
        except Exception as e:
            print(f"Failed to Form C {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    get_form_c()