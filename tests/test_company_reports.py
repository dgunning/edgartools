import pandas as pd
from rich import print

from edgar import Filing
from edgar import find
from edgar.company_reports import TenK, TenQ, TwentyF, EightK
from edgar.htmltools import ChunkedDocument

pd.options.display.max_colwidth = 40


def test_tenk_filing_with_no_gaap():
    # This filing has no GAAP data
    filing = Filing(form='10-K', filing_date='2023-04-06', company='Frontier Masters Fund', cik=1450722,
                    accession_no='0001213900-23-028058')
    tenk: TenK = filing.obj()
    assert tenk
    assert tenk.financials is not None


def test_tenk_item_and_parts():
    filing = Filing(form='10-K', filing_date='2023-04-06', company='Frontier Masters Fund', cik=1450722,
                    accession_no='0001213900-23-028058')

    chunked_document = ChunkedDocument(filing.html())
    chunk_df = chunked_document._chunked_data
    tenk: TenK = filing.obj()
    # Get item 1
    item1 = tenk['Item 1']
    assert 'Item 1.' in item1

    # Case in
    item3 = tenk['Item 3']
    assert 'There are no material legal' in item3
    print(item3)
    # Show Item 1
    # tenk.view('Item 1')


def test_tenq_filing():
    filing = Filing(form='10-Q', filing_date='2023-04-06', company='NIKE, Inc.', cik=320187,
                    accession_no='0000320187-23-000013')
    tenq: TenQ = filing.obj()
    assert tenq
    assert tenq.financials is not None
    assert tenq.financials.balance_sheet
    assert tenq.financials.income_statement
    assert tenq.financials.cash_flow_statement
    print()
    print(tenq)


def test_is_valid_item_for_filing():
    assert TenK.structure.is_valid_item('Item 1')
    assert TenK.structure.is_valid_item('Item 9A')
    assert TenK.structure.is_valid_item('Item 9A', part='Part II')
    assert TenK.structure.is_valid_item('ITEM 9A', part='Part II')
    assert TenK.structure.is_valid_item('ITEM 9A', part='PART II')
    assert not TenK.structure.is_valid_item('Item 9A', part='Part III')

    assert TenQ.structure.is_valid_item('Item 4')
    assert not TenQ.structure.is_valid_item('Item 40')
    assert TenQ.structure.is_valid_item('Item 4', "PART I")
    assert TenQ.structure.is_valid_item('Item 4', "PART II")

    assert TwentyF.structure.is_valid_item('ITEM 10')
    assert not TwentyF.structure.is_valid_item('ITEM 10', "PART IV")

    assert EightK.structure.is_valid_item('Item 1.01')
    # Part is ignored for 8-K
    assert EightK.structure.is_valid_item('Item 1.01', "PART IV")


def test_chunk_items_for_company_reports():
    filing = find("0001193125-23-086073")
    html = filing.html()
    chunked_document = ChunkedDocument(html)
    print()
    items = chunked_document.show_items("Item.str.contains('ITEM', case=False)", "Item")
    assert not items.empty
    print(items)


def test_items_for_10k_filing():
    filing = Filing(form='10-K', filing_date='2023-11-08', company='CHS INC', cik=823277,
                    accession_no='0000823277-23-000053')
    tenk = filing.obj()
    item_2 = tenk['Item 2']
    assert "We own or lease energy" in item_2
    assert "Kaw Pipe Line Company" in item_2
    print(item_2)

    item_7A = tenk['Item 7A']
    print(item_7A)
    assert "Commodity Price Risk" in item_7A

    item_15 = tenk['Item 15']
    assert item_15
    assert 'FINANCIAL STATEMENTS' in item_15
    assert tenk['ITEM 15'] == item_15
    print(item_15)


