import re
from pathlib import Path
from edgar.search import numeric_shape, preprocess, convert_items_to_tokens, RegexSearch, BM25Search
from rich import print
from markdownify import markdownify

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()
document_sections = re.split(r"\n\s*\n", markdownify(blackrock_8k))


def test_create_bm25_search_index():
    bm25: BM25Search = BM25Search(document_sections)
    assert bm25
    search_results = bm25.search("financial")
    assert len(search_results) == 2

    # Search for item
    print()
    results = bm25.search("Item 5.02")
    print(results)
    assert len(results) > 0

    results = bm25.search("Item 9.02")
    print(results)
    assert len(results) > 0


def test_regex_search_preprocess():
    assert RegexSearch.preprocess("Item&#160;5.02") == "Item 5.02"


def test_regex_search():
    regex_search: RegexSearch = RegexSearch(document_sections)
    search_results = regex_search.search(r"Item\s5.02")
    print()
    print(search_results)
    assert len(search_results) > 0


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
    assert "4.01" in post_text and "item" in post_text
    assert "xx%" in post_text


def test_convert_items_to_tokens():
    text = "item 0 and Item 1 and item 2 and item 4.01 and Item 1A"
    item_text = convert_items_to_tokens(text)
    print(item_text)
