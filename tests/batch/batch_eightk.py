from edgar import *
from edgar.company_reports import EightK

def load_eightk():
    filings = Company("AAPL").get_filings(form="8-K")
    filing = filings[0]
    eightk:EightK = filing.obj()
    doc = eightk.doc
    print(doc)


if __name__ == "__main__":
    load_eightk()