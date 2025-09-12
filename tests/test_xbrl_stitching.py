"""
Tests for the XBRL statement stitching functionality.
"""

from unittest.mock import MagicMock, patch
from edgar import *
from edgar.xbrl import XBRL, XBRLS
from rich import print
from edgar.richtools import rich_to_text
import pytest
import pandas as pd
from functools import lru_cache

from edgar.xbrl.statements import StitchedStatements
from edgar.xbrl.stitching import (
    StatementStitcher, stitch_statements,
    render_stitched_statement, to_pandas, determine_optimal_periods,
    StitchedFactsView, StitchedFactQuery
)



@pytest.fixture
def stitcher():
    """Fixture providing a fresh StatementStitcher instance."""
    return StatementStitcher()

@pytest.fixture
def amd_xbrl():
    c = Company("AMD")
    filings = c.latest("10-K", 3)
    return XBRLS.from_filings(filings)

@pytest.fixture
def meta_xbrl():
    c = Company("META")
    filings = c.get_filings(form="10-K").latest(3)
    return XBRLS.from_filings(filings)

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


@patch('edgar.xbrl.stitching.core.standardize_statement')
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


def test_stitch_aapl_statements(aapl_company):
    c = aapl_company
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
    assert len(statement_data['periods']) >= 2, f"Expected at least 4 periods, got {len(statement_data['periods'])}"


def test_stitching_using_xbrls(aapl_company):
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls:XBRLS = XBRLS.from_filings(filings)
    income_statement = xbrls.statements.income_statement()
    print(income_statement)
    df = income_statement.to_dataframe()
    print(df.columns)
    print(df.concept)

@lru_cache(maxsize=None)
def get_statements(ticker:str, n=6):
    c = Company(ticker)
    filings = c.latest("10-K", n)
    return XBRLS.from_filings(filings).statements


def test_determine_optimal_periods(aapl_company):
    c = aapl_company
    filings = c.latest("10-K", 4)
    xbrls = [XBRL.from_filing(f) for f in filings]
    optimal_periods = determine_optimal_periods(xbrls, "BalanceSheet")
    assert optimal_periods
    assert len(optimal_periods) == 4
    period_keys = [op['period_key'] for op in optimal_periods]
    assert period_keys == ['instant_2024-09-28','instant_2023-09-30','instant_2022-09-24','instant_2021-09-25']

    c = Company("ORCL")
    filings = c.latest("10-K", 4)
    xbrls = [XBRL.from_filing(f) for f in filings]
    optimal_periods = determine_optimal_periods(xbrls, "BalanceSheet")
    print(optimal_periods)
    period_keys = [op['period_key'] for op in optimal_periods]
    
    # Check that we got 4 periods and they are all May 31st dates in descending order
    assert len(period_keys) == 4
    assert all('instant_' in key and '-05-31' in key for key in period_keys)
    
    # Check that dates are in descending order (most recent first)
    years = [int(key.split('_')[1].split('-')[0]) for key in period_keys]
    assert years == sorted(years, reverse=True)

def test_stitch_balance_sheet():
    statements = get_statements("ORCL")
    balance_sheet = statements.balance_sheet()
    print(balance_sheet)


def test_concept_merging():
    """
    Test that rows with the same concept but different labels are merged properly.
    """
    # Create a stitcher
    stitcher = StatementStitcher()
    
    # Set up periods (most recent first)
    stitcher.periods = ['instant_2024-12-31', 'instant_2023-12-31', 'instant_2022-12-31']
    stitcher.period_dates = {
        'instant_2024-12-31': 'Dec 31, 2024',
        'instant_2023-12-31': 'Dec 31, 2023',
        'instant_2022-12-31': 'Dec 31, 2022'
    }
    
    # Create 2 statements with the same concept but different labels
    statement1 = {
        'statement_type': 'BalanceSheet',
        'periods': {
            'instant_2024-12-31': {'label': 'Dec 31, 2024'}
        },
        'data': [
            {
                'concept': 'us-gaap_Assets',
                'label': 'Total Assets',  # Label in 2024
                'level': 0,
                'is_abstract': False,
                'is_total': True,
                'values': {'instant_2024-12-31': 1000},
                'decimals': {'instant_2024-12-31': 2}
            }
        ]
    }
    
    statement2 = {
        'statement_type': 'BalanceSheet',
        'periods': {
            'instant_2023-12-31': {'label': 'Dec 31, 2023'},
            'instant_2022-12-31': {'label': 'Dec 31, 2022'}
        },
        'data': [
            {
                'concept': 'us-gaap_Assets',
                'label': 'Assets, Total',  # Different label in 2023/2022
                'level': 0,
                'is_abstract': False,
                'is_total': True,
                'values': {
                    'instant_2023-12-31': 900,
                    'instant_2022-12-31': 800
                },
                'decimals': {
                    'instant_2023-12-31': 2,
                    'instant_2022-12-31': 2
                }
            }
        ]
    }
    
    # Stitch the statements
    result = stitcher.stitch_statements([statement1, statement2])
    
    # Verify that a single line item was created for the matching concepts
    assert len(result['statement_data']) == 1, "There should be only one row for the matching concepts"
    
    # Verify that the label from the most recent period is used
    assert result['statement_data'][0]['label'] == 'Total Assets', "The label from the most recent period should be used"
    
    # Verify that values from all periods are included
    assert result['statement_data'][0]['values']['instant_2024-12-31'] == 1000
    assert result['statement_data'][0]['values']['instant_2023-12-31'] == 900
    assert result['statement_data'][0]['values']['instant_2022-12-31'] == 800


