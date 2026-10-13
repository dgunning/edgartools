"""Filing.text(), html() and markdown() on unusual primary documents.

What is left of this file after 6.0 removed the legacy ``edgar.files`` parser:
the tests of ``HtmlDocument``, ``ChunkedDocument`` and their helpers went with
it, and these are the ones that exercise the public ``Filing`` methods.
"""
import warnings

from edgar import Filing

warnings.filterwarnings("ignore")


def test_get_text_for_paper_filing():
    filing = Filing(form='FOCUSN', filing_date='2024-02-28', company='JACKSON NATIONAL LIFE DISTRIBUTORS LLC',
                    cik=1006323, accession_no='9999999997-24-001009')
    filing.html()
    text = filing.text()
    assert text


def test_filing_text_for_file_with_fil_extension():
    filing = Filing(form='NSAR-A', filing_date='2016-06-28',
                    company='AMERICAN FUNDS GLOBAL BALANCED FUND', cik=1505612, accession_no='0000051931-16-002553')
    html = filing.html()
    assert "American Funds Global Balanced Fund" in html
    assert "American Funds Global Balanced Fund" in filing.text()

    filing = Filing(form='NSAR-A', filing_date='2016-09-28', company='Investment Managers Series Trust', cik=1318342,
                    accession_no='0000926877-16-000629')
    assert "A000000 INVESTMENT MANAGERS SERIES TRUST" in filing.text()


def test_get_clean_html_from_unusual_filing():
    filing = Filing(form='NSAR-B', filing_date='2016-12-29', company='Thrivent Cash Management Trust', cik=1300087,
                    accession_no='0001193125-16-805810')
    html = filing.html()
    assert html
    markdown = filing.markdown()
    assert markdown


def test_get_text_from_prospectus():
    # Expected xmlns:xbrli for the instance namespace
    # but was xmlns:i="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    filing = Filing(form='485BPOS', filing_date='2024-03-28', company='DELAWARE GROUP EQUITY FUNDS II', cik=27574,
                    accession_no='0001145443-24-000056')
    text = filing.text()
    assert text


def test_parse_html_document_with_issue_decomposing_page_numbers():
    filing = Filing(form='10-Q', filing_date='2024-07-16', company='Global Arena Holding, Inc.', cik=1138724,
                    accession_no='0001756125-24-001116')
    text = filing.text()
    assert text


def test_get_html_wrapped_in_document_tag():
    filing = Filing(form='F-1', filing_date='2024-06-13', company='Haoxi Health Technology Ltd', cik=1954594,
                    accession_no='0001213900-24-052441')
    html = filing.html()
    assert html.upper().startswith("<HTML>")
    text = filing.text()
    assert text.strip().startswith("As filed with the")
