from edgar import *
from pyinstrument import Profiler

use_local_storage()

def get_company_filings_no_full_load():
    c = Company("AAPL")
    filings = c.get_filings(trigger_full_load=False)

if __name__ == '__main__':
    with Profiler() as p:
        get_company_filings_no_full_load()
    p.print(timeline=True)