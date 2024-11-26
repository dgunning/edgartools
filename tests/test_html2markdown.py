

from edgar.files.html import *
from pathlib import Path
from edgar import Company, Filing
from rich import print


def test_parse_markdown():
    html_content = Path('data/NextPoint.8K.html').read_text()
    parser = SECHTMLParser(html_content)
    document = parser.parse()

    # Render to markdown
    renderer = MarkdownRenderer(document)
    markdown_content = renderer.render()
    print(markdown_content)


def test_filing_to_markdown():
    filing = Filing(company='Apple Inc.', cik=320193, form='8-K', filing_date='2024-10-31', accession_no='0000320193-24-000120')
    Path('data/Apple.8-K.md').write_text(filing.markdown())

    filing = Company("AAPL").latest("10-K")
    #filing.open()
    print(str(filing))
    html = filing.html()
    parser = SECHTMLParser(html)
    document = parser.parse()
    md = to_markdown(filing.html())
    Path('data/Apple.10-K.md').write_text(md)
    #print(Markdown(md))
    #print(md)
    renderer = MarkdownRenderer(document)
    print(renderer.render_to_text())

def test_apple_tenq_rendering():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-Q', filing_date='2024-08-02', accession_no='0000320193-24-000081')
    html = filing.html()
    parser = SECHTMLParser(html)
    document = parser.parse()
    renderer = MarkdownRenderer(document)
    md = renderer.render()
    Path('data/Apple.10-Q.md').write_text(md)


def test_parse_financial_table_with_two_header_rows():
    html = Path("data/html/AppleIncomeTaxTable.html").read_text()
    #print(html)
    parser = SECHTMLParser(html)
    document:Document = Document.parse(html)
    # There is nodes in the document
    assert len(document) == 1
    # Get the node
    node:DocumentNode = document[0]
    assert node.type == "table"
    header = node.content[0]
    #assert header.virtual_columns == 24


    print(document)



def test_8k_markdown():
    print("")
    filing = Filing(company='ORACLE CORP', cik=1341439, form='8-K', filing_date='2024-11-18', accession_no='0001193125-24-260986')
    html = filing.html()
    parser = SECHTMLParser(html)
    document = parser.parse()
    renderer = MarkdownRenderer(document)
    md = renderer.render()
    print(md)


def test_document_parse():
    document = Document.parse(Path('data/NextPoint.8K.html').read_text())
    assert document
    assert len(document) == 32
    print()
    print(document)

def test_financial_table_header_displays_line_breaks():
    html = Path("data/html/AppleRSUTable.html").read_text()
    document:Document = Document.parse(html)
    print(document)
    assert len(document) == 1
    table = document.nodes[0]
    #print(table)
    row = table.content[1]
    cell = row.cells[1]
    #print(cell)
    assert cell.content == 'Number of\nRSUs\n(in thousands)'
    #print(row)



def test_document_repr():
    html_content = Path('data/NextPoint.8K.html').read_text()
    parser = SECHTMLParser(html_content)
    document = parser.parse()
    print()
    print(document)


def test_read_html_document_wih_financials():
    f = Filing(company='BUCKLE INC', cik=885245, form='8-K', filing_date='2024-11-22', accession_no='0000885245-24-000103')
    print()
    attachment = f.attachments[1]
    html = attachment.download()
    parser = SECHTMLParser(html)
    document = parser.parse()
    print(document)