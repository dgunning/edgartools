import re
from pathlib import Path

from edgar.search import BM25SearchIndex
from edgar.search import numeric_shape, preprocess, convert_items_to_tokens

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()


def test_create_bm25_search_index():
    bm25: BM25SearchIndex = BM25SearchIndex(re.split(r"\n\s*\n", blackrock_8k))
    assert bm25


def test_numeric_shape():
    tokens = ["21", "34.4", "and", "10,030,000"]
    shaped_tokens = numeric_shape(tokens)
    assert shaped_tokens == ['xx', 'xx.x', 'and', 'xx,xxx,xxx']
    print(shaped_tokens)
    # percentages
    tokens = ["21%", "34.4%", "0.24%", "and", "10,030,000"]
    shaped_tokens = numeric_shape(tokens)
    assert shaped_tokens == ['xx%', 'xx.x%', 'x.xx%', 'and', 'xx,xxx,xxx']


def test_preprocess_text():
    text = """International revenues accounted for approximately 21%, 34% and 29% of our |
           total revenues in 2017, 2016 and 2015, respectively"""
    post_text = preprocess(text)
    print(post_text)
    assert 'xx%' in post_text
    assert 'international' in post_text
    assert "|" not in post_text

    text = """
    item 4.01 approximately 21%, 34% and 29%
    Item 1
    """
    post_text = preprocess(text)
    print(post_text)
    assert "item_4.01" in post_text
    assert "xx%" in post_text


def test_convert_items_to_tokens():
    text = "item 0 and Item 1 and item 2 and item 4.01 and Item 1A"
    item_text = convert_items_to_tokens(text)
    print(item_text)