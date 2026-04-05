from edgar import *
from tqdm.auto import tqdm



if __name__ == '__main__':
    filings = get_filings(form='13F-HR', year=[2025]).sample(500)
    #thirteenf = filing.obj()
    #Error processing filing 0000902664-12-001664: 'NoneType' object has no attribute 'filter'

    index = 1
    for filing in tqdm(filings):
        print(index)
        try:
            thirteenf:ThirteenF = filing.obj()
            print(thirteenf)
            print(thirteenf.compare_holdings())
            print(thirteenf.holding_history())
        except AttributeError as e:
            print(f"Error processing filing {filing.accession_number}: {e}")
            raise

