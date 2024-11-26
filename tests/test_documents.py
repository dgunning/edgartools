import re
from copy import copy
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from rich import print

from edgar import Filing
from edgar.datatools import dataframe_to_text
from edgar.files.html_documents import *
from edgar.files.html_documents import fixup
from edgar.files.htmltools import ChunkedDocument
from typing import Optional

pd.options.display.max_columns = 10
import warnings
warnings.filterwarnings("ignore")


def test_html_document_does_not_drop_content():
    warnings.filterwarnings("ignore")
    html_str = Path("data/ixbrl.simple.html").read_text()
    document = HtmlDocument.from_html(html_str)

    # All the non-space text is the same
    expected_text = re.sub(r'\s+', '', BeautifulSoup(html_str, 'lxml').text)
    expected_text = expected_text.replace("DEF14Afalse000001604000000160402022-10-012023-09-30iso4217:USD", "")
    actual_text = re.sub(r'\s+', '', document.text)
    assert actual_text == expected_text


def test_html_document_data():
    document: HtmlDocument = HtmlDocument.from_html(Path("data/ixbrl.simple.html").read_text(), extract_data=True)
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
    assert "Item 8.01" in html_document.text


def test_items_headers_are_separate_chunks():
    html = """
    <html>
    <body>
    <div><span>Item 1.01&nbsp;&nbsp;&nbsp;&nbsp;Entry into a Material Definitive Agreement.</span></div>
    <div><span><br></span></div>
    <div><span>Item 2.03&nbsp;&nbsp;&nbsp;&nbsp;Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement of a Registrant.</span></div>
    <div><span><br></span></div>
    <div><span>On November 8, 2023, Alpine 4 Holdings, Inc., a Delaware corporation</span></div>
    <div><span><br></span></div>
    <div><span>Item 9.01 Financial Statements and Exhibits</span></div>
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    blocks = document.blocks
    # The headers are separate blocks
    for item in ['Item 1.01', 'Item 2.03', 'Item 9.01']:
        assert any(block.text.startswith(item) for block in blocks)

    # Now test the chunks
    for chunk in document.generate_chunks():
        print(chunk)
        print('*' * 80)


def test_item_split_by_newline():
    """
    See
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AFC Gamma, Inc.', cik=1822523,
                    accession_no='0001829126-23-002149')
    """
    html = """
    <html>
    <body>
    <div>
        <span><b>Item
                            5.02</b></span>
                            <span><b>Departure
of Directors or Certain Officers; Election of Directors;</b></span>
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    blocks = document.blocks
    assert "Item 5.02" in document.text
    assert blocks[0].text.startswith("Item 5.02")
    print()
    print('[' + document.text)


def test_parse_complicated_htmldocument():
    html_str = Path("data/Nvidia.10-K.html").read_text()
    html_document = HtmlDocument.from_html(html_str)

    assert "NVIDIA has a platform strategy" in html_document.text

    doc: ChunkedDocument = ChunkedDocument(html_str)
    assert "are not a part of this Annual Report on Form 10-K" in doc['Item 1']
    assert "evaluating NVIDIA, the following risk factors should be considered" in doc['Item 1A']
    assert "Microsoft may have first and last rights of refusal to purchase the stock" in doc['Item 1A']
    assert "Item 15 of this Annual Report on Form 10-K for a discussion" in doc['Item 3']
    assert "Not applicable." in doc['Item 4']
    assert "stock is traded on the Nasdaq Global Select Market under the symbol NVDA" in doc['Item 5']
    assert "The following discussion and analysis of our financial condition and results of operations" in doc["Item 7"]
    assert "Climate Change" in doc["Item 7"]
    assert "The information required by this Item is set forth in our Consolidated Financial Statements" in doc[
        'Item 8']
    assert "None" in doc['Item 9']
    assert "Based on their evaluation as of January 29, 2023, our management" in doc['Item 9A']
    assert "all control issues and instances of fraud, if any, within NVIDIA have been detected" in doc['Item 9A']
    assert "Equity Compensation Plan Information" in doc["Item 12"]


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
    print(document.text)
    # The html
    assert "5.22" in document.text
    assert "at $5.22 per share" in document.text
    assert not "<ix:nonNumeric" in document.text


