from edgar import Filing
from edgar.company_reports import EightK


def test_eightk_has_items_in_repr():
    filing = Filing(form='8-K', filing_date='2023-10-10', company='ACELRX PHARMACEUTICALS INC', cik=1427925,
                    accession_no='0001437749-23-027971')
    eightk: EightK = filing.obj()
    assert eightk.items == ['Item 5.02', 'Item 5.07', 'Item 9.01']
    eightk_repr = repr(eightk)
    assert '5.02' in eightk_repr
    assert '5.07' in eightk_repr
    assert '9.01' in eightk_repr
    print(eightk)



