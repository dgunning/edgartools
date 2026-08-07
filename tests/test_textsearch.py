import re
from pathlib import Path
from edgar.search.textsearch import numeric_shape, preprocess, convert_items_to_tokens, RegexSearch, BM25Search
from rich import print
from edgar import Filing
from edgar.search import SearchResults
from edgar.files.html_documents import html_to_markdown
import pytest

blackrock_8k = Path('data/form8K.Blackrock.html').read_text()
document_sections = re.split(r"\n\s*\n", html_to_markdown(blackrock_8k))


@pytest.mark.fast
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

@pytest.mark.fast
def test_regex_search_preprocess():
    assert RegexSearch.preprocess("Item&#160;5.02") == "Item 5.02"

@pytest.mark.fast
def test_regex_search():
    regex_search: RegexSearch = RegexSearch(document_sections)
    search_results = regex_search.search(r"Item\s5.02")
    print()
    print(search_results)
    assert len(search_results) > 0

@pytest.mark.fast
def test_numeric_shape():
    tokens = ["21", "34.4", "and", "10,030,000"]
    shaped_tokens = numeric_shape(tokens)
    assert shaped_tokens == ['xx', 'xx.x', 'and', 'xx,xxx,xxx']
    print(shaped_tokens)
    # percentages
    tokens = ["21%", "34.4%", "0.24%", "and", "10,030,000"]
    shaped_tokens = numeric_shape(tokens)
    assert shaped_tokens == ['xx%', 'xx.x%', 'x.xx%', 'and', 'xx,xxx,xxx']

@pytest.mark.fast
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

@pytest.mark.fast
def test_convert_items_to_tokens():
    text = "item 0 and Item 1 and item 2 and item 4.01 and Item 1A"
    item_text = convert_items_to_tokens(text)
    print(item_text)

@pytest.mark.fast
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

@pytest.mark.fast
def test_search_works_in_fwp_prospectus():
    filing = Filing(form='FWP', filing_date='2023-03-30', company='CITIGROUP INC', cik=831001, accession_no='0000950103-23-004912')
    results = filing.search("Pricing Supplement", regex=True)
    assert len(results) > 0

@pytest.mark.fast
def test_search_results_as_json():
    filing = Filing(company='NVIDIA CORP', cik=1045810, form='10-K', filing_date='2023-02-24',
                    accession_no='0001045810-23-000017')
    results:SearchResults = filing.search("GPU")
    json_results = results.json()
    assert isinstance(json_results, dict)
    assert len(json_results['sections']) > 0
    assert json_results['query'] == "GPU"


# --- Match highlighting in rendered output (issue #765 / edgartools-gnzy) ---

# Rich emits these SGR sequences for the "bold red" highlight style.
_BOLD_RED = ("\x1b[1;31m", "\x1b[31;1m")


def _rendered_has_highlight(results: SearchResults) -> bool:
    """Render the SearchResults to ANSI and report whether any match is bold-red."""
    from rich.console import Console
    console = Console(force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(results)
    out = capture.get()
    return any(code in out for code in _BOLD_RED)


@pytest.mark.fast
def test_bm25_search_highlights_matches():
    bm25 = BM25Search(document_sections)
    results = bm25.search("financial")
    assert len(results) > 0
    assert results._highlight_pattern is not None
    assert _rendered_has_highlight(results)


@pytest.mark.fast
def test_regex_search_highlights_matches():
    regex_search = RegexSearch(document_sections)
    results = regex_search.search(r"Item\s5.02")
    assert len(results) > 0
    assert results._regex is True
    assert _rendered_has_highlight(results)


@pytest.mark.fast
def test_bm25_highlight_matches_substrings_case_insensitively():
    # "repurchase" should also light up "Repurchases"/"repurchased".
    sections = ["The company announced Repurchases and later repurchased more shares."]
    results = BM25Search(sections).search("repurchase")
    pattern = results._highlight_pattern
    assert pattern is not None
    assert len(pattern.findall(sections[0])) == 2


@pytest.mark.fast
def test_stopword_only_query_produces_no_highlight_pattern():
    # All-stopword query must not crash and must not build a (match-everything) pattern.
    results = SearchResults(query="the of and", sections=[])
    assert results._highlight_pattern is None
    assert _rendered_has_highlight(results) is False


@pytest.mark.fast
def test_invalid_regex_query_does_not_crash_highlighting():
    results = SearchResults(query="[", sections=[], regex=True)
    assert results._highlight_pattern is None  # invalid regex -> no highlight, no error


@pytest.mark.fast
def test_table_cells_are_highlighted():
    # Table sections (markdown starting with "|  |") should highlight matched cells too.
    table_md = "|  | Item | Amount |\n| Total repurchase | 100 |"
    results = SearchResults(query="repurchase",
                            sections=[],
                            tables=True)
    from rich.console import Console
    from edgar._markdown import convert_table
    table = convert_table(table_md, cell_highlighter=results._highlight)
    console = Console(force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(table)
    out = capture.get()
    assert any(code in out for code in _BOLD_RED)
