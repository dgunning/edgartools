from edgar import *
from edgar.company_reports import EightK
from tqdm.auto import tqdm

def verify_eightk_across_time():
    filings = get_filings(year=[1995, 2003, 2008, 2013, 2023],  quarter=1, form="8-K").sample(100)
    for filing in tqdm(filings):
        try:
            eightk: EightK = filing.obj()
            repr(eightk)
        except:
            print(f"Failed to get text for {filing}")
            raise




if __name__ == '__main__':
    verify_eightk_across_time()