def test_eightk_item_parsing_after_dollar_sign():
    # This issue was reported ib https://github.com/dgunning/edgartools/issues/21
    # The issue was that the text in item 8.01 was cutoff after the dollar sign
    filing = Filing(company='NexPoint Capital, Inc.', cik=1588272, form='8-K', filing_date='2023-12-20',
                    accession_no='0001193125-23-300021')
    document: HtmlDocument = HtmlDocument.from_html(filing.html())
    assert "(the “DRP”) at $5.22 per share" in document.text
    assert "(the “DRP”) at $5.22 per share" in document.markdown
    print(document.markdown)


def test_parse_inline_divs_with_ixbrl_tags():
    html = """
    <html>
    <body>
    <div>
    <div style="display:inline;"><ix:nonNumeric name="dei:EntityAddressAddressLine1" contextRef="P12_20_2023To12_20_2023">300 Crescent Court</ix:nonNumeric></div>, <div style="display:inline;"><ix:nonNumeric name="dei:EntityAddressAddressLine2" contextRef="P12_20_2023To12_20_2023">Suite 700</ix:nonNumeric></div> 
    </div>
    </body>
    </html>
    """
    # 300 Crescent Court, Suite 700
    document: HtmlDocument = HtmlDocument.from_html(html)
    blocks = document.blocks
    print(''.join([b.text for b in blocks]))


def test_parse_ixbrldocument_with_dimensions():
    text = Path("data/cabot.DEF14A.ixbrl.html").read_text()
    warnings.filterwarnings("ignore")
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


def test_clean_document_text():
    html = """
       <html>
       <body>
       <table>
        <tr>
        <td><b>Item 3.</b></span></td>
        <td><b><i>LEGAL PROCEEDINGS. </i></b></span></td></tr>
        </table>
       </body>
       </html>
       """
    # assert "Item&#160;3." in html
    # assert "Item 3." in html
    # document = HtmlDocument.from_html(html)
    # print(document.text)
    # assert "Item 3." in document.text


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


def test_page_numbers_are_removed():
    html = """
    <html>
    <h1>Header</h1>
    <div>
        <div>
        <div><span>19</span></div>
        </div>
    </div>
    <h1>Another header</h1>
    <div>
        <div>
          <div><span>20</span></div>
        </div>
    </div>
    
    </html>
    """
    document = HtmlDocument.from_html(html)
    assert not "19" in document.text
    assert not "20" in document.text

    html = """
    <html>
    <h1>Header</h1>
    <div>
        <div>
            <div><span>180</span></div>
        </div>
    </div>
    <div>
        <div>
            <div><span>181</span></div>
        </div>
    </div>
    </html>
    """
    document = HtmlDocument.from_html(html)
    assert not "180" in document.text
    assert not "181" in document.text


