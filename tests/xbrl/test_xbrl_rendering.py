"""
Tests for XBRL2 rendering functionality.
"""
from pathlib import Path
import pytest
from datetime import datetime, date
import calendar
from edgar.xbrl.xbrl import XBRL
from rich import print
from edgar.richtools import rich_to_text, repr_rich
from edgar.xbrl.rendering import render_statement, _format_period_labels, format_date


@pytest.fixture
def aapl_xbrl():
    data_dir = Path("data/xbrl/datafiles/aapl")

    # Parse the directory
    return XBRL.from_directory(data_dir)

def test_render_statement_with_shares():
    """Test rendering a statement with share values."""
    # Create minimal test data with share and monetary values
    statement_data = [
        {
            'label': 'Total Assets',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'concept': 'us-gaap_Assets',
            'has_values': True,
            'values': {'instant_2023-12-31': 1000000000},
            'decimals': {'instant_2023-12-31': -6}  # In millions
        },
        {
            'label': 'Common Stock Shares Outstanding',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_CommonStockSharesOutstanding',
            'has_values': True,
            'values': {'instant_2023-12-31': 5123456000},
            'decimals': {'instant_2023-12-31': -3}  # In thousands
        },
        {
            'label': 'Earnings Per Share, Basic',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_EarningsPerShareBasic',
            'has_values': True,
            'values': {'instant_2023-12-31': 1.25},
            'decimals': {'instant_2023-12-31': 2}  # 2 decimal places
        }
    ]
    
    periods_to_display = [('instant_2023-12-31', 'Dec 31, 2023')]
    
    # Render the statement
    rendered = render_statement(
        statement_data,
        periods_to_display,
        'Test Statement',
        'BalanceSheet'
    )
    panel = rendered.__rich__()

    # Basic check that the panel was created
    assert panel is not None

    # The rendered output should include the scale note (In millions, except shares in thousands)
    # Check the units_note attribute directly since str() may truncate
    assert rendered.units_note is not None
    assert "millions" in rendered.units_note
    assert "shares" in rendered.units_note
    assert "thousands" in rendered.units_note


def test_render_statement_showing_date_range(aapl_xbrl):
    statement = aapl_xbrl.render_statement("IncomeStatement", show_date_range=True)
    _statement = repr_rich(statement)
    print(statement)
    assert 'Sep 26, 2021 -'in _statement


def test_format_period_labels_with_date_range():
    """Test that period labels properly show date ranges when show_date_range is True."""
    # Create test data
    today = date.today()
    
    # Create a quarterly period (90 days)
    end_date = today
    # Calculate target year and month for start_date (3 months prior)
    start_year = end_date.year
    start_month = end_date.month - 3
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    
    # Get the last day of the target month
    last_day_of_start_month = calendar.monthrange(start_year, start_month)[1]
    
    # Set the day for start_date, ensuring it's not out of range for the month
    start_day = min(end_date.day, last_day_of_start_month)
    
    start_date = date(start_year, start_month, start_day)
    
    # Create period keys and labels
    quarterly_key = f"duration_{start_date.isoformat()}_{end_date.isoformat()}"
    
    # Entity info for a quarterly report
    entity_info = {
        'fiscal_period': 'Q1',
        'document_period_end_date': end_date
    }
    
    # Test with show_date_range=True for an income statement
    periods_to_display = [(quarterly_key, "")]
    formatted_periods, indicator = _format_period_labels(
        periods_to_display, 
        entity_info, 
        'IncomeStatement', 
        show_date_range=True
    )
    
    # Verify that the formatted date shows a range (contains a hyphen)
    assert len(formatted_periods) == 1, "Should return one formatted period"
    assert "-" in formatted_periods[0].label, "Should include date range with hyphen when show_date_range=True"
    assert format_date(start_date) in formatted_periods[0].label, "Should include start date in range"
    assert format_date(end_date) in formatted_periods[0].label, "Should include end date in range"
    
    # Test with show_date_range=False (default behavior)
    formatted_periods_no_range, _ = _format_period_labels(
        periods_to_display, 
        entity_info, 
        'IncomeStatement', 
        show_date_range=False
    )
    
    # Verify that the formatted date only shows end date (no hyphen)
    assert len(formatted_periods_no_range) == 1, "Should return one formatted period"
    assert "-" not in formatted_periods_no_range[0].label, "Should not include date range when show_date_range=False"
    assert format_date(end_date) in formatted_periods_no_range[0].label, "Should include end date"
    assert format_date(start_date) not in formatted_periods_no_range[0].label, "Should not include start date"
