from edgar.search import BM25SearchIndex
from pathlib import Path
from edgar._html import HtmlBlocks

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()


def test_create_bm25_search_index():
    blocks: HtmlBlocks = HtmlBlocks.read(blackrock_8k)
    bm25: BM25SearchIndex = BM25SearchIndex(blocks.blocks, text_fn=lambda b: str(b))
    assert bm25
    assert len(bm25) == len(blocks)


def test_search_with_bm25_index():
    blocks: HtmlBlocks = HtmlBlocks.read(blackrock_8k)
    bm25: BM25SearchIndex = BM25SearchIndex(blocks.blocks, text_fn=lambda b: str(b))
    results = bm25.search("Financial Emerging common stock")
    print(results)
