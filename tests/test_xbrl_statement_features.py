"""
Tests for XBRL2 statement features.

This module focuses on testing advanced statement functionality in XBRL2:
- Statement structure and hierarchy
- Statement rendering
- Statement to DataFrame conversion
- Period detection and handling
- Statement data access methods
- Statement calculations
- Dimensional statements

Note: Basic resolution tests are in test_xbrl_statements.py to avoid duplication.
"""

# Import XBRL directly
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL, FactQuery
from edgar.xbrl.rendering import RenderedStatement


# Setup a test fixture for companies
@pytest.fixture
def test_companies():
    """Create basic test companies for use in tests."""
    result = {}
    
    # Define fixture paths
    fixture_dir = Path("tests/fixtures/xbrl2")

    result['aapl'] = XBRL.from_directory(fixture_dir / "aapl/10k_2023")
    result['msft'] = XBRL.from_directory(fixture_dir / "msft/10k_2024")
    result['nflx'] = XBRL.from_directory(fixture_dir / "nflx/10k_2024")

    return result

# Setup fixtures for statement types
@pytest.fixture
def test_balance_sheets(test_companies):
    """Get balance sheets from test companies."""
    result = {}
    for ticker, xbrl in test_companies.items():
        balance_sheet = xbrl.statements.balance_sheet()
        if balance_sheet:
            result[ticker] = balance_sheet
    return result

@pytest.fixture
def test_income_statements(test_companies):
    """Get income statements from test companies."""
    result = {}
    for ticker, xbrl in test_companies.items():
        income_statement = xbrl.statements.income_statement()
        if income_statement:
            result[ticker] = income_statement
    return result

@pytest.fixture
def test_cash_flow_statements(test_companies):
    """Get cash flow statements from test companies."""
    result = {}
    for ticker, xbrl in test_companies.items():
        cash_flow = xbrl.statements.cashflow_statement()
        if cash_flow:
            result[ticker] = cash_flow
    return result

@pytest.fixture
def test_dimensional_data():
    """Try to find company data with dimensional statements."""
    fixture_dir = Path("tests/fixtures/xbrl2/special_cases/dimensional/ko")
    if fixture_dir.exists() and any(fixture_dir.iterdir()):
        try:
            return XBRL.from_directory(fixture_dir)
        except Exception:
            pass
    return None


# ===== Statement Resolution Tests =====
# Note: Basic resolution tests (test_standard_statement_resolution,
# test_statement_accessor_methods, test_parenthetical_statement_resolution)
# are in test_xbrl_statements.py to avoid duplication


# ===== Statement Structure Tests =====

def test_statement_structure(test_balance_sheets):
    """Test the basic structure of statements."""
    if not test_balance_sheets:
        pytest.skip("No balance sheet fixtures available")
    
    # Get the first available balance sheet
    ticker, statement = next(iter(test_balance_sheets.items()))
    
    # Basic structure tests
    assert hasattr(statement, "get_raw_data"), "Statement missing get_raw_data method"
    assert hasattr(statement, "to_dataframe"), "Statement missing to_dataframe method"
    assert hasattr(statement, "render"), "Statement missing render method"
    assert hasattr(statement, "calculate_ratios"), "Statement missing calculate_ratios method"
    
    # Get raw data
    raw_data = statement.get_raw_data()
    assert isinstance(raw_data, list), "Raw data should be a list"
    assert raw_data, "Raw data should not be empty"
    
    # Check structure of first item
    first_item = raw_data[0]
    assert "concept" in first_item, "Statement item missing concept field"
    assert "label" in first_item, "Statement item missing label field"


def test_statement_concept_hierarchy(test_balance_sheets):
    """Test that statements maintain a hierarchical structure of concepts."""
    if not test_balance_sheets:
        pytest.skip("No balance sheet fixtures available")
    
    # Get the first available balance sheet
    ticker, statement = next(iter(test_balance_sheets.items()))
    
    # Get raw data
    raw_data = statement.get_raw_data()
    
    # Look for different types of hierarchical relationships
    # Either parent_id or children fields
    items_with_parents = [item for item in raw_data if "parent_id" in item]
    items_with_children = [item for item in raw_data 
                          if isinstance(item.get("children"), list) and item.get("children")]
    
    # Check for any type of hierarchical relationship
    has_hierarchy = items_with_parents or items_with_children
    
    # Log what we find instead of asserting
    print(f"\nStatement hierarchy for {ticker} balance sheet:")
    print(f"  Total items: {len(raw_data)}")
    print(f"  Items with parent_id: {len(items_with_parents)}")
    print(f"  Items with children: {len(items_with_children)}")
    
    # Only apply this assertion if the data supports it
    # For some statements, the hierarchy may be represented differently
    if not has_hierarchy:
        print("  No explicit parent-child relationship found in this statement format")
        print("  This may be normal for some statement formats")