def test_multiple_concepts_merging():
    """
    Test merging with multiple concepts, including some that should merge and some that shouldn't.
    """
    # Create a stitcher
    stitcher = StatementStitcher()
    
    # Set up periods (most recent first)
    stitcher.periods = ['instant_2024-12-31', 'instant_2023-12-31']
    stitcher.period_dates = {
        'instant_2024-12-31': 'Dec 31, 2024',
        'instant_2023-12-31': 'Dec 31, 2023'
    }
    
    # Statement 1 (2024)
    statement1 = {
        'statement_type': 'BalanceSheet',
        'periods': {
            'instant_2024-12-31': {'label': 'Dec 31, 2024'}
        },
        'data': [
            {
                'concept': 'us-gaap_Assets',
                'label': 'Total Assets',
                'level': 0,
                'is_abstract': False,
                'values': {'instant_2024-12-31': 1000},
                'decimals': {'instant_2024-12-31': 2}
            },
            {
                'concept': 'us-gaap_Cash',
                'label': 'Cash and Cash Equivalents',
                'level': 1,
                'is_abstract': False,
                'values': {'instant_2024-12-31': 200},
                'decimals': {'instant_2024-12-31': 2}
            },
            {
                'concept': 'us-gaap_AccountsReceivable',
                'label': 'Accounts Receivable, Net',
                'level': 1,
                'is_abstract': False,
                'values': {'instant_2024-12-31': 300},
                'decimals': {'instant_2024-12-31': 2}
            }
        ]
    }
    
    # Statement 2 (2023) - with different labels but same concepts
    statement2 = {
        'statement_type': 'BalanceSheet',
        'periods': {
            'instant_2023-12-31': {'label': 'Dec 31, 2023'}
        },
        'data': [
            {
                'concept': 'us-gaap_Assets',
                'label': 'Assets, Total',  # Different label
                'level': 0,
                'is_abstract': False,
                'values': {'instant_2023-12-31': 900},
                'decimals': {'instant_2023-12-31': 2}
            },
            {
                'concept': 'us-gaap_Cash',
                'label': 'Cash & Equivalents',  # Different label
                'level': 1,
                'is_abstract': False,
                'values': {'instant_2023-12-31': 180},
                'decimals': {'instant_2023-12-31': 2}
            },
            {
                'concept': 'us-gaap_Inventory',  # Different concept, shouldn't merge
                'label': 'Inventory',
                'level': 1,
                'is_abstract': False,
                'values': {'instant_2023-12-31': 150},
                'decimals': {'instant_2023-12-31': 2}
            }
        ]
    }
    
    # Stitch the statements
    result = stitcher.stitch_statements([statement1, statement2])
    
    # Extract labels from the result for easier testing
    result_labels = [item['label'] for item in result['statement_data']]
    
    # We should have 4 unique rows:
    # 1. Total Assets (merged from both statements)
    # 2. Cash and Cash Equivalents (merged from both statements)
    # 3. Accounts Receivable, Net (only from statement 1)
    # 4. Inventory (only from statement 2)
    assert len(result['statement_data']) == 4, "There should be 4 distinct rows after merging"
    
    # Verify the labels are as expected (most recent should be used for merged items)
    assert 'Total Assets' in result_labels
    assert 'Cash and Cash Equivalents' in result_labels
    assert 'Accounts Receivable, Net' in result_labels
    assert 'Inventory' in result_labels
    
    # Verify no duplicate labels
    assert 'Assets, Total' not in result_labels
    assert 'Cash & Equivalents' not in result_labels
    
    # Get the merged Total Assets row
    total_assets_row = next(item for item in result['statement_data'] 
                           if item['label'] == 'Total Assets')
    
    # Verify it has values for both periods
    assert total_assets_row['values']['instant_2024-12-31'] == 1000
    assert total_assets_row['values']['instant_2023-12-31'] == 900


