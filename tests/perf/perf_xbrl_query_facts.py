from edgar.xbrl import XBRLData, XBRLInstance
from edgar.financials import Financials
from pathlib import Path

from edgar import *
from pyinstrument import Profiler

if __name__ == '__main__':
    filing = Filing(company='Tesla, Inc.', cik=1318605,
                    form='10-K', filing_date='2024-01-29',
                    accession_no='0001628280-24-002390')
    instance = XBRLInstance.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text())


    with Profiler(async_mode=True) as p:
        revenue = instance.query_facts('us-gaap:Revenue')

    p.print()

