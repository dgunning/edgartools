"""Filing.html() and Filing.text() on primary documents that are not ordinary HTML.

What is left of this file after 6.0 removed the legacy ``edgar.files`` parser:
the tests of its ``Document``/``SECHTMLParser`` went with it.
"""
from rich import print

from edgar import Filing


def test_document_from_filing_with_plain_text_filing_document():
    f = Filing(form='SC 13G/A', filing_date='2024-11-25', company='Bridgeline Digital, Inc.', cik=1378590,
               accession_no='0001968076-24-000022')
    html = f.html()
    assert html


def test_get_text_from_filing_with_no_body_tag():
    filing = Filing(form='TA-1/A', filing_date='2024-04-17', company='PEAR TREE ADVISORS INC /TA',
                    cik=949738, accession_no='0000949738-24-000005')
    html = filing.html()
    assert html

    # No body tag
    text = filing.text()
    assert not text


def test_html_from_old_filings_is_none():
    f = Filing(form='8-K', filing_date='1998-01-05', company='YAHOO INC', cik=1011006,
               accession_no='0001047469-98-000122')
    text = f.text()
    assert text
    html = f.html()
    assert not html


def test_get_html_problem_filing():
    filing = Filing(form='497K',
                    filing_date='2024-12-30',
                    company='VOYAGEUR MUTUAL FUNDS',
                    cik=906236,
                    accession_no='0001206774-24-001226')
    text = filing.text()
    assert text
    print(text)
