from pathlib import Path
from rich import print

from edgar.documents import *

pd.options.display.max_columns = 10


def test_html_document_does_not_drop_content():
    html_str = Path("data/ixbrl.simple.html").read_text()
    document = HtmlDocument.from_html(html_str)

    # All the non-space text is the same
    expected_text = re.sub(r'\s+', '', BeautifulSoup(html_str, 'lxml').text)
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
    html_str = Path("data/NextPoint.8K.html").read_text()
    html_document = HtmlDocument.from_html(html_str)
    assert "Item 8.01" in html_document.text


def test_parse_complicated_htmldocument():
    html_str = Path("data/Nvidia.10-K.html").read_text()
    html_document = HtmlDocument.from_html(html_str)
    print(html_document.text)
    assert "NVIDIA has a platform strategy" in html_document.text


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
    text = Path("data/NextPoint.8K.html").read_text()
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


def test_handle_span_inside_divs_has_correct_whitespace():
    html = """
    <html>
    <body>
    <div>Section Header</div>
    <p>The information provided in&#160;<span style="text-decoration: underline">Item 5.03</span>&#160;is hereby incorporated by reference.</p>
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    assert "Section Header\n" in document.text
    assert "The information provided in" in document.text
    assert "Item 5.03" in document.text
    assert "is hereby incorporated by reference" in document.text
    assert "is hereby incorporated by reference." in document.text


def test_consecutive_div_spans():
    html = """
    <html>
    <body>
        <div><span>SPAN 1</span></div>
        <div><span>SPAN 2</span></div>
        </body>
    </html>
    
    """
    document = HtmlDocument.from_html(html)
    print()
    print(document.text)


def test_paragraph_is_not_split():
    html = """
    <html>
    <body>
<p style="font: 10pt Times New Roman, Times, Serif; margin: 0pt 0; text-align: justify; text-indent: 0.5in">The Company is effecting
the Reverse Stock Split to satisfy the $1.00 minimum bid price requirement, as set forth in Nasdaq Listing Rule 5550(a)(2), for continued
listing on The NASDAQ Capital Market. As previously disclosed in a Current Report on Form 8-K filed with the Securities and Exchange
Commission on September 8, 2023, on September 7, 2023, the Company received a deficiency letter from the Listing Qualifications Department
(the “<span style="text-decoration: underline">Staff</span>”) of the Nasdaq Stock Market (“<span style="text-decoration: underline">Nasdaq</span>”) notifying the Company that, for the preceding
30 consecutive business days, the closing bid price for the common stock was trading below the minimum $1.00 per share requirement for
continued inclusion on The Nasdaq Capital Market pursuant to Nasdaq Listing Rule 5550(a)(2) (the “<span style="text-decoration: underline">Bid Price Requirement</span>”).
In accordance with Nasdaq Rules, the Company has been provided an initial period of 180 calendar days, or until March 5, 2024 (the “<span style="text-decoration: underline">Compliance
Date</span>”), to regain compliance with the Bid Price Requirement. If at any time before the Compliance Date the closing bid price
for the Company’s common stock is at least $1.00 for a minimum of 10 consecutive business days, the Staff will provide the Company
written confirmation of compliance with the Bid Price Requirement. By effecting the Reverse Stock Split, the Company expects that the
closing bid price for the common stock will increase above the $1.00 per share requirement.</p>
    </body>
    
    </html>
    """
    document = HtmlDocument.from_html(html)
    print(document.text)
    assert not '\n' in document.text.strip()


def test_html_comments_are_removed():
    html = """
    <html>
    <body>
    <h1>This HTML has comments</h1>
        <!-- this is a comment -->
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    assert not "this is a comment" in document.text

def test_span_with_nonbreaking_spaces():
    html = """
    <html>
    <div style="-sec-extract:summary">
    <span>Item 2.02</span><span>&nbsp;&nbsp;&nbsp;&nbsp;</span><span>Results of Operations and Financial Condition</span></div>
    </html>
    """
    document = HtmlDocument.from_html(html)
    print()
    print(document.text)
