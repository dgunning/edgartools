from rich import print

from edgar import Filing
from edgar.company_reports import EightK, PressRelease, PressReleases
from edgar.files.htmltools import ChunkedDocument


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

    filing = Filing(form='8-K', filing_date='2023-03-20',
                    company='Artificial Intelligence Technology Solutions Inc.',
                    cik=1498148, accession_no='0001493152-23-008256')
    eightk = filing.obj()
    assert eightk.items == ['Item 8.01', 'Item 9.01']
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


def test_get_press_release():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    eightk = filing.obj()
    press_releases: PressReleases = eightk.press_releases
    print(press_releases)
    press_release: PressRelease = press_releases[0]
    print(press_release)
    assert press_release.document == 'pressrelease3-8x24.htm'
    assert isinstance(press_release, PressRelease)
    assert "Board of Directors has approved the planned spin-off" in press_release.text()


def test_get_press_release_for_8k_multiple_ex99_files():
    filing = Filing(form='8-K', filing_date='2024-01-19', company='DatChat, Inc.',
                    cik=1648960, accession_no='0001213900-24-004875')

    eightK: EightK = filing.obj()
    assert len(eightK.press_releases) == 3
    press_release: PressRelease = eightK.press_releases[0]
    assert press_release
    assert press_release.document == 'ea191807ex99-1_datchat.htm'
    assert press_release.description == 'PRESS RELEASE DATED JANUARY 16, 2024'
    assert eightK.press_releases[1].description == 'PRESS RELEASE DATED JANUARY 17, 2024'
    assert eightK.press_releases[2].description == 'PRESS RELEASE DATED JANUARY 19, 2024'


def test_get_exhibit_content_for_new_filing():
    filing = Filing(form='8-K', filing_date='2024-12-27', company='1895 Bancorp of Wisconsin, Inc. /MD/', cik=1847360,
                    accession_no='0000943374-24-000509')
    eightk = filing.obj()
    exhibit = filing.exhibits[0]
    content = eightk._get_exhibit_content(exhibit)
    assert content

def test_get_exhibit_content_for_old_filing():
    f = Filing(form='8-K', filing_date='1998-01-05', company='YAHOO INC', cik=1011006, accession_no='0001047469-98-000122')
    eightk = f.obj()
    exhibit = f.exhibits[0]
    content = eightk._get_exhibit_content(exhibit)
    assert content
    text = eightk.text()
    assert text
    assert "Yahoo" in text


def test_create_eightk_from_old_filing_with_no_html():
    f = Filing(form='8-K', filing_date='1998-01-05', company='YAHOO INC', cik=1011006, accession_no='0001047469-98-000122')
    eightk = f.obj()
    assert eightk
    html = f.html()
    print(html)


def test_get_content_for_eightk_with_binary_exhibit():
    filing = Filing(form='8-K', filing_date='2010-02-26', company='MANNATECH INC', cik=1056358, accession_no='0001056358-10-000003')
    eightk = filing.obj()
    exhibits = filing.exhibits
    print(exhibits)
    content = eightk._content_renderables()
    assert content

def test_eightk_date_of_report():
    f = Filing(form='8-K', filing_date='1995-01-24', company='AMERICAN EXPRESS CO', cik=4962, accession_no='0000004962-95-000001')
    eightk = f.obj()
    assert eightk.date_of_report == ''