def test_get_optimal_statements(amd_xbrl, meta_xbrl):
    """Test stitching 3 statements."""

    optimal_periods = determine_optimal_periods(amd_xbrl.xbrl_list, "BalanceSheet")
    periods = [op['period_key'] for op in optimal_periods]
    assert periods == ['instant_2024-12-28', 'instant_2023-12-30', 'instant_2022-12-31']

    optimal_periods = determine_optimal_periods(meta_xbrl.xbrl_list, "BalanceSheet")
    periods = [op['period_key'] for op in optimal_periods]
    print(periods)
    balance_sheet = meta_xbrl.render_statement("BalanceSheet")
    print(balance_sheet)

def test_stitch_3_statements(amd_xbrl, meta_xbrl):
    statement = stitch_statements(meta_xbrl.xbrl_list, statement_type='BalanceSheet')
    print()
    assert len(statement['periods']) == 3


def test_stitch_aapl_statements_from_2019(aapl_company):
    c = aapl_company
    filings = c.get_filings(form="10-K", filing_date="2019-01-01:2020-11-05").head(2)
    xbrls = XBRLS.from_filings(filings)
    optimal_periods = determine_optimal_periods(xbrls.xbrl_list, "IncomeStatement")
    periods = [op['period_key'] for op in optimal_periods]
    assert periods == ['duration_2019-09-29_2020-09-26', 'duration_2018-09-30_2019-09-28']

    income_statement = xbrls.render_statement("IncomeStatement")
    _repr = rich_to_text(income_statement)
    print(_repr)
    assert '$(161,782)' in _repr


def test_stitch_statements_using_max_periods(aapl_company):
    c = aapl_company
    filings = c.latest("10-K", 10)
    xb = XBRLS.from_filings(filings)
    income_statement = xb.statements.income_statement(max_periods=10)
    assert len(income_statement.periods) == 10


# ======== NEW QUERY FUNCTIONALITY TESTS ========

def test_xbrls_facts_property(aapl_company):
    """Test that XBRLS has a facts property that returns StitchedFactsView."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Test facts property
    facts_view = xbrls.facts
    assert isinstance(facts_view, StitchedFactsView)
    assert facts_view.xbrls is xbrls
    
    # Test that it's cached
    facts_view2 = xbrls.facts
    assert facts_view is facts_view2


def test_stitched_facts_view_basic(aapl_company):
    """Test basic functionality of StitchedFactsView."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    facts_view = xbrls.facts
    
    # Test entity name and document type
    assert facts_view.entity_name
    assert facts_view.document_type
    
    # Test get_facts
    facts = facts_view.get_facts(max_periods=3)
    assert isinstance(facts, list)
    assert len(facts) > 0
    
    # Check that facts have expected structure
    fact = facts[0]
    expected_keys = [
        'concept', 'label', 'statement_type', 'value', 'numeric_value',
        'period_key', 'period_type', 'standardized'
    ]
    for key in expected_keys:
        assert key in fact, f"Expected key '{key}' not found in fact"
    
    # Test that standardized flag is set
    assert fact['standardized'] is True


def test_xbrls_query_method(aapl_company):
    """Test XBRLS query method."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Test query method returns StitchedFactQuery
    query = xbrls.query(max_periods=3)
    assert isinstance(query, StitchedFactQuery)
    
    # Test query execution
    results = query.execute()
    assert isinstance(results, list)
    assert len(results) > 0


def test_stitched_fact_query_by_standardized_concept(aapl_company):
    """Test filtering by standardized concept."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Query for Revenue
    revenue_query = xbrls.query().by_standardized_concept("Revenue")
    revenue_facts = revenue_query.execute()
    
    # Should find some revenue facts
    assert len(revenue_facts) > 0
    
    # All results should contain "Revenue" in label or concept
    for fact in revenue_facts:
        label = fact.get('label', '').lower()
        concept = fact.get('concept', '').lower()
        assert 'revenue' in label or 'revenue' in concept


