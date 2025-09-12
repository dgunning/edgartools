
from edgar.files.html import *
from edgar.files.html_documents import fixup_soup, HtmlDocument
from edgar.files.tables import TableProcessor
from pathlib import Path
from edgar import Filing
from rich import print
from edgar.richtools import rich_to_text
from bs4 import BeautifulSoup
import pytest

def get_html(path):
    return Path(path).read_text()

@pytest.mark.fast
def test_parse_html_with_table():
    document = Document.parse(get_html('data/html/OneTable.html'))
    assert len(document.tables) == 1

@pytest.mark.fast
def test_parse_html_with_2tables():
    document = Document.parse(get_html('data/html/TwoTables.html'))
    assert len(document.tables) == 2
    assert len(document.nodes) == 2

@pytest.mark.fast
def test_parse_html_with_table_inside_div():
    document = Document.parse(get_html('data/html/TableInsideDiv.html'))
    assert len(document.tables) == 1
    assert len(document.nodes) == 1

@pytest.mark.fast
def test_parse_html_with_table_inside_div_with_h2():
    content = get_html('data/html/TableInsideDivWithHeader.html')
    document = Document.parse(content)
    assert len(document.tables) == 1
    assert len(document.nodes) == 2
    assert document.nodes[0].content == 'This HTML has a table. This is a header'

@pytest.mark.fast
def test_handle_spans_inside_divs():
    content = """
    <html>
<body>
    <div>
        <span>This is a span</span>
        <span>A second span 2</span>
        <span>And a 3rd</span>
    </div>
</body>
</html>
    """
    document = Document.parse(content)
    assert len(document.nodes) == 1
    assert document.nodes[0].content == 'This is a span A second span 2 And a 3rd'

@pytest.mark.fast
def test_multiple_spans_in_div():
    # Test HTML
    html = """
    <html>
    <body>
        <div>
            <span>This is a span</span>
            <span>A second span 2</span>
            <span>And a 3rd</span>
        </div>
    </body>
    </html>
    """

    # Parse HTML
    soup = BeautifulSoup(html, 'html.parser')
    parser = SECHTMLParser(soup)
    document = parser.parse()

    # Basic document validation
    assert document is not None
    assert len(document.nodes) == 1, "Should have exactly one text block node"

    # Get the text block node
    node = document.nodes[0]

    # Verify node properties
    assert node.type == 'text_block', "Node should be a text block"

    # Verify content includes all spans correctly concatenated
    expected_text = "This is a span A second span 2 And a 3rd"
    assert node.content.strip() == expected_text, f"Expected '{expected_text}' but got '{node.content.strip()}'"

@pytest.mark.fast
def test_spans_with_styling():
    # Test HTML with styled spans
    html = """
    <html>
    <body>
        <div style="text-align: center">
            <span style="font-weight: bold">Bold span</span>
            <span style="font-style: italic">Italic span</span>
            <span style="color: blue">Blue span</span>
        </div>
    </body>
    </html>
    """

    soup = BeautifulSoup(html, 'html.parser')
    parser = SECHTMLParser(soup)
    document = parser.parse()

    assert document is not None
    assert len(document.nodes) == 3

    node = document.nodes[0]
    assert node.type == 'heading'

    # Verify content
    expected_text = "Bold span"
    assert node.content.strip() == expected_text

    # Verify div styling was preserved
    assert node.style.text_align == 'center'

@pytest.mark.fast
def test_mixed_content_spans():
    # Test HTML with mixed content
    html = """
    <html>
    <body>
        <div>
            Text before
            <span>Inside span</span>
            Text between
            <span>Another span</span>
            Text after
        </div>
    </body>
    </html>
    """

    soup = BeautifulSoup(html, 'html.parser')
    parser = SECHTMLParser(soup)
    document = parser.parse()

    assert document is not None
    assert len(document.nodes) == 1

    node = document.nodes[0]
    assert node.type == 'text_block'

    # Verify all content is preserved in correct order
    expected_text = "Text before Inside span Text between Another span Text after"
    assert node.content.strip() == expected_text

