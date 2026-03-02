from tqdm import tqdm
from edgar import get_filings


def get_fund_reports():
    for filing in tqdm(get_filings(form="NPORT-P").sample(100)):
        try:
            fund_report = filing.obj()
        except Exception as e:
            print(f"Failed to get data object for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    get_fund_reports()
