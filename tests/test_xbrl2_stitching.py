"""
Tests for the XBRL statement stitching functionality.
"""

from unittest.mock import MagicMock, patch
from edgar import *
from edgar.xbrl2 import XBRL, XBRLS
from rich import print

import pytest

from edgar.xbrl2.stitching import (
    StatementStitcher, stitch_statements, render_stitched_statement, to_pandas
)



@pytest.fixture
def stitcher():
    """Fixture providing a fresh StatementStitcher instance."""
    return StatementStitcher()


def test_init(stitcher):
    """Test initialization of StatementStitcher."""
    assert stitcher.concept_mapper is not None
    assert stitcher.mapping_store is not None
    assert stitcher.periods == []
    assert stitcher.period_dates == {}


def test_period_type_enum():
    """Test PeriodType enum."""
    assert StatementStitcher.PeriodType.RECENT_PERIODS == "Most Recent Periods"
    assert StatementStitcher.PeriodType.THREE_YEAR_COMPARISON == "Three-Year Comparison"
    assert StatementStitcher.PeriodType.THREE_QUARTERS == "Three Recent Quarters"


def test_extract_periods(stitcher):
    """Test period extraction from statements."""
    statements = [{
        'periods': {
            'instant_2024-12-31': {'label': 'Dec 31, 2024'},
            'instant_2023-12-31': {'label': 'Dec 31, 2023'},
            'duration_2024-01-01_2024-12-31': {'label': 'Year Ended Dec 31, 2024'},
            'duration_2023-01-01_2023-12-31': {'label': 'Year Ended Dec 31, 2023'}
        }
    }]

    periods = stitcher._extract_periods(statements)

    assert len(periods) == 4
    assert periods[0][0] == 'instant_2024-12-31'
    assert periods[1][0] == 'duration_2024-01-01_2024-12-31'
    assert len(stitcher.period_dates) == 4
    assert stitcher.period_dates['instant_2024-12-31'] == 'Dec 31, 2024'


def test_select_periods_recent(stitcher):
    """Test period selection for RECENT_PERIODS type."""
    all_periods = [
        ('instant_20241231', '2024-12-31'),
        ('instant_20231231', '2023-12-31'),
        ('instant_20221231', '2022-12-31'),
        ('instant_20211231', '2021-12-31')
    ]

    selected = stitcher._select_periods(all_periods,
                                      StatementStitcher.PeriodType.RECENT_PERIODS,
                                      max_periods=2)

    assert len(selected) == 2
    assert selected[0] == 'instant_20241231'
    assert selected[1] == 'instant_20231231'


def test_select_periods_three_year_comparison(stitcher):
    """Test period selection for THREE_YEAR_COMPARISON type."""
    all_periods = [
        ('instant_20241231', '2024-12-31'),
        ('duration_20240101_20241231', '2024-12-31'),
        ('instant_20231231', '2023-12-31'),
        ('duration_20230101_20231231', '2023-12-31'),
        ('instant_20221231', '2022-12-31'),
        ('duration_20220101_20221231', '2022-12-31'),
    ]

    selected = stitcher._select_periods(all_periods,
                                      StatementStitcher.PeriodType.THREE_YEAR_COMPARISON,
                                      max_periods=3)

    assert len(selected) == 3
    assert selected[0] == 'instant_20241231'
    assert selected[1] == 'instant_20231231'
    assert selected[2] == 'instant_20221231'


def test_integrate_statement_data(stitcher):
    """Test integrating statement data."""
    stitcher.periods = ['instant_20241231', 'instant_20231231']
    statement_data = [
        {
            'concept': 'us-gaap_Assets',
            'label': 'Total Assets',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'values': {'instant_20241231': 1000, 'instant_20231231': 900},
            'decimals': {'instant_20241231': 0, 'instant_20231231': 0}
        },
        {
            'concept': 'us-gaap_Liabilities',
            'label': 'Total Liabilities',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'values': {'instant_20241231': 600, 'instant_20231231': 550},
            'decimals': {'instant_20241231': 0, 'instant_20231231': 0}
        }
    ]
    period_map = {
        'instant_20241231': {'label': 'Dec 31, 2024'},
        'instant_20231231': {'label': 'Dec 31, 2023'}
    }
    relevant_periods = {'instant_20241231', 'instant_20231231'}

    stitcher._integrate_statement_data(statement_data, period_map, relevant_periods)

    assert len(stitcher.concept_metadata) == 2
    assert 'Total Assets' in stitcher.concept_metadata
    assert 'Total Liabilities' in stitcher.concept_metadata
    assert stitcher.data['Total Assets']['instant_20241231']['value'] == 1000
    assert stitcher.data['Total Liabilities']['instant_20231231']['value'] == 550


def test_format_output(stitcher):
    """Test formatting output."""
    stitcher.periods = ['instant_20241231', 'instant_20231231']
    stitcher.period_dates = {
        'instant_20241231': 'Dec 31, 2024',
        'instant_20231231': 'Dec 31, 2023'
    }
    stitcher.concept_metadata = {
        'Total Assets': {'level': 0, 'is_abstract': False, 'is_total': True, 'original_concept': 'us-gaap_Assets'},
        'Total Liabilities': {'level': 0, 'is_abstract': False, 'is_total': True, 'original_concept': 'us-gaap_Liabilities'}
    }
    stitcher.data = {
        'Total Assets': {'instant_20241231': {'value': 1000, 'decimals': 0}, 'instant_20231231': {'value': 900, 'decimals': 0}},
        'Total Liabilities': {'instant_20241231': {'value': 600, 'decimals': 0}, 'instant_20231231': {'value': 550, 'decimals': 0}}
    }

    result = stitcher._format_output()

    assert 'periods' in result
    assert 'statement_data' in result
    assert len(result['periods']) == 2
    assert result['periods'][0] == ('instant_20241231', 'Dec 31, 2024')
    assert len(result['statement_data']) == 2
    assert result['statement_data'][0]['label'] == 'Total Assets'
    assert result['statement_data'][0]['values']['instant_20241231'] == 1000