@pytest.mark.fast
def test_spans_with_breaks():
    # Test HTML with line breaks between spans
    html = """
    <html>
    <body>
        <div>
            <span>First line</span>
            <br/>
            <span>Second line</span>
            <br/>
            <span>Third line</span>
        </div>
    </body>
    </html>
    """

    soup = BeautifulSoup(html, 'html.parser')
    parser = SECHTMLParser(soup)
    document = parser.parse()

    assert document is not None
    assert len(document.nodes) == 1

    node = document.nodes[0]
    assert node.type == 'text_block'

    # Verify content with line breaks
    expected_text = 'First line \n Second line \n Third line'
    assert node.content.strip() == expected_text

@pytest.mark.fast
def test_parse_correct_setting_of_widths():
    html = Path("data/html/424-DivContainingSpans.html").read_text()
    document = Document.parse(html)
    assert len(document.tables) == 0
    # The bulleted list should have the correct width
    print(document)
    assert len(document.nodes) > 0
    assert document.nodes[0].style.width.value == 456.0
    assert 'Offers to purchase the' in str(document)
    assert 'educational and charitable institutions' in str(document)

@pytest.mark.fast
def test_parse_table_from_nextpoint_filing():
    html_content = Path('data/NextPoint.8K.html').read_text()
    document = Document.parse(html_content)
    tables = document.tables
    assert len(tables) == 8
    print(document)

@pytest.mark.fast
def test_order_of_table_in_document():
    html = Path("data/html/OrderOfTableInDiv.html").read_text()
    document = Document.parse(html)
    print(document)
    assert "2024" in str(document)

@pytest.mark.fast
def test_document_tables():
    html = Path("data/html/Apple.10-Q.html").read_text()
    document = Document.parse(html)

    tables = document.tables
    assert all(table.type == "table" for table in tables)
    revenue_table = tables[17]
    #print(revenue_table.render(160))
    assert revenue_table.metadata['ix_tag'] == 'us-gaap:DisaggregationOfRevenueTableTextBlock'

    for table in document.tables:
        if table.metadata.get('ix_has_table'):
            print(table.metadata.get("ix_tag"))
            print(table.render(160))
            print("-" * 80)

@pytest.mark.fast
def test_document_tables_in_10K():
    html = Path("data/html/Apple.10-K.html").read_text()
    document = Document.parse(html)
    print()
    for table in document.tables:
        if table.metadata.get('ix_has_table'):
            print(table.metadata.get("ix_tag"))
            print(table.render(160))
            print("-" * 80)

@pytest.mark.fast
def test_parse_financial_table_with_two_header_rows():
    html = Path("data/html/AppleIncomeTaxTable.html").read_text()
    document:Document = Document.parse(html)
    # There are nodes in the document
    assert len(document) == 1
    node:DocumentNode = document[0]
    assert node.type == "table"
    header = node.content[0]
    assert header.virtual_columns == 24
    print(document)

@pytest.mark.fast
def test_oracle_10K_document():
    document = Document.parse(Path("data/html/Oracle.10-Q.html").read_text())
    print(document)

@pytest.mark.fast
def test_oracle_randd_table():
    html = Path("data/html/OracleR&DTable.html").read_text()
    document = Document.parse(html)
    print(document)

@pytest.mark.fast
def test_8k_markdown():
    print("")
    document = Document.parse(Path('data/html/Oracle.8-K.html').read_text())
    md = document.to_markdown()
    print(md)

@pytest.mark.fast
def test_document_parse_nextpoint_8k():
    content = Path('data/NextPoint.8K.html').read_text()
    document = Document.parse(content)
    assert document
    tables = document.tables

    print()
    print(document)
    assert 'Effective December' in repr(document)
    assert 'Forward-Looking Statements' in repr(document)
    assert len(tables) > 0
    #assert len(document) > 30

@pytest.mark.fast
def test_financial_table_header_displays_line_breaks():
    html = Path("data/html/AppleRSUTable.html").read_text()
    document:Document = Document.parse(html)
    print(document)
    assert len(document) == 1
    table = document.nodes[0]
    row = table.content[1]
    cell = row.cells[1]
    assert cell.content == 'Number of\nRSUs\n(in thousands)'

@pytest.mark.fast
def test_table_metadata():
    html = Path("data/html/AppleRSUTable.html").read_text()
    document: Document = Document.parse(html)
    table = document.nodes[0]

