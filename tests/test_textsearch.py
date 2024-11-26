import re
from pathlib import Path
from edgar.search.textsearch import numeric_shape, preprocess, convert_items_to_tokens, RegexSearch, BM25Search
from rich import print
from edgar import Filing
from edgar.search import SearchResults
from edgar.files.html_documents import html_to_markdown

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()
document_sections = re.split(r"\n\s*\n", html_to_markdown(blackrock_8k))


def test_create_bm25_search_index():
    bm25: BM25Search = BM25Search(document_sections)
    assert bm25
    search_results = bm25.search("financial")
    assert len(search_results) == 3

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


def test_search_sections():
    print()
    filing = Filing(company='NVIDIA CORP', cik=1045810, form='10-K', filing_date='2023-02-24',
                    accession_no='0001045810-23-000017')

    results:SearchResults = filing.search("GPU")
    assert len(results) > 0

    # Get the original locations in the document
    locations = [section.loc for section in results.sections]
    # assert that locations are non contiguous
    assert locations != list(range(min(locations), max(locations) + 1))
    # assert that locations are sorted
    assert locations == sorted(locations)

    print(results)

    assert 'GPU' in results[0].doc

    # search for a term that's not there
    results: SearchResults = filing.search("NOTTHERE")
    assert len(results) == 0
    print(results)


def test_search_works_in_fwp_prospectus():
    filing = Filing(form='FWP', filing_date='2023-03-30', company='CITIGROUP INC', cik=831001, accession_no='0000950103-23-004912')
    results = filing.search("Pricing Supplement", regex=True)
    assert len(results) > 0


def test_search_results_as_json():
    filing = Filing(company='NVIDIA CORP', cik=1045810, form='10-K', filing_date='2023-02-24',
                    accession_no='0001045810-23-000017')
    results:SearchResults = filing.search("GPU")
    json_results = results.json()
    assert isinstance(json_results, dict)
    assert len(json_results['sections']) > 0
    assert json_results['query'] == "GPU"
