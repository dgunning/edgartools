import re
from pathlib import Path
from rich import print

from edgar.documents import *
pd.options.display.max_columns = 10


def test_html_document_does_not_drop_content():
    html_str = Path("data/ixbrl.simple.html").read_text()
    document = HtmlDocument.from_html(html_str)

    # All the non-space text is the same
    expected_text = re.sub(r'\s+', '', BeautifulSoup(html_str, 'html5lib').text)
    expected_text = expected_text.replace("DEF14Afalse000001604000000160402022-10-012023-09-30iso4217:USD", "")
    actual_text = re.sub(r'\s+', '', document.text)
    assert actual_text == expected_text


def test_html_document_data():
    document: HtmlDocument = HtmlDocument.from_html(Path("data/ixbrl.simple.html").read_text())
    document_ixbrl: DocumentData = document.data
    assert "NamedExecutiveOfficersFnTextBlock" in document_ixbrl
    assert 'PeoName' in document_ixbrl

    property = document_ixbrl['PeoName']
    assert property['start'] == '2022-10-01'
    assert property['end'] == '2023-09-30'
    assert property['value'] == 'Sean D.\n            Keohane'
    print()
    print(property)


def test_parse_simple_htmldocument():
    html_str = Path("data/NextPoint.8k.html").read_text()
    html_document = HtmlDocument.from_html(html_str)
    print(html_document.text)


def test_parse_complicated_htmldocument():
    html_str = Path("data/Nvidia.10-k.html").read_text()
    html_document = HtmlDocument.from_html(html_str)
    print(html_document.text)


def test_htmldocument_from_filing_with_document_tag():
    """
    The text does not include the text of the document tag
    <DOCUMENT>
    <TYPE>424B5
    <SEQUENCE>1
    <FILENAME>d723817d424b5.htm
   <DESCRIPTION>424B5
    """
    html_str = Path("data/PacificGas.424B5.html").read_text()
    html_document = HtmlDocument.from_html(html_str)
    assert "d723817d424b5.htm" not in html_document.text


def test_parse_ixbrldocument_with_nested_div_tags():
    text = Path("data/Nextpoint.8K.html").read_text()
    document: HtmlDocument = HtmlDocument.from_html(text)
    # The html
    assert "5.22" in document.text
    assert not "<ix:nonNumeric" in document.text


def test_parse_ixbrldocument_with_dimensions():
    text = Path("data/cabot.DEF14A.ixbrl.html").read_text()
    headers = BeautifulSoup(text, 'lxml').find_all('ix:header')
    document: DocumentData = DocumentData.parse_headers(headers)
    assert document

    # The header
    assert len(document.data) == 3
    assert 'P10_01_2020To09_30_2021' in document.context