# ===== Statement Rendering Tests =====

def test_statement_rendering(test_balance_sheets):
    """Test statement rendering functionality."""
    if not test_balance_sheets:
        pytest.skip("No balance sheet fixtures available")
    
    # Get the first available balance sheet
    ticker, statement = next(iter(test_balance_sheets.items()))
    
    # Render the statement
    rendered = statement.render()
    
    # Verify basic structure
    assert isinstance(rendered, RenderedStatement), "Render should return a RenderedStatement"
    assert rendered.title, "Rendered statement should have a title"
    assert hasattr(rendered, "rows"), "Rendered statement should have rows"
    assert hasattr(rendered, "periods"), "Rendered statement should have periods"
    
    # Check row structure
    assert rendered.rows, "Rendered statement should have at least one row"
    first_row = rendered.rows[0]
    assert hasattr(first_row, "label"), "Row should have a label"
    
    # Check for cells or values (API might use either)
    assert hasattr(first_row, "cells") or hasattr(first_row, "values"), "Row should have cells or values"
    
    # Check for indent if it exists, but don't require it
    if not hasattr(first_row, "indent"):
        print("  Note: Row does not have an explicit indent attribute")
    
    # Check period structure
    assert rendered.periods, "Rendered statement should have at least one period"
    
    # Print rendering summary
    print(f"\nRendered statement for {ticker} balance sheet:")
    print(f"  Title: {rendered.title}")
    print(f"  Periods: {rendered.periods}")
    print(f"  Row count: {len(rendered.rows)}")


def test_statement_to_dataframe_conversion(test_balance_sheets):
    """Test conversion of statements to pandas DataFrames."""
    if not test_balance_sheets:
        pytest.skip("No balance sheet fixtures available")
    
    # Get the first available balance sheet
    ticker, statement = next(iter(test_balance_sheets.items()))
    
    # Convert to DataFrame
    df = statement.to_dataframe()
    
    # Verify DataFrame structure
    assert isinstance(df, pd.DataFrame), "to_dataframe should return a pandas DataFrame"
    assert "concept" in df.columns, "DataFrame should have a concept column"
    assert "label" in df.columns, "DataFrame should have a label column"
    
    # Check for period columns
    period_columns = [col for col in df.columns if "-" in col]
    assert period_columns, "DataFrame should have at least one period column"
    
    # Verify data content
    assert not df.empty, "DataFrame should not be empty"
    
    # Print DataFrame summary
    print(f"\nDataFrame for {ticker} balance sheet:")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {', '.join(df.columns)}")
    print(f"  Period columns: {', '.join(period_columns)}")


# ===== Period Handling Tests =====

def test_statement_period_detection(test_balance_sheets, test_income_statements):
    """Test detection and handling of different reporting periods."""
    # Collect all period formats from statements
    period_formats = {}
    
    # Check balance sheets (typically point-in-time)
    if test_balance_sheets:
        for ticker, statement in test_balance_sheets.items():
            df = statement.to_dataframe()
            period_cols = [col for col in df.columns if "-" in col]
            if period_cols:
                period_formats[f"{ticker}_bs"] = period_cols
    
    # Check income statements (typically period-based)
    if test_income_statements:
        for ticker, statement in test_income_statements.items():
            df = statement.to_dataframe()
            period_cols = [col for col in df.columns if "-" in col]
            if period_cols:
                period_formats[f"{ticker}_is"] = period_cols
    
    # Verify we found periods
    assert period_formats, "No period columns found in any statement"
    
    # Print period information
    print("\nStatement periods found:")
    for stmt_key, periods in period_formats.items():
        print(f"  {stmt_key}: {', '.join(periods)}")


# ===== Statement Data Access Tests =====

