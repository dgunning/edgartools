from pathlib import Path

"""

from edgar._html import chomp, read_blocks, TableBlock, HtmlBlocks, HtmlBlockConverter, abstract_inline_conversion, \
    table_html_to_df
    """
from rich import print
from markdownify import markdownify
from edgar._html import *

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()


def test_markdown_converter():
    blocks = HtmlBlocks.read(blackrock_8k)
    assert isinstance(blocks, HtmlBlocks)
    assert len(blocks) > 20
    print(blocks[4])
    assert blocks[4].text == "Washington, D.C. 20549"
    print()
    print(blocks)


def test_htmlblock_tables():
    blocks = HtmlBlocks.read(blackrock_8k)
    table_blocks = blocks.tables
    assert all(isinstance(block, TableBlock) for block in table_blocks)
    table = table_blocks[6]
    print()
    print(table)


def test_chomp():
    assert chomp("<b> foo</b>") == ('', '', '<b> foo</b>')
