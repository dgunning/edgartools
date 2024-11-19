from edgar.html2markdown import *
from pathlib import Path


def test_parse_markdown():
    html_content = Path('data/NextPoint.8K.html').read_text()
    parser = SECHTMLParser(html_content)
    document = parser.parse()

    # Render to markdown
    renderer = MarkdownRenderer(document)
    markdown_content = renderer.render()
    print(markdown_content)