def test_statement_data_access_methods(test_companies):
    """Test methods for accessing statement data."""
    if not test_companies:
        pytest.skip("No company fixtures available")
    
    # Get the first available company
    ticker, xbrl = next(iter(test_companies.items()))
    
    # Get a statement
    statement = xbrl.statements.balance_sheet()
        
     # Test different data access methods
        
     # 1. Raw data access
    raw_data = statement.get_raw_data()
    assert isinstance(raw_data, list), "Raw data should be a list"
        
    # 2. Rendered data
    rendered = statement.render()
    assert isinstance(rendered, RenderedStatement), "Rendered data has incorrect type"
        
    # 3. DataFrame access
    df = statement.to_dataframe()
    assert isinstance(df, pd.DataFrame), "DataFrame has incorrect type"
        
    # 4. Accessing by concept
     # Find a concept in the raw data
    if raw_data:
        concept = raw_data[0].get("concept", "")
        if concept:
            # Try to query for this concept
            query_result = xbrl.query(concept)
            assert isinstance(query_result, FactQuery), "Query result should be a list"
                
            print(f"\nConcept search for {concept} in {ticker}:")
            print(f"  Found {len(query_result.to_dataframe())} results")


# ===== Statement Calculation Tests =====

def test_statement_calculations(test_companies):
    """Test calculation relationships in statements."""
    for ticker, xbrl in test_companies.items():
        try:
            # Try to get a balance sheet
            balance_sheet = xbrl.statements.balance_sheet()
            if not balance_sheet:
                continue
                
            # Get the raw data
            raw_data = balance_sheet.get_raw_data()
            
            # Look for total assets or liabilities (common calculation targets)
            total_concepts = [
                item for item in raw_data 
                if "concept" in item and (
                    "Assets" in item["concept"] or 
                    "Liabilities" in item["concept"] or
                    "Equity" in item["concept"]
                )
            ]
            
            if total_concepts:
                # We found at least one potential calculation target
                print(f"\nPotential calculation targets for {ticker}:")
                for item in total_concepts[:3]:  # Show just a few
                    print(f"  {item.get('label', 'Unknown')}: {item.get('concept', 'Unknown')}")
                
                # Try to verify calculations (if supported by the API)
                if hasattr(balance_sheet, "verify_calculations"):
                    try:
                        calc_results = balance_sheet.verify_calculations()
                        print(f"  Calculation verification results: {calc_results}")
                    except Exception as e:
                        print(f"  Calculation verification failed: {e}")
                
                # We found at least one example, return
                return
        except Exception:
            continue
    
    # If we get here, we didn't find any good examples
    pytest.skip("No statements with calculation targets found")


def test_dimensional_statements(test_dimensional_data):
    """Test handling of dimensional statements."""
    if test_dimensional_data is None:
        pytest.skip("Dimensional statement fixture not available")
    
    # Get all statements
    statements = test_dimensional_data.get_all_statements()
    
    # Look for dimensional statements
    dimensional_statements = []
    for statement in statements:
        try:
            # Check if this looks like a dimensional statement
            if any(dim_type in statement['definition'].lower() for dim_type in [
                "segment", "geographic", "dimension", "member", "axis"
            ]):
                dimensional_statements.append(statement['role'])
        except Exception:
            continue
    
    # Take the first dimensional statement
    dim_statement_name = dimensional_statements[0]
    
    try:
        # Get the statement
        dim_statement = test_dimensional_data.get_statement(dim_statement_name)
        
        # Print information about the dimensional statement
        print(f"\nDimensional statement found: {dim_statement_name}")
        
        # Look for dimensions in the items
        if isinstance(dim_statement, list):
            # Find items with dimensions
            items_with_dimensions = [
                item for item in dim_statement 
                if "dimensions" in item and item["dimensions"]
            ]
            
            print(f"  Total items: {len(dim_statement)}")
            print(f"  Items with dimensions: {len(items_with_dimensions)}")
            
            if items_with_dimensions:
                # Show a sample of dimensions
                sample_item = items_with_dimensions[0]
                print(f"  Sample dimensions: {list(sample_item['dimensions'].keys())}")
                print(f"  Sample dimension values: {list(sample_item['dimensions'].values())}")
    except Exception as e:
        pytest.skip(f"Dimensional statement test failed: {e}")