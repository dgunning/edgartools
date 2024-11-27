
from edgar.files.html import *
from edgar.files.tables import TableProcessor
from edgar.files.markdown import to_markdown, MarkdownRenderer
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

def test_document_tables():
    html = Path("data/html/Apple.10-Q.html").read_text()
    document = Document.parse(html)

    tables = document.tables
    assert all(table.type == "table" for table in tables)


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

def test_oracle_10K_document():
    document = Document.parse(Path("data/html/Oracle.10-Q.html").read_text())
    print(document)

def test_oracle_randd_table():
    html = Path("data/html/OracleR&DTable.html").read_text()
    document = Document.parse(html)
    print(document)


def test_8k_markdown():
    print("")
    document = Document.parse(Path('data/html/Oracle.8-K.html').read_text())
    md = document.to_markdown()
    print(md)


def test_document_parse_nextpoint_8k():
    document = Document.parse(Path('data/NextPoint.8K.html').read_text())
    assert document
    assert len(document) == 34
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

def test_table_processor_process_table():
    document = Document.parse(Path('data/html/AppleRSUTable.html').read_text())
    table_node = document.nodes[0]
    assert table_node
    processed_table = TableProcessor.process_table(table_node)
    assert processed_table
    assert len(processed_table.data_rows) == 5
    assert processed_table.data_rows[0][0].startswith("Balance")
    table = document._render_table(table_node)
    assert table
    print(table)


def test_read_html_document_wih_financials():
    f = Filing(company='BUCKLE INC', cik=885245, form='8-K', filing_date='2024-11-22', accession_no='0000885245-24-000103')
    print()
    attachment = f.attachments[1]
    html = attachment.download()
    parser = SECHTMLParser(html)
    document = parser.parse()
    print(document)


def test_document_parses_table_inside_ix_elements():
    html = Path("data/html/TableInsideIxElement.html").read_text()
    document = Document.parse(html)
    md = document.to_markdown()
    nodes = document.nodes
    assert len(nodes) == 1
    tables = document.tables
    assert len(tables) == 1
    table = tables[0]
    assert len(table.rows) == 7
    #md = document.to_markdown()
    #print()
    #print(md)

def test_document_markdown_headings_parsed_correctly():
    html = Path("data/NextPoint.8K.html").read_text()
    document = Document.parse(html)
    md = document.to_markdown()
    print()
    print(md)
    assert "# SECURITIES AND EXCHANGE COMMISSION" in md


def test_document_parsed_from_plain_text_returns_plain_text():
    html = """
    This document is just test
    """
    document = Document.parse(html)
    assert document
    assert len(document) == 1
    assert document[0].type == "paragraph"
    assert document[0].content == html.strip()

def test_document_from_filing_with_plain_text_filing_document():
    f = Filing(form='SC 13G/A', filing_date='2024-11-25', company='Bridgeline Digital, Inc.', cik=1378590, accession_no='0001968076-24-000022')
    text = f.html()
    document = Document.parse(text)
    assert document
    assert len(document) == 1
    assert document[0].type == "paragraph"