import pytest
import pyarrow as pa


# Assuming the FastSearch class and related functions are in a file named fast_search.py
from edgar.search.datasearch import FastSearch, create_search_index, search


@pytest.fixture
def sample_data():
    return pa.table({
        'cik': [1, 2, 3, 4, 5],
        'ticker': ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'FB'],
        'name': ['Apple Inc.', 'Alphabet Inc.', 'Microsoft Corporation', 'Amazon.com, Inc.', 'Facebook, Inc.']
    })


@pytest.fixture
def company_ticker_preprocess():
    def preprocess(text: str) -> str:
        text = FastSearch._default_preprocess(text)
        common_terms = ['llc', 'inc', 'corp', 'ltd', 'limited', 'company']
        return ' '.join(word for word in text.split() if word not in common_terms)

    return preprocess


@pytest.fixture
def company_ticker_score():
    def score(query: str, value: str, column: str) -> float:
        query = query.upper()
        value = value.upper()

        if len(query) <= 5 and column == 'ticker':
            if query == value:
                return 100
            elif value.startswith(query):
                return 90 + (10 * len(query) / len(value))
            else:
                return 0
        else:
            return FastSearch._default_calculate_score(query, value)

    return score


@pytest.fixture
def company_index(sample_data, company_ticker_preprocess, company_ticker_score):
    return create_search_index(
        sample_data,
        columns=['ticker', 'name'],
        preprocess_func=company_ticker_preprocess,
        score_func=company_ticker_score
    )


def test_exact_ticker_match(company_index):
    results = search(company_index, 'AAPL')
    assert len(results) > 0
    assert results[0]['ticker'] == 'AAPL'
    assert results[0]['score'] == 100  # Perfect score for exact match


def test_partial_ticker_match(company_index):
    results = search(company_index, 'AMZ')
    assert len(results) > 0
    assert results[0]['ticker'] == 'AMZN'
    assert results[0]['score'] > 90  # High score for partial match


def test_company_name_match(company_index):
    results = search(company_index, 'Microsoft')
    assert len(results) > 0
    assert results[0]['name'] == 'Microsoft Corporation'


def test_no_match(company_index):
    results = search(company_index, 'XYZ123')
    assert len(results) == 0


def test_multiple_matches(company_index):
    results = search(company_index, 'A', top_n=3)
    assert len(results) == 2
    tickers = [r['ticker'] for r in results]
    assert 'AAPL' in tickers
    assert 'AMZN' in tickers


def test_case_insensitivity(company_index):
    results_upper = search(company_index, 'APPLE')
    results_lower = search(company_index, 'apple')
    assert results_upper == results_lower


def test_special_characters(company_index):
    results = search(company_index, 'Amazon.com')
    assert len(results) > 0
    assert results[0]['name'] == 'Amazon.com, Inc.'


def test_threshold(company_index):
    results = search(company_index, 'A')
    assert all(r['score'] >= 90 for r in results)


def test_cik_returned(company_index):
    results = search(company_index, 'AAPL')
    assert results[0]['cik'] == 1  # CIK should be 1 for AAPL in our sample data