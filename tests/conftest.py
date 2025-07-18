import pytest
from pathlib import Path
from typing import Dict, Any

from edgar.xbrl import XBRL

# Base paths
FIXTURE_DIR = Path("tests/fixtures/xbrl2")
DATA_DIR = Path("data/xbrl/datafiles")

def pytest_configure(config):
    """
    - Disables caching for testing
    - Uses a sqlitebucket so we can use xdist to parallelize the tests
    """

    httpclient.CACHE_DIRECTORY = None