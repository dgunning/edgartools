from edgar import Filing
from edgar.company_reports import EightK
from unstructured.partition.html import partition_html
from pathlib import Path


def test_eightk_repr():
    filing = Filing(form='8-K', filing_date='2023-10-10', company='ACELRX PHARMACEUTICALS INC', cik=1427925,
                    accession_no='0001437749-23-027971')
    eightk: EightK = filing.obj()
    print()
    print(eightk)

def test_eightk_item_parsing_after_dollar_sign():
    # This issue was reported ib https://github.com/dgunning/edgartools/issues/21
    # The issue was that the text in item 8.01 was cutoff after the dollar sign
    filing = Filing(company='NexPoint Capital, Inc.', cik=1588272, form='8-K', filing_date='2023-12-20',
                    accession_no='0001193125-23-300021')

    with Path('data/NextPoint.8k.html').open('w') as f:
        f.write(filing.html())
    # partition the html and test if the text is in one of the elements
    elements = partition_html(text=filing.html())
    for element in elements:
        print(element.text)

    #text = filing.text()
    #eightk = filing.obj()
    #item_801 = eightk['Item 8.01']
    #print(item_801)
    #print(text)
