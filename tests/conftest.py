import pytest
from pathlib import Path
from typing import Dict, Any

from edgar.xbrl import XBRL
from edgar import httpclient

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
