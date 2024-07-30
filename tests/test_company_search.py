import pytest

from edgar.entities import CompanySearchIndex, CompanySearchResults


@pytest.fixture(scope="module")
def company_search_index():
    return CompanySearchIndex()


def test_search_for_company_exact_ticker_match(company_search_index):
    results: CompanySearchResults = company_search_index.search("AAPL")
    print(results)
    assert len(results) == 1


def test_search_for_company_partial_ticker_match(company_search_index):
    results: CompanySearchResults = company_search_index.search("TE")
    assert len(results) > 1
    assert all(ticker.startswith("TE") for ticker in results.tickers)


def test_search_for_company_name_and_ticker_partial_match(company_search_index):
    results: CompanySearchResults = company_search_index.search("ORC")
    assert len(results) >= 1
    assert {'ORC', 'ORCL'} & set(results.tickers)


def test_search_exact_company_name_match(company_search_index):
    results: CompanySearchResults = company_search_index.search("ORACLE CORP")
    assert len(results) == 1
    assert results.tickers[0] == "ORCL"


def test_search_with_no_matches(company_search_index):
    results: CompanySearchResults = company_search_index.search("NOT A REAL COMPANY")
    assert len(results) == 0


def test_get_company_from_data_search_results(company_search_index):
    results: CompanySearchResults = company_search_index.search("ORCL")
    company = results[0]
    assert company
    assert company.name == "ORACLE CORP"
    assert company.tickers == ["ORCL"]
    assert company.cik == 1341439


def test_get_company_from_search_results_not_found(company_search_index):
    results: CompanySearchResults = company_search_index.search("ORCL")
    assert not results[-1]
    assert not results[100]
