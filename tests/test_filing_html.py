from pathlib import Path

from edgar import *
from edgar.core import is_probably_html
from edgar.documents import parse_html
from edgar.sgml.tools import extract_text_between_tags


def test_get_html_from_document_tags():
    # This file has html inside <DOCUMENT> tags
    content = Path('data/html/SC-13G-DOCUMENT.html').read_text()
    text = extract_text_between_tags(content, "TEXT")
    assert is_probably_html(text)
    document = parse_html(text)
    assert "SCHEDULE 13G" in document.text()
    assert "LIVENT CORPORATION" in document.text()


def test_get_plaintext_from_document_tags():
    # This file has plain text inside <DOCUMENT> tags
    content = Path('data/html/SG-13G-DOCUMENT-WITH-TEXT.html').read_text()
    text = extract_text_between_tags(content, "TEXT")
    assert not is_probably_html(text)
    document = parse_html(text)
    assert "SCHEDULE 13G" in document.text()


def test_get_html_inside_document_tags():
    filing = Filing(form='SC 13G',
                    filing_date='2024-01-08',
                    company='ICS OPPORTUNITIES, LTD.',
                    cik=1487118,
                    accession_no='0001487118-24-000001')

    html = filing.html()
    assert html
    # We can parse the HTML
    document = parse_html(html)
    assert document.text()


def test_get_html_from_filing_with_plain_text():
    filing = Filing(form='SC 13G/A', filing_date='2024-01-22', company='BlackRock Inc.', cik=1364742,
           accession_no='0001086364-24-000768')
    html = filing.html()
    assert html
    assert is_probably_html(html)


def test_get_text_from_filing_with_pre_tag():
    filing = Filing(form='8-K', filing_date='2024-12-20',
                    company='Liaoning Shuiyun Qinghe Rice Industry Co., Ltd.',
                    cik=710782, accession_no='0000710782-24-000005')
    html = filing.html()
    assert html
    text = filing.text()
    assert text