def test_lists_are_preserved_in_block():
    html = """
    <html>
    <body>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    <ol>
        <li>Ordered List Item 1</li>
        <li>Ordered List Item 2</li>
    </ol>
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    assert "Item 1" in document.text
    assert "Item 2" in document.text
    assert "Ordered List Item 1" in document.text
    assert "Ordered List Item 2" in document.text


def test_compress_blocks():
    html = """
    <html>
    <body>
        <div>$<span>5.20</span>&nbsp;<span>dollars</span>
        </div>
        <table>
            <tr><th>Name</th><th>Age</th></tr>
            <tr><td>Mark</td><td>23</td></tr>
        </table>
        Last content
    </body>
    </html>
    """
    document = HtmlDocument.from_html(html)
    blocks = copy(document.blocks)

    uncompressed_blocks = (blocks[:2]
                           + [TextBlock(word) for word in ['Age', ' ', 'is', ' ', 'just', ' ', 'a', ' ', 'number']]
                           + blocks[2:])
    compressed_blocks = HtmlDocument._compress_blocks(uncompressed_blocks)
    assert "Age is just a number" == compressed_blocks[2].text
    assert 'Last content' in compressed_blocks[-1]


def test_detect_header():
    assert SECLine("Accrued Clinical Trial Expenses").is_header
    assert SECLine("1. Business Overview and Liquidity Business Organization and Overview").is_header
    assert not SECLine("two short").is_header
    assert SECLine("Item 9. Changes in and Disagreements With Accountants on Accounting and Financial Disclosure.")
    assert SECLine("Item 8. Financial Statements and Supplementary Data.").is_header
    assert SECLine("Item 8.01.		Other Events").is_header
    assert SECLine(" 18. Subsequent Events").is_header
    assert not SECLine(" shares of the Company’s common stock at an offering price to the public of $29.50").is_header
    assert SECLine("15. Derivative Liability").is_header
    assert SECLine(".  13. Common Stock Warrants").is_header
    assert not SECLine("Stock-based compensation expense recorded for employee options was $19.5").is_header
    assert SECLine(" 11. Common Stock").is_header
    assert SECLine("WHERE YOU CAN FIND MORE INFORMATION").is_header
    assert SECLine("  5. Market Risk").is_header
    assert SECLine("Forward-Looking Statements").is_header
    assert not SECLine("© 2023 NVIDIA Corporation. All rights reserved.").is_header
    assert SECLine("Professional Visualization").is_header
    assert SECLine(
        "Item 2.03    Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement of a Registrant.").is_header


def test_textanalysis():
    text_analysis = TextAnalysis("Washington, D.C. 20549")
    assert not text_analysis.is_mostly_title_case

    text_analysis = TextAnalysis("")
    assert text_analysis.num_words == 0


def test_detect_regular_sentence():
    assert SECLine("")


def test_generate_chunks():
    html = """
    <html>
    
    <body>
    <div>Risk Factors</div>
    <div>Risks Related to Our Industry and Markets</div>
<div>
<p>
Failure to meet the evolving needs of our industry and markets may adversely impact our financial results.
Our accelerated computing platforms experience rapid changes in technology, customer requirements, competitive products, and industry standards.
Our success depends on our ability to:
</p>
<ul>
<li>timely identify industry changes, adapt our strategies, and develop new or enhance existing products and technologies that meet the evolving needs of these markets</li>
<li>develop new products and technologies through investments in research and development;</li>
<li>launch new offerings with new business models including standalone software, cloud solutions, and software-, infrastructure-, or platform-as-a-service solutions;</li>
<li>expand the ecosystem for our products and technologies;</li>
<li>meet evolving and prevailing customer and industry safety and compliance standards;</li>
<li>manage product and software lifecycles to maintain customer and end user satisfaction;</li>
<li>develop, acquire, and maintain the internal and external infrastructure needed to scale our business, and</li>
<li>complete technical, financial, compliance, sales and marketing investments for some of the above activities.</li>
</ul>
</div>
<div>
We invest in research and development in markets where we have a limited operating history, which may not produce meaningful revenue for several years, if at all. If we fail to develop or monetize new products and technologies, or if they do not become widely adopted, our financial results could be adversely affected. Obtaining design wins may involve a lengthy process and depend on our ability to anticipate and provide features and functionality that customers will demand. They also do not guarantee revenue. Failure to obtain a design win may prevent us from obtaining future design wins in subsequent generations. We cannot ensure that the products and technologies we bring to market will provide value to our customers and partners. If we fail any of these key success criteria, our financial results may be harmed.
We will offer enterprise customers NVIDIA AI cloud services directly and through our network of partners. Examples of these services include NVIDIA DGX Cloud, which is cloud-based infrastructure and software for training AI models, and customizable pretrained AI models. NVIDIA has partnered with leading cloud service providers to host these services in their data centers, and we entered into multi-year cloud service agreements in the second half of fiscal year 2023 to support these offerings and our research and development activities. NVIDIA AI cloud services may not be successful and will take time, resources and investment. We also offer or plan to offer standalone software solutions for AI including NVIDIA AI Enterprise, NVIDIA Omniverse, NVIDIA DRIVE for automotive, and several other software solutions. 
</div>

    </body>
    
    </html>
    """
    document = HtmlDocument.from_html(html)
    print()
    for chunk in document.generate_chunks():
        print(chunk)
        print('-' * 80)


def test_get_clean_html():
    html = """
    <html>
    <body>
    <h1>Header</h1>
        <!-- This is a header -->
        <ix:header>Header</ix:header>
        <a href="#toc">Table of Contents</a>
    </body>
    </html>
    """
    html = get_clean_html(html)
    assert not "<ix:header>" in html
    assert not '<!-- This is a header -->' in html


def test_get_text_for_paper_filing():
    filing = Filing(form='FOCUSN', filing_date='2024-02-28', company='JACKSON NATIONAL LIFE DISTRIBUTORS LLC',
                    cik=1006323, accession_no='9999999997-24-001009')

    text = filing.text()
    assert text


def test_get_table_blocks():
        html = """
        <html>
        
        <body>
        <table>
        <thead>
            <tr><th>#</th><th>Count</th></tr>
        </thead>
        <tbody>
            <tr>1<td></td><td>400</td></tr>
            <tr>2<td></td><td>900</td></tr>
        </tbody>
        </table>
        </body>
        </html>
        """
        document = HtmlDocument.from_html(html)
        tables = document.get_table_blocks()
        assert len(tables) == 1


def test_table_to_text():
    html = """
    <table cellpadding="0" cellspacing="0" style="border-collapse: collapse; width: 100%; font: 10pt Times New Roman, Times, Serif">
