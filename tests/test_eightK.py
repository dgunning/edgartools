from edgar import Filing
from edgar.company_reports import EightK


def test_eightk_repr():
    filing = Filing(form='8-K', filing_date='2023-10-10', company='ACELRX PHARMACEUTICALS INC', cik=1427925,
                    accession_no='0001437749-23-027971')
    eightk: EightK = filing.obj()
    print()
    print(eightk)
