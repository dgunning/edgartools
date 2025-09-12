import pytest
from pathlib import Path
from typing import Dict, Any

from edgar.xbrl import XBRL
from edgar import httpclient
from edgar import Company
from edgar._filings import Filing, get_filings

import logging

logger = logging.getLogger(__name__)
# Base paths
FIXTURE_DIR = Path("tests/fixtures/xbrl2")
DATA_DIR = Path("data/xbrl/datafiles")


def pytest_addoption(parser):
    parser.addoption("--enable-cache", action="store_true", help="Enable HTTP cache")


def pytest_configure(config):
    """
    - Disables caching for testing
    """
    if not config.getoption("--enable-cache"):
        logger.info("Cache disabled for test accuracy")    
        httpclient.HTTP_MGR = httpclient.get_http_mgr(cache_enabled=False)

    if hasattr(config, 'workerinput'):
        logger.info("pytest-xdist is enabled, enabling a distributed sqlite ratelimiter")    
        from pyrate_limiter import limiter_factory
        httpclient.HTTP_MGR.rate_limiter = limiter_factory.create_sqlite_limiter(rate_per_duration=10, db_path="ratelimiter.sqlite", use_file_lock=True)


def pytest_collection_modifyitems(items):
    """
    Automatically add regression marker to tests in regression folders.
    
    This ensures that any test file in a 'regression' folder is automatically
    marked with @pytest.mark.regression, even if developers or agents forget
    to add the marker manually. This provides a robust safety net for CI
    test exclusion.
    """
    for item in items:
        test_path = str(item.fspath)
        # Check if test is in any regression folder (supports nested paths)
        if "/regression/" in test_path or "\\regression\\" in test_path:
            item.add_marker(pytest.mark.regression)
            logger.debug(f"Auto-marked regression test: {item.nodeid}")


# Session-scoped company fixtures for performance optimization
@pytest.fixture(scope="session")
def aapl_company():
    """Apple Inc. company fixture - cached for entire test session"""
    return Company("AAPL")


@pytest.fixture(scope="session") 
def tsla_company():
    """Tesla Inc. company fixture - cached for entire test session"""
    return Company("TSLA")


@pytest.fixture(scope="module")
def expe_company():
    """Expedia Group company fixture - cached per test module"""
    return Company("EXPE")


@pytest.fixture(scope="module")
def nvda_company():
    """NVIDIA Corporation company fixture - cached per test module"""
    return Company("NVDA")


@pytest.fixture(scope="module")
def snow_company():
    """Snowflake Inc. company fixture - cached per test module"""
    return Company("SNOW")


@pytest.fixture(scope="module")
def msft_company():
    """Microsoft Corporation company fixture - cached per test module"""
    return Company("MSFT")


@pytest.fixture(scope="module")
def amzn_company():
    """Amazon.com Inc. company fixture - cached per test module"""
    return Company("AMZN")


# Filing fixtures for performance optimization
@pytest.fixture(scope="session")
def carbo_10k_filing():
    """CARBO CERAMICS INC 10-K filing - cached for entire test session"""
    return Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672,
                 filing_date='2018-03-08', accession_no='0001564590-18-004771')


@pytest.fixture(scope="module")
def three_m_8k_filing():
    """3M CO 8-K filing - cached per test module"""
    return Filing(form='8-K', filing_date='2024-03-08', company='3M CO',
                 cik=66740, accession_no='0000066740-24-000023')


@pytest.fixture(scope="module")
def ten_x_genomics_10k_filing():
    """10x Genomics, Inc. 10-K filing - cached per test module"""
    return Filing(form='10-K', company='10x Genomics, Inc.',
                 cik=1770787, filing_date='2020-02-27', accession_no='0001193125-20-052640')


@pytest.fixture(scope="module")
def orion_form4_filing():
    """Orion Engineered Carbons S.A. Form 4 filing - cached per test module"""
    return Filing(form='4', company='Orion Engineered Carbons S.A.',
                 cik=1609804, filing_date='2022-11-04', accession_no='0000950142-22-003095')


# Cached get_filings() results for performance
@pytest.fixture(scope="session")
def filings_2022_q3():
    """2022 Q3 filings - cached for entire test session"""
    return get_filings(2022, 3)


@pytest.fixture(scope="session") 
def filings_2021_q1():
    """2021 Q1 filings - cached for entire test session"""
    return get_filings(2021, 1)


@pytest.fixture(scope="session")
def filings_2021_q1_xbrl():
    """2021 Q1 XBRL filings - cached for entire test session"""
    return get_filings(2021, 1, index="xbrl")


@pytest.fixture(scope="module")
def filings_2014_q4():
    """2014 Q4 filings - cached per test module"""
    return get_filings(2014, 4)