@patch('edgar.xbrl2.stitching.standardize_statement')
def test_standardize_statement_data(mock_standardize, stitcher):
    """Test standardizing statement data."""
    mock_standardize.return_value = [{'label': 'Standardized Label'}]
    statement = {'statement_type': 'BalanceSheet', 'data': [{'label': 'Original Label'}]}

    result = stitcher._standardize_statement_data(statement)

    mock_standardize.assert_called_once()
    assert result == [{'label': 'Standardized Label'}]


def test_stitch_statements(stitcher):
    """Test stitching statements."""
    statements = [{
        'statement_type': 'BalanceSheet',
        'periods': {
            'instant_2024-12-31': {'label': 'Dec 31, 2024'},
            'instant_2023-12-31': {'label': 'Dec 31, 2023'}
        },
        'data': [{
            'concept': 'us-gaap_Assets',
            'label': 'Total Assets',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'values': {'instant_2024-12-31': 1000, 'instant_2023-12-31': 900},
            'decimals': {'instant_2024-12-31': 0, 'instant_2023-12-31': 0}
        }]
    }]

    result = stitcher.stitch_statements(statements,
                                      StatementStitcher.PeriodType.RECENT_PERIODS,
                                      max_periods=2,
                                      standard=False)

    assert 'periods' in result
    assert 'statement_data' in result
    assert len(result['periods']) == 2
    assert len(result['statement_data']) == 1
    assert result['statement_data'][0]['label'] == 'Total Assets'


@patch('edgar.xbrl2.stitching.StatementStitcher')
def test_stitch_statements_function(mock_stitcher_class):
    """Test the stitch_statements function."""
    mock_stitcher = MagicMock()
    mock_stitcher_class.return_value = mock_stitcher
    mock_stitcher.stitch_statements.return_value = {'result': 'test'}

    mock_xbrl1 = MagicMock()
    mock_xbrl1.get_statement_by_type.return_value = {'statement': 'data1'}
    mock_xbrl2 = MagicMock()
    mock_xbrl2.get_statement_by_type.return_value = {'statement': 'data2'}

    result = stitch_statements([mock_xbrl1, mock_xbrl2],
                             statement_type='IncomeStatement',
                             period_type='THREE_QUARTERS',
                             max_periods=3,
                             standard=True)

    mock_stitcher_class.assert_called_once()
    mock_xbrl1.get_statement_by_type.assert_called_once_with('IncomeStatement')
    mock_stitcher.stitch_statements.assert_called_once_with(
        [{'statement': 'data1'}, {'statement': 'data2'}],
        'THREE_QUARTERS',
        3,
        True
    )
    assert result == {'result': 'test'}

def test_stitch_aapl_statements():
    c = Company("AAPL")
    filings = c.latest("10-K", 2)  # 2 filings should cover ~4 years with overlaps
    print()
    xbrls = [XBRL.from_filing(f) for f in filings]

    # Print information about the individual filings
    for i, xbrl in enumerate(xbrls):
        # Count available periods for this filing
        periods = []
        for period in xbrl.reporting_periods:
            if period['type'] == 'duration':
                key = f"duration_{period['start_date']}_{period['end_date']}"
                periods.append((key, period['label']))
        
        print(f"\nFiling {i+1} periods: {[p[1] for p in periods]}")
        print(xbrl.render_statement("IncomeStatement"))

    # Use ALL_PERIODS and higher max_periods to ensure we see all years
    statement_data = stitch_statements(
        xbrls, 
        statement_type="IncomeStatement",
        period_type=StatementStitcher.PeriodType.ALL_PERIODS,
        max_periods=10  # Allow up to 10 periods to ensure we capture all
    )
    
    # Print the periods we found in the stitched data
    print(f"\nPERIODS IN STITCHED DATA: {[p[1] for p in statement_data['periods']]}")
    print(f"Number of periods: {len(statement_data['periods'])}")
    
    # Render the stitched statement
    result = render_stitched_statement(
        statement_data,
        statement_title="CONSOLIDATED STATEMENT OF INCOME",
        statement_type="IncomeStatement"
    )

    print("\nSTITCHED STATEMENT:")
    print(result)
    
    # Convert to pandas for easier viewing of column structure
    df = to_pandas(statement_data)
    print("\nDataFrame Columns (should be unique periods):")
    print(df.columns.tolist())
    
    # Assert we have at least 4 periods in the stitched data (no duplicates)
    assert len(statement_data['periods']) >= 4, f"Expected at least 4 periods, got {len(statement_data['periods'])}"
    
    # Assert the DataFrame columns match the unique periods
    assert len(df.columns) == len(statement_data['periods']), f"Column mismatch: {len(df.columns)} vs {len(statement_data['periods'])}"


def test_stitching_using_xbrls():
    c = Company("AAPL")
    filings = c.latest("10-K", 2)
    xbrls:XBRLS = XBRLS.from_filings(filings)
    income_statement = xbrls.statements.income_statement()
    print(income_statement)
    df = income_statement.to_dataframe()
    print(df.columns)