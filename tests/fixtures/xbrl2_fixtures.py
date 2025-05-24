"""
XBRL2 test fixtures for edgartools.

This module provides pytest fixtures for testing the XBRL2 implementation.
Fixtures are organized to optimize test performance while providing
comprehensive coverage of different company types, time periods, and XBRL features.
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from edgar import Company, Filing
from edgar.xbrl import XBRL

# Base paths
FIXTURE_DIR = Path("tests/fixtures/xbrl2")
DATA_DIR = Path("data/xbrl/datafiles")


# ===== Company Fixtures =====

@pytest.fixture(scope="session")
def aapl_10k_2023():
    """Latest annual report for Apple (2023)."""
    # Try data directory first (existing tests may expect this)
    data_dir = DATA_DIR / "aapl"
    if data_dir.exists():
        return XBRL.from_directory(data_dir)
    
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "aapl/10k_2023"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    # Fallback to original Apple files if available
    alternate_dir = FIXTURE_DIR / "aapl"
    if alternate_dir.exists() and any(alternate_dir.iterdir()):
        # Look for XSD file at the top level
        xsd_files = list(alternate_dir.glob("*.xsd"))
        if xsd_files:
            return XBRL.from_directory(alternate_dir)
    
    # If nothing else works, skip the test
    pytest.skip("Apple 2023 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def aapl_10k_2010():
    """Historical annual report for Apple (2010)."""
    fixture_dir = FIXTURE_DIR / "aapl/10k_2010"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Apple 2010 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def aapl_10q_2023():
    """Latest quarterly report for Apple (2023)."""
    fixture_dir = FIXTURE_DIR / "aapl/10q_2023"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Apple 2023 10-Q fixture not available")
    return None


@pytest.fixture(scope="session")
def msft_10k_2024():
    """Latest annual report for Microsoft (2024)."""
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "msft/10k_2024" 
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        xb = XBRL.from_directory(fixture_dir)
        return xb


@pytest.fixture(scope="session")
def msft_10k_2015():
    """Historical Microsoft filing from 2015."""
    fixture_dir = FIXTURE_DIR / "msft/10k_2015"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Microsoft 2015 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def nflx_10k_2010():
    """Historical Netflix filing from 2010."""
    # Try data directory first
    data_dir = DATA_DIR / "nflx/2010"
    if data_dir.exists():
        return XBRL.from_directory(data_dir)
    
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "nflx/10k_2010"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Netflix 2010 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def nflx_10k_2024():
    """Recent Netflix filing from 2024."""
    # Try data directory first
    data_dir = DATA_DIR / "nflx/2024"
    if data_dir.exists():
        return XBRL.from_directory(data_dir)
    
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "nflx/10k_2024"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Netflix 2024 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def nflx_10q_2024():
    """Recent Netflix quarterly filing from 2024."""
    fixture_dir = FIXTURE_DIR / "nflx/10q_2024"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Netflix 2024 10-Q fixture not available")
    return None


@pytest.fixture(scope="session")
def jpm_10k_2024():
    """JPMorgan 10-K from 2024."""

    fixture_dir = FIXTURE_DIR / "jpm/10k_2024"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)


@pytest.fixture(scope="session")
def jpm_10k_2013():
    """Historical JPMorgan 10-K from 2013."""
    fixture_dir = FIXTURE_DIR / "jpm/10k_2013"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("JPMorgan 2013 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def ko_10k_2024():
    """Coca-Cola 10-K from 2024."""
    fixture_dir = FIXTURE_DIR / "ko/10k_2024"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Coca-Cola 2024 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def ko_10k_2012():
    """Historical Coca-Cola 10-K from 2012."""
    fixture_dir = FIXTURE_DIR / "ko/10k_2012"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Coca-Cola 2012 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def unp_10k_2012():
    """Union Pacific from 2012 - represents older filing format."""
    # Try data directory first
    data_dir = DATA_DIR / "unp"
    if data_dir.exists():
        return XBRL.from_directory(data_dir)
    
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "unp"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Union Pacific 2012 10-K fixture not available")
    return None


@pytest.fixture(scope="session")
def tsla_10k_2024():
    """Tesla 10-K from 2024."""
    # Try data directory first
    data_dir = DATA_DIR / "tsla"
    if data_dir.exists():
        return XBRL.from_directory(data_dir)
    
    # Then try fixture directory
    fixture_dir = FIXTURE_DIR / "tsla"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Tesla 2024 10-K fixture not available")
    return None


# ===== Live Data Fixtures =====

@pytest.fixture(scope="session")
def jpm_latest_10k():
    """Latest JPMorgan 10-K, fetched from EDGAR."""
    filing = Filing(company='JPMORGAN CHASE & CO', cik=19617, form='10-K', 
                   filing_date='2024-02-27', accession_no='0000019617-24-000126')
    return XBRL.from_filing(filing)


@pytest.fixture(scope="session")
def comcast_latest_10k():
    """Latest Comcast 10-K, fetched from EDGAR."""
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', 
                   filing_date='2024-01-31', accession_no='0001166691-24-000011')
    return XBRL.from_filing(filing)


# ===== Special Case Fixtures =====

@pytest.fixture(scope="session")
def complex_segment_statement():
    """Company with complex segment reporting."""
    # If we've downloaded the special case fixture
    fixture_dir = FIXTURE_DIR / "special_cases/segments/amzn"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    # If fixture not available, skip the test
    pytest.skip("Amazon segment reporting fixture not available")
    return None


@pytest.fixture(scope="session")
def dimensional_statement():
    """Company with dimensional reporting."""
    # If we've downloaded the special case fixture
    fixture_dir = FIXTURE_DIR / "special_cases/dimensional/ko"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    # If fixture not available, skip the test
    pytest.skip("Coca-Cola dimensional reporting fixture not available")
    return None


@pytest.fixture(scope="session")
def custom_taxonomy_example():
    """Company using extensive custom taxonomy."""
    fixture_dir = FIXTURE_DIR / "special_cases/custom_taxonomy/ba"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    # If fixture not available, skip the test
    pytest.skip("Boeing custom taxonomy fixture not available")
    return None


# ===== Industry-Specific Fixtures =====

@pytest.fixture(scope="session")
def financial_company():
    """Financial industry company (JPMorgan)."""
    return jpm_10k_2024


@pytest.fixture(scope="session")
def technology_company():
    """Technology industry company (Apple)."""
    return aapl_10k_2023


@pytest.fixture(scope="session")
def consumer_goods_company():
    """Consumer goods industry company (Coca-Cola)."""
    return ko_10k_2024


@pytest.fixture(scope="session")
def energy_company():
    """Energy industry company (Exxon)."""
    fixture_dir = FIXTURE_DIR / "xom/10k_2023"
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        return XBRL.from_directory(fixture_dir)
    
    pytest.skip("Exxon 2023 10-K fixture not available")
    return None


# ===== Consolidated Fixtures =====

@pytest.fixture(scope="session")
def cached_companies(
    # Modern companies - dependency injection style
    aapl_10k_2023, msft_10k_2024, nflx_10k_2024, jpm_10k_2024, ko_10k_2024,
    # Historical companies
    aapl_10k_2010, nflx_10k_2010, msft_10k_2015, jpm_10k_2013, ko_10k_2012, unp_10k_2012
) -> Dict[str, XBRL]:
    """
    Cache for all company fixtures to avoid reloading.
    
    This fixture returns a dictionary mapping company tickers to their XBRL objects.
    Use this fixture for tests that need to access multiple companies.
    """
    companies = {}
    
    # The proper way - receiving fixtures as parameters and using their values directly
    fixtures_map = {
        # Modern companies
        "aapl": aapl_10k_2023,
        "msft": msft_10k_2024,
        "nflx": nflx_10k_2024,
        "jpm": jpm_10k_2024,
        "ko": ko_10k_2024,
        # Historical companies
        "aapl_2010": aapl_10k_2010,
        "nflx_2010": nflx_10k_2010,
        "msft_2015": msft_10k_2015,
        "jpm_2013": jpm_10k_2013,
        "ko_2012": ko_10k_2012,
        "unp": unp_10k_2012
    }
    
    # Add all available fixtures to the cache
    for ticker, xbrl in fixtures_map.items():
        if xbrl is not None:
            companies[ticker] = xbrl
    
    # Return what we have, even if it's empty
    return companies


# ===== Statement-Type Fixtures =====

@pytest.fixture(scope="session")
def balance_sheets(cached_companies) -> Dict[str, Any]:
    """
    Balance sheets for all companies.
    
    Returns a dictionary mapping company tickers to their balance sheet statements.
    """
    bs = {
        ticker: xbrl.statements.balance_sheet()
        for ticker, xbrl in cached_companies.items()
        if xbrl.statements.balance_sheet() is not None
    }
    return bs


@pytest.fixture(scope="session")
def income_statements(cached_companies) -> Dict[str, Any]:
    """
    Income statements for all companies.
    
    Returns a dictionary mapping company tickers to their income statements.
    """
    return {
        ticker: xbrl.statements.income_statement()
        for ticker, xbrl in cached_companies.items()
        if xbrl.statements.income_statement() is not None
    }


@pytest.fixture(scope="session")
def cash_flow_statements(cached_companies) -> Dict[str, Any]:
    """
    Cash flow statements for all companies.
    
    Returns a dictionary mapping company tickers to their cash flow statements.
    """
    return {
        ticker: xbrl.statements.cashflow_statement()
        for ticker, xbrl in cached_companies.items()
        if xbrl.statements.cashflow_statement() is not None
    }


# ===== Utility Fixtures =====

@pytest.fixture(scope="session")
def get_xbrl_by_filing():
    """
    Utility fixture that provides a function to get XBRL for any filing.
    
    This is useful for tests that need to dynamically fetch XBRL data.
    """
    def _get_xbrl(ticker=None, cik=None, form='10-K', year=None, accession_no=None):
        if accession_no:
            # If we have an accession number, use it
            filing = Filing.get(accession_no)
        else:
            # Otherwise, search for a filing
            company = Company(ticker, cik)
            filings = company.get_filings(form_type=form, year=year)
            if not filings:
                raise ValueError(f"No {form} filings found for {ticker or cik} in {year}")
            filing = filings[0]
        
        return XBRL.from_filing(filing)
    
    return _get_xbrl