from rich import print
from tqdm.auto import tqdm

from edgar import *
from edgar.xbrl.xbrldata import XBRLAttachments


def examine_filing_xbrl(filing: Filing):
    doc = XBRLAttachments(filing.attachments)
    if doc.empty:
        print(f"No XBRL data found for filing {filing}")
        return
    xbrl = doc.get_xbrl()
    print(xbrl)


if __name__ == '__main__':
    filings = get_filings(form=['S-1', 'S-3', 'N-1', 'N-2', '424B5', '424B2'], index="xbrl").head(100)
    for filing in tqdm(filings):
        examine_filing_xbrl(filing)