<tr style="vertical-align: bottom; background-color: White">
<td style="padding-bottom: 1.5pt"> </td><td style="font-weight: bold; padding-bottom: 1.5pt"> </td>
<td style="border-bottom: Black 1.5pt solid; font-weight: bold; text-align: left"> </td><td style="border-bottom: Black 1.5pt solid; font-weight: bold; text-align: center"><font style="font-family: Times New Roman, Times, Serif; font-size: 10pt"><b>Per
                                         Share</b></font></td><td style="padding-bottom: 1.5pt; font-weight: bold; text-align: left"> </td><td style="font-weight: bold; padding-bottom: 1.5pt"> </td>
<td style="border-bottom: Black 1.5pt solid; font-weight: bold; text-align: left"> </td><td style="border-bottom: Black 1.5pt solid; font-weight: bold; text-align: center"><font style="font-family: Times New Roman, Times, Serif; font-size: 10pt"><b>Total</b></font></td><td style="padding-bottom: 1.5pt; font-weight: bold; text-align: left"> </td></tr>
<tr>
<td> </td>
<td>$</td><td style="width: 12%; text-align: right">14.50</td><td style="width: 1%; text-align: left"> </td><td style="width: 2%"> </td>
<td>$</td><td style="width: 12%; text-align: right">95,700,000</td><td style="width: 1%; text-align: left"> </td></tr>
<tr>
<td>Underwriting discounts and commissions (1)</td><td> </td>
<td>$</td><td style="text-align: right">0.87</td><td style="text-align: left"> </td><td> </td>
<td>$</td><td style="text-align: right">5,742,000</td><td style="text-align: left"> </td></tr>
<tr>
<td>Proceeds to us, before expenses</td><td> </td>
<td>$</td><td style="text-align: right">13.63</td><td style="text-align: left"> </td><td> </td>
<td>$</td><td style="text-align: right">89,958,000</td><td style="text-align: left"> </td></tr>
</table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    text = table_to_text(table)
    print(text)
    assert text.count('\n') == 5
    fixed = fixup(text)
    assert fixed.count('\n') == 5
    print(fixed)


