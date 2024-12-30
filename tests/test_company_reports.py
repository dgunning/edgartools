import pandas as pd
from rich import print

from edgar import Filing
from edgar.company_reports import TenK, TenQ, TwentyF, EightK
from edgar.files.htmltools import ChunkedDocument

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
    assert tenq.financials.get_balance_sheet()
    assert tenq.financials.get_income_statement()
    assert tenq.financials.get_cash_flow_statement()
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
    filing = Filing(form='10-K', filing_date='2023-03-31', company='7GC & Co. Holdings Inc.',
cik=1826011, accession_no='0001193125-23-086073')
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

def test_tenk_item_structure():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    tenk = filing.obj()
    tenk_repr = repr(tenk)
    print()
    print(tenk_repr)
    assert "Item 1" in tenk_repr


def test_tenk_section_properties():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
    tenk:TenK = filing.obj()
    assert tenk.management_discussion
    assert tenk.business
    assert tenk.risk_factors
    assert tenk.directors_officers_and_governance


def test_tenk_detect_items_with_spaces():
    f = Filing(company='LOCKHEED MARTIN CORP', cik=936468, form='10-K', filing_date='2024-01-23', accession_no='0000936468-24-000010')
    tenk = f.obj()
    # Previously we were not detecting items with spaces
    assert "Item 1" in tenk.items
