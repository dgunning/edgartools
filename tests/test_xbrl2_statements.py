from pathlib import Path

import pytest
from rich import print
from rich.console import Console

from edgar import *
from edgar.xbrl2.statements import Statements
from edgar.xbrl2.xbrl import XBRL


@pytest.fixture
def tsla_xbrl():
    data_dir = Path("data/xbrl/datafiles/tsla")

    # Parse the directory
    return XBRL.parse_directory(data_dir)

def test_get_statement_by_short_name(tsla_xbrl):
    print()
    statement = tsla_xbrl.get_statement('Cover')
    assert statement
    print(statement)

def test_statement_get_item_int(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements[0]
    assert statement

def test_statement_get_item_by_name(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements["Cover"]
    assert statement
    print(statement.render())