def test_table_block_to_dataframe():
    html = """
    <table>
<tr>
<td><b>SVB
    Leerink</b></font></td>
<td><font><b>Cantor</b></font></td></tr>
</table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    table_block = TableBlock(table)
    df = table_block.to_dataframe()
    assert df.shape == (1, 2)


def test_get_table_containing_text():
    filing = Filing(form='424B5', filing_date='2020-06-18', company='Provention Bio, Inc.', cik=1695357, accession_no='0001493152-20-011383')
    document:HtmlDocument = HtmlDocument.from_html(filing.html())
    blocks = document.get_table_blocks()
    print()
    table_blocks = [block for block in blocks if 'Number of' in block.get_text()]
    for block in table_blocks:
        table = block.to_dataframe()
        if not table.empty:
            print(dataframe_to_text(table))


def test_html_to_text():
    html = Path('data/NextPoint.8K.html').read_text()
    text = html_to_text(html)
    assert text
    assert 'NEXPOINT CAPITAL' in text
    print(text)


def test_document_get_text():
    """Render text from a document"""
    filing = Filing(company='Paramount Global', cik=813828, form='8-K', filing_date='2024-04-29',
                    accession_no='0000813828-24-000018')
    document:HtmlDocument = HtmlDocument.from_html(filing.attachments[1].download())
    text = document.text
    assert "A Quiet Place, Mission Impossible, Scream, Teenage Mutant Ninja Turtles and PAW Patrol" in text
    print(text)


def test_document_get_markdown():
    """Render mark from a document"""
    filing = Filing(company='Paramount Global', cik=813828, form='8-K', filing_date='2024-04-29',
                    accession_no='0000813828-24-000018')
    """ """
    document:HtmlDocument = HtmlDocument.from_html(filing.attachments[1].download())
    md = document.markdown
    assert md
    assert "A Quiet Place, Mission Impossible, Scream, Teenage Mutant Ninja Turtles and PAW Patrol" in md
    assert "Leading Paramount’s Business Units" in md


def test_filing_text_for_file_with_fil_extension():
    filing = Filing(form='NSAR-A', filing_date='2016-06-28',
                    company='AMERICAN FUNDS GLOBAL BALANCED FUND', cik=1505612, accession_no='0000051931-16-002553')
    assert "American Funds Global Balanced Fund" in filing.html()
    assert "American Funds Global Balanced Fund" in filing.text()
    assert "American Funds Global Balanced Fund" in filing.markdown()

    filing = Filing(form='NSAR-A', filing_date='2016-09-28', company='Investment Managers Series Trust', cik=1318342,
                    accession_no='0000926877-16-000629')
    assert "A000000 INVESTMENT MANAGERS SERIES TRUST" in filing.html()
    assert "A000000 INVESTMENT MANAGERS SERIES TRUST" in filing.text()


def test_parse_html_with_funny_character():
    # repr was not implemented on Table Block so there was an exception
    filing = Filing(company='WideOpenWest, Inc.', cik=1701051, form='10-K', filing_date='2024-03-13', accession_no='0001558370-24-003047')
    tenk = filing.obj()
    chunked_document:ChunkedDocument = tenk.chunked_document

    item_1a_chunks = list(chunked_document.chunks_for_item("Item 1A"))
    blocks = item_1a_chunks[6]
    result = repr(blocks[0])
    assert result

def test_get_clean_html_from_unusual_filing():
    filing =  Filing(form='NSAR-B', filing_date='2016-12-29', company='Thrivent Cash Management Trust', cik=1300087,
                     accession_no='0001193125-16-805810')
    html = filing.html()
    clean_html = get_clean_html(html)
    assert not clean_html
    markdown = filing.markdown()
    assert markdown


def test_get_text_from_prospectus():
    #Expected xmlns:xbrli for the instance namespace
    # but was xmlns:i="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    filing = Filing(form='485BPOS', filing_date='2024-03-28', company='DELAWARE GROUP EQUITY FUNDS II', cik=27574, accession_no='0001145443-24-000056')
    text = filing.text()
    assert text
    #print(text)
    html_document:Optional[HtmlDocument] = HtmlDocument.from_html(filing.html(), extract_data=True)
    assert html_document.data


def test_parse_html_document_with_issue_decomposing_page_numbers():
    filing = Filing(form='10-Q', filing_date='2024-07-16', company='Global Arena Holding, Inc.', cik=1138724,
           accession_no='0001756125-24-001116')
    text = filing.text()
    assert text