def test_items_for_8k_filing():
    filing = Filing(form='8-K', filing_date='2023-11-14',
                    company='ALPINE 4 HOLDINGS, INC.',
                    cik=1606698,
                    accession_no='0001628280-23-039016')
    chunked_df = ChunkedDocument(filing.html())._chunked_data
    eightk = EightK(filing)
    doc = eightk.doc

    assert eightk.items == ['Item 1.01', 'Item 2.03', 'Item 9.01']

    item_901 = doc['Item 9.01']
    assert "Merchant Cash Advance" in item_901


def test_eightk_with_spaces_in_items():
    # This filing has space characters .&#160;&#160; in the item numbers
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AAR CORP', cik=1750,
                    accession_no='0001104659-23-034265')
    eightk = filing.obj()
    print()
    print(eightk)
    assert eightk.items == ['Item 7.01', 'Item 8.01', 'Item 9.01']
    assert 'Company acquired Trax for a purchase price of $120 million in cash' in eightk['Item 8.01']


def test_eightk_with_no_signature_header():
    # This filing has no SIGNATURE header, which means the signature is being detected in Item 9.01
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AMERISERV FINANCIAL INC /PA/', cik=707605,
                    accession_no='0001104659-23-034205')
    eightk = filing.obj()
    assert eightk.items == ['Item 8.01', 'Item 9.01']
    assert "Cover Page" in eightk['Item 9.01']
    # We did not include the signature in the item
    assert 'Pursuant to the requirements of the Securities Exchange Act' not in eightk['Item 9.01']


def test_eightk_difficult_parsing():
    # As we find problems with parsing, we add them here
    filing = Filing(form='8-K', filing_date='2023-03-20', company='4Front Ventures Corp.', cik=1783875,
                    accession_no='0001279569-23-000330')
    eightk = filing.obj()
    assert eightk.items == ['Item 5.02']
    assert 'appointed Kristopher Krane as a member of the Board' in eightk['Item 5.02']

    filing = Filing(form='8-K', filing_date='2023-03-20', company='ALBEMARLE CORP', cik=915913,
                    accession_no='0000915913-23-000088')
    eightk = filing.obj()
    assert eightk.items == ['Item 5.02', 'Item 9.01']
    assert 'receive an annual base salary of $1,400,000' in eightk['Item 5.02']

    filing = Filing(form='8-K', filing_date='2023-03-20', company='Artificial Intelligence Technology Solutions Inc.',
                    cik=1498148, accession_no='0001493152-23-008256')
    eightk = filing.obj()
    assert eightk.items == ['Item 8.01', 'ITEM 9.01']
    assert "we will be issuing a Shareholder Letter to our shareholders," in eightk['Item 8.01']

    filing = Filing(form='8-K', filing_date='2023-03-20', company='CATO CORP', cik=18255,
                    accession_no='0001562762-23-000124')
    eightk = filing.obj()
    assert eightk.items == ['Item 9.01']


def test_eightk_with_items_split_by_newlines():
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AFC Gamma, Inc.', cik=1822523,
                    accession_no='0001829126-23-002149')
    eightk: EightK = filing.obj()
    print()
    assert eightk.items == ['Item 5.02', 'Item 7.01', 'Item 9.01']
    assert "press release announcing Mr. Hetzel’s appointment as Chief Financial Officer" in eightk['Item 7.01']
    print(eightk)


def test_create_eightk_obj_and_find_items():
    adobe_8K = Filing(form='8-K',
                      filing_date='2023-03-15',
                      company='ADOBE INC.',
                      cik=796343,
                      accession_no='0000796343-23-000044')
    eightk = adobe_8K.obj()
    assert isinstance(eightk, EightK)
    assert eightk.filing_date == '2023-03-15'
    assert eightk.form == '8-K'
    assert eightk.company == 'ADOBE INC.'

    assert eightk.items == ['Item 2.02', 'Item 9.01']
    print()
    item_202 = eightk['Item 2.02']
    print(item_202)
    assert "Item 2.02" in item_202
    assert "Results of Operations and Financial Condition" in item_202
    print(eightk['Item 9.01'])
