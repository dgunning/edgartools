import pytest
from pathlib import Path
from typing import Dict, Any

from edgar import Company, Filing
from edgar.xbrl2 import XBRL

# Base paths
FIXTURE_DIR = Path("tests/fixtures/xbrl2")
DATA_DIR = Path("data/xbrl/datafiles")