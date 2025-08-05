from typing import List, Union
from edgar import *
from tqdm.auto import tqdm



def sample_and_test_xbrls(year:Union[int, List[int]]=2024, sample=100):
    filings = get_filings(year=year, form=['10-Q']).sample(sample)
    for filing in tqdm(filings):
        try:
            xbrl = filing.xbrl()
            if not xbrl:
                print(f"No XBRL data for {filing}")
                continue
            income_statement = xbrl.statements.income_statement()
            print(income_statement)
            balance = xbrl.statements.balance_sheet()
            print(balance)
            cashflow = xbrl.statements.cashflow_statement()
            print(cashflow)
            print("*" * 80)
        except Exception as e:
            print(f"Failed to get XBRL for {filing}")
            filing.open()
            print(e)
            raise


if __name__ == '__main__':
    sample_and_test_xbrls(year=2024, sample=100)