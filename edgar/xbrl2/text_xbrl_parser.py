
import os
from pathlib import Path
import datetime
import pandas as pd
from rich.console import Console
from edgar import *
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statements import Statements
import pytest
from rich import print



@pytest.fixture
def aapl_xbrl():
    data_dir = Path(__file__).parent / "aapl"

    # Parse the directory
    return XBRL.parse_directory(data_dir)


def test_correct_entity_info(aapl_xbrl:XBRL):
    entity_info = aapl_xbrl.entity_info
    assert entity_info

    assert entity_info == aapl_xbrl.entity_info
    print(entity_info)
    assert entity_info['entity_name'] == 'Apple Inc.'
    assert entity_info['identifier'] == '320193'
    assert entity_info['reporting_end_date'] == datetime.date(2023, 10, 20)
    assert entity_info['fiscal_year'] == 2023
    assert entity_info['fiscal_period'] == 'FY'
    assert entity_info['annual_report']
    assert not entity_info['quarterly_report']
    assert not entity_info['amendment']

    # Axes
    assert aapl_xbrl.axes
    assert aapl_xbrl.tables
    assert aapl_xbrl.facts
    assert aapl_xbrl.contexts
    assert aapl_xbrl.units
    assert aapl_xbrl.entity_info
    assert aapl_xbrl.calculation_trees
    assert aapl_xbrl.context_period_map
    assert aapl_xbrl.definition_roles
    assert aapl_xbrl.domains
    assert aapl_xbrl.element_catalog
    assert aapl_xbrl.presentation_roles
    assert aapl_xbrl.presentation_trees

