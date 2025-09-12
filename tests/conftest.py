import pytest
from pathlib import Path
from typing import Dict, Any

from edgar.xbrl import XBRL
from edgar import httpclient
from edgar import Company

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