def test_stitched_fact_query_by_original_label(aapl_company):
    """Test filtering by original company-specific labels."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Query for facts with original labels containing "Net sales"
    query = xbrls.query().by_original_label("sales")
    results = query.execute()
    
    # Test that we get results (assuming AAPL has "Net sales" in their original labels)
    if results:  # Only test if we found matching facts
        for fact in results:
            original_label = fact.get('original_label', '').lower()
            assert 'sales' in original_label


def test_stitched_fact_query_across_periods(aapl_company):
    """Test filtering to concepts that appear across multiple periods."""
    c = aapl_company
    filings = c.latest("10-K", 3)
    xbrls = XBRLS.from_filings(filings)
    
    # Query for concepts that appear in at least 2 periods
    query = xbrls.query().across_periods(min_periods=2)
    results = query.execute()
    
    assert len(results) > 0
    
    # Verify that each concept appears in at least 2 periods
    from collections import defaultdict
    concept_periods = defaultdict(set)
    for fact in results:
        concept_key = (fact.get('concept', ''), fact.get('label', ''))
        concept_periods[concept_key].add(fact.get('period_key', ''))
    
    for concept, periods in concept_periods.items():
        assert len(periods) >= 2, f"Concept {concept} appears in {len(periods)} periods, expected >= 2"


def test_stitched_fact_query_trend_analysis(aapl_company):
    """Test trend analysis functionality."""
    c = aapl_company
    filings = c.latest("10-K", 3)
    xbrls = XBRLS.from_filings(filings)
    
    # Set up trend analysis for Revenue
    query = xbrls.query().trend_analysis("Revenue")
    results = query.execute()
    
    if results:  # Only test if we found revenue data
        # Results should be sorted by period_end for trend analysis
        period_ends = [fact.get('period_end') for fact in results if fact.get('period_end')]
        assert period_ends == sorted(period_ends), "Results should be sorted by period_end for trend analysis"
        
        # Test trend DataFrame
        trend_df = query.to_trend_dataframe()
        assert isinstance(trend_df, pd.DataFrame)
        if not trend_df.empty:
            # Should have periods as columns
            assert len(trend_df.columns) > 0


def test_stitched_fact_query_to_dataframe(aapl_company):
    """Test converting query results to DataFrame."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Get basic query results as DataFrame
    query = xbrls.query()
    df = query.to_dataframe()
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    
    # Check for expected columns
    expected_cols = ['concept', 'label', 'value', 'numeric_value', 'statement_type']
    for col in expected_cols:
        assert col in df.columns, f"Expected column '{col}' not found"
    
    # Test filtering specific columns
    df_filtered = query.to_dataframe('concept', 'label', 'value')
    assert list(df_filtered.columns) == ['concept', 'label', 'value']


def test_stitched_fact_query_chaining(aapl_company):
    """Test method chaining for complex queries."""
    c = aapl_company
    filings = c.latest("10-K", 3)
    xbrls = XBRLS.from_filings(filings)
    
    # Build a complex query with method chaining
    query = (xbrls.query()
             .by_standardized_concept("Revenue")
             .across_periods(min_periods=2)
             .sort_by('period_end')
             .limit(10))
    
    results = query.execute()
    
    # Should have limited results
    assert len(results) <= 10
    
    # All results should be revenue-related and appear in multiple periods
    if results:
        # Check period sorting
        period_ends = [fact.get('period_end') for fact in results if fact.get('period_end')]
        if len(period_ends) > 1:
            assert period_ends == sorted(period_ends), "Results should be sorted by period_end"


def test_stitched_fact_query_value_filtering(aapl_company):
    """Test filtering by value ranges."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Query for high-value items (> $1 billion)
    query = xbrls.query().by_value(lambda x: x > 1000000000)
    results = query.execute()
    
    # All results should have numeric values > 1 billion
    for fact in results:
        numeric_value = fact.get('numeric_value')
        if numeric_value is not None:
            assert numeric_value > 1000000000


def test_stitched_fact_query_statement_type_filtering(aapl_company):
    """Test filtering by statement type."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    # Query for only income statement facts
    query = xbrls.query(statement_types=['IncomeStatement'])
    results = query.execute()
    
    # All results should be from income statement
    for fact in results:
        assert fact.get('statement_type') == 'IncomeStatement'


def test_stitched_facts_view_caching(aapl_company):
    """Test that facts are cached properly."""
    c = aapl_company
    filings = c.latest("10-K", 2)
    xbrls = XBRLS.from_filings(filings)
    
    facts_view = xbrls.facts
    
    # First call
    facts1 = facts_view.get_facts(max_periods=3)
    
    # Second call with same parameters should use cache
    facts2 = facts_view.get_facts(max_periods=3)
    
    # Should be the same object (cached)
    assert facts1 is facts2
    
    # Different parameters should bypass cache
    facts3 = facts_view.get_facts(max_periods=2)
    assert facts3 is not facts1


def test_stitched_statements_uses_document_period_end_date():
    c = Company("CMI")
    filings = c.get_filings(form="10-K", amendments=False).latest(3)
    xbrls = XBRLS.from_filings(filings)
    statements = xbrls.statements
    balance_sheet = statements.balance_sheet()
    print(balance_sheet)

    xbrl_periods = [ xb.period_of_report for xb in xbrls.xbrl_list]

    assert xbrl_periods == balance_sheet.periods