@pytest.mark.fast
def test_table_processor_process_table():
    document = Document.parse(Path('data/html/AppleRSUTable.html').read_text())
    table_node = document.nodes[0]
    assert table_node
    processed_table = TableProcessor.process_table(table_node)
    assert processed_table
    assert len(processed_table.data_rows) == 5
    assert processed_table.data_rows[0][0].startswith("Balance")
    table = table_node.render(160)
    assert table
    print(table)

@pytest.mark.fast
def test_read_html_document_wih_financials():
    content = Path("data/html/BuckleInc.8-K.EX99.1.html").read_text()
    document = Document.parse(content)
    assert document
    print()
    print(document)

@pytest.mark.fast
def test_render_paragraph_block_with_line_breaks():
    content = Path("data/html/BuckleInc.8-K.EX99.1.html").read_text()
    document = Document.parse(content)
    block = document.nodes[4]

    text = block.render(200)
    print()
    print(text)

@pytest.mark.fast
def test_document_parses_table_inside_ix_elements():
    html = Path("data/html/TableInsideIxElement.html").read_text()
    document = Document.parse(html)
    md = document.to_markdown()
    nodes = document.nodes

    tables = document.tables
    assert len(tables) == 1
    assert len(nodes) == 2
    table = tables[0]
    #md = document.to_markdown()
    #print()
    #print(md)

@pytest.mark.fast
def test_document_markdown_headings_parsed_correctly():
    html = Path("data/NextPoint.8K.html").read_text()
    document = Document.parse(html)
    md = document.to_markdown()
    print()
    print(md)
    #assert "# SECURITIES AND EXCHANGE COMMISSION" in md

@pytest.mark.fast
def test_document_parsed_from_plain_text_returns_plain_text():
    html = """
    This document is just test
    """
    root = HtmlDocument.get_root(html)
    print("ROOT:")
    print(root)
    print('Body: ', root.find('body'))
    parser = SECHTMLParser(root)
    doc = parser.parse()
    print("Parsed Document:")
    document = Document.parse(html)
    #assert document is not None, "Document should not be None"

@pytest.mark.fast
def test_document_from_filing_with_plain_text_filing_document():
    f = Filing(form='SC 13G/A', filing_date='2024-11-25', company='Bridgeline Digital, Inc.', cik=1378590, accession_no='0001968076-24-000022')
    html = f.html()
    assert html

@pytest.mark.fast
def test_text_in_spans():
    html="""<p id="part_ii_or_information"><span>PART II. OTHE</span><span>R INFORMATION</span></p>"""
    document = Document.parse(html)
    assert document.nodes[0].content == "PART II. OTHER INFORMATION"

    html = """<div><p style="font-size:10pt;margin-top:0;font-family:Times New Roman;margin-bottom:0;text-align:justify;" id="part_i_financial_information"><span style="color:#000000;white-space:pre-wrap;font-weight:bold;font-size:10pt;font-family:'Calibri',sans-serif;min-width:fit-content;">PART I. FINANCI</span><span style="color:#000000;white-space:pre-wrap;font-weight:bold;font-size:10pt;font-family:'Calibri',sans-serif;min-width:fit-content;">AL INFORMATION</span></p></div>"""
    document = Document.parse(html)
    assert document.nodes[0].content == "PART I. FINANCIAL INFORMATION"

@pytest.mark.fast
def test_document_to_text():
    document = Document.parse(
        """
        <html>
        <body>
        <p>Basic Document</p>
        <body>
        </html>
        """
    )
    text = rich_to_text(document)
    assert text == "Basic Document\n"
    print(text)

@pytest.mark.fast
def test_render_paragraph():
    html = Path("data/html/424-Snippet.html").read_text()
    document = Document.parse(html)
    assert not document.empty()
    print()
    paragraph = document.nodes[0]
    print(paragraph.content)

@pytest.mark.fast
def test_get_text_from_filing_with_no_body_tag():
    filing = Filing(form='TA-1/A', filing_date='2024-04-17', company='PEAR TREE ADVISORS INC /TA',
                    cik=949738, accession_no='0000949738-24-000005')
    html = filing.html()
    assert html
    text = filing.text()
    assert text

