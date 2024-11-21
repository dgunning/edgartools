from edgar.html2markdown import *
from pathlib import Path
from edgar import Company, Filing
from rich.markdown import Markdown
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
    #Path('data/Apple.8-K.md').write_text(filing.markdown())

    filing = Company("AAPL").latest("10-K")
    print(str(filing))
    html = filing.html()
    parser = SECHTMLParser(html)
    document = parser.parse()
    md = to_markdown(filing.html())
    #Path('data/Apple.10-K.md').write_text(md)
    #print(Markdown(md))
    print(md)

