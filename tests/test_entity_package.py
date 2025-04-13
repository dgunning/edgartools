import pytest
from edgar.entity import (
    Entity,
    Company,
    Fund,
    SecFiler,
    get_entity,
    get_company,
    get_fund,
    find_company,
    get_company_tickers,
    get_icon_from_ticker,
    get_entity_submissions,
    get_ticker_to_cik_lookup,
    get_cik_lookup_data,
    CompanySearchResults,
    NoCompanyFactsFound
)


def test_entity_class_hierarchy():
    """Test the entity class hierarchy"""
    entity = Entity("0000320193")  # Apple
    company = Company("AAPL")
    
    # Test inheritance
    assert isinstance(entity, Entity)
    assert isinstance(entity, SecFiler)
    assert isinstance(company, Company)
    assert isinstance(company, Entity)
    assert isinstance(company, SecFiler)


def test_functions_exist():
    """Test that the functions we reimplemented exist"""
    # Test that the functions exist
    assert callable(get_entity)
    assert callable(get_company)
    assert callable(get_fund)
    assert callable(find_company)
    assert callable(get_company_tickers)
    assert callable(get_icon_from_ticker)
    assert callable(get_entity_submissions)
    assert callable(get_ticker_to_cik_lookup)
    assert callable(get_cik_lookup_data)


def test_company_search():
    """Test that company search works"""
    results = find_company("Apple")
    assert isinstance(results, CompanySearchResults)
    assert len(results) > 0
    # Assert "AAPL" is in the results
    assert "AAPL" in results.tickers


def test_get_company():
    """Test that get_company works"""
    company = get_company("AAPL")
    assert isinstance(company, Entity)
    # Company might be a function wrapper, so we check the data attribute
    assert company.cik == 320193  # Apple's CIK
    # The data attribute should have the company name
    if hasattr(company, 'data'):
        assert hasattr(company.data, 'name')
        assert company.data.name.upper().startswith("APPLE")