@pytest.mark.fast
def test_parse_document_within_just_paragraph_tags():
    content = Path('data/html/BeyondAir.html').read_text()
    document = Document.parse(content)
    print()
    print(document)

@pytest.mark.fast
def test_table_of_content_for_10K():
    content = Path('data/html/Apple.10-K.html').read_text()
    document = Document.parse(content)
    print()
    print(document)
    tables = document.tables
    #toc = document.table_of_contents()
    #print(toc)

@pytest.mark.fast
def test_parse_and_identify_headings():
    content = Path('data/html/Headings-Snippet.html').read_text()
    document = Document.parse(content)
    headings = document.headings
    assert len(headings) == 3
    assert headings[0].content == "PART I"
    assert headings[1].content == "Item 1. Business"
    print()
    print(document)

@pytest.mark.fast
def test_html_from_old_filings_is_none():
    f = Filing(form='8-K', filing_date='1998-01-05', company='YAHOO INC', cik=1011006, accession_no='0001047469-98-000122')
    text = f.text()
    assert text
    html = f.html()
    assert not html

@pytest.mark.fast
def test_get_html_problem_filing():
    filing = Filing(form='497K',
                    filing_date='2024-12-30',
                    company='VOYAGEUR MUTUAL FUNDS',
                    cik=906236,
                    accession_no='0001206774-24-001226')
    text = filing.text()
    assert text
    print(text)

@pytest.mark.fast
def test_parse_html_document_with_pre():
    content = Path('data/html/document-with-pre.html').read_text()
    document = Document.parse(content)
    assert document

@pytest.mark.fast
def test_pre_tag_handling():
    # Test case 1: Pre with plain text
    html1 = "<pre>Simple text content</pre>"
    soup1 = BeautifulSoup(html1, 'html.parser')
    fixup_soup(soup1)
    div1 = soup1.find('div')
    assert div1 is not None
    assert div1.get_text().strip() == 'Simple text content'
    
    # Test case 2: Pre with mixed content
    html2 = "<pre>Text before <b>bold text</b> and after</pre>"
    soup2 = BeautifulSoup(html2, 'html.parser')
    fixup_soup(soup2)
    div2 = soup2.find('div')
    assert div2 is not None
    assert div2.find('b') is not None, "Bold tag was lost"
    assert div2.find('b').get_text() == 'bold text'
    assert div2.get_text().strip() == 'Text before bold text and after'
    
    # Test case 3: Pre with single styled div
    html3 = '''<pre><div style="TEXT-ALIGN: right"><font style="FONT-SIZE: 9pt; FONT-FAMILY: Times New Roman">to Form 8-K dated 1/7/08</font></div></pre>'''
    soup3 = BeautifulSoup(html3, 'html.parser')
    fixup_soup(soup3)
    div3 = soup3.find('div')
    assert div3 is not None
    # Get the styled div (either the outer div if style was moved up, or inner div)
    styled_div = div3.find('div', style='TEXT-ALIGN: right') or div3
    assert styled_div.get('style') == 'TEXT-ALIGN: right'
    font = styled_div.find('font')
    assert font.get('style') == 'FONT-SIZE: 9pt; FONT-FAMILY: Times New Roman'
    
    # Test case 4: Pre with multiple divs
    html4 = '''<pre><div>First div</div><div>Second div</div></pre>'''
    soup4 = BeautifulSoup(html4, 'html.parser')
    fixup_soup(soup4)
    outer_div = soup4.find('div')
    assert outer_div is not None
    # Get direct child divs of the outer div
    inner_divs = outer_div.find_all('div', recursive=False)
    assert len(inner_divs) == 2
    assert inner_divs[0].get_text() == 'First div'
    assert inner_divs[1].get_text() == 'Second div'
    
    # Test case 5: Pre with other HTML elements
    html5 = '''<pre><p>A paragraph</p><span>A span</span><b>Bold text</b></pre>'''
    soup5 = BeautifulSoup(html5, 'html.parser')
    fixup_soup(soup5)
    div5 = soup5.find('div')
    assert div5 is not None
    assert div5.find('p').get_text() == 'A paragraph'
    assert div5.find('span').get_text() == 'A span'
    assert div5.find('b').get_text() == 'Bold text'