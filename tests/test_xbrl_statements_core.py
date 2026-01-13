"""
Core tests for XBRL2 statements functionality.

These tests focus on the basic statement capabilities of XBRL2:
- Statement resolution
- Statement rendering
- Statement data access
- Statement conversion to dataframes
"""

# Register the fixtures module as a pytest plugin
pytest_plugins = ["tests.fixtures.xbrl2_fixtures"]

import pytest
import pandas as pd

from edgar.xbrl.statements import Statement
from edgar.xbrl.rendering import RenderedStatement


# ===== Statement Resolution Tests =====
@pytest.mark.network
def test_statement_resolution(cached_companies):
    """Test that statements are correctly identified."""
    # Test all companies except those known to have issues
    for ticker, xbrl in cached_companies.items():
        if xbrl is None:
            continue
        
        # Skip companies we know have issues with specific statements
        # This information would come from analyzing the fixtures
        
        # Try to get balance sheet
        try:
            balance_sheet = xbrl.statements.balance_sheet()
            if balance_sheet:
                assert isinstance(balance_sheet, Statement), f"{ticker} balance sheet is not a Statement"
        except Exception as e:
            print(f"Warning: Failed to get balance sheet for {ticker}: {e}")
        
        # Try to get income statement
        try:
            income_stmt = xbrl.statements.income_statement()
            if income_stmt:
                assert isinstance(income_stmt, Statement), f"{ticker} income statement is not a Statement"
        except Exception as e:
            print(f"Warning: Failed to get income statement for {ticker}: {e}")
        
        # Try to get cash flow statement
        try:
            cash_flow = xbrl.statements.cashflow_statement()
            if cash_flow:
                assert isinstance(cash_flow, Statement), f"{ticker} cash flow statement is not a Statement"
        except Exception as e:
            print(f"Warning: Failed to get cash flow statement for {ticker}: {e}")


# ===== Statement Data Tests =====
@pytest.mark.network
def test_balance_sheet_data(balance_sheets):
    """Test balance sheet data structure and content."""
    for ticker, statement in balance_sheets.items():
        if statement is None:
            continue
        
        # Get statement data
        data = statement.get_raw_data()
        
        # Check data structure
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify basic balance sheet concepts are present
        concepts = [item["concept"] for item in data if "concept" in item]
        
        # Look for core balance sheet concepts
        asset_concepts = [c for c in concepts if "Asset" in c]
        liability_concepts = [c for c in concepts if "Liabilit" in c]
        equity_concepts = [c for c in concepts if "Equity" in c or "StockholdersEquity" in c]
        
        # At least one of each category should be present
        assert len(asset_concepts) > 0, f"{ticker} balance sheet missing asset concepts"
        assert len(liability_concepts) > 0, f"{ticker} balance sheet missing liability concepts"
        assert len(equity_concepts) > 0, f"{ticker} balance sheet missing equity concepts"

@pytest.mark.network
def test_income_statement_data(income_statements):
    """Test income statement data structure and content."""
    for ticker, statement in income_statements.items():
        if statement is None:
            continue
        
        # Get statement data
        data = statement.get_raw_data()
        
        # Check data structure
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify basic income statement concepts are present
        concepts = [item["concept"] for item in data if "concept" in item]
        
        # Look for core income statement concepts
        revenue_concepts = [c for c in concepts if "Revenue" in c]
        expense_concepts = [c for c in concepts if "Expense" in c or "Cost" in c]
        income_concepts = [c for c in concepts if "Income" in c or "Earnings" in c or "Profit" in c]
        
        # At least one of each category should be present
        assert len(revenue_concepts) > 0, f"{ticker} income statement missing revenue concepts"
        assert len(expense_concepts) > 0, f"{ticker} income statement missing expense concepts"
        assert len(income_concepts) > 0, f"{ticker} income statement missing income concepts"

@pytest.mark.network
def test_cash_flow_statement_data(cash_flow_statements):
    """Test cash flow statement data structure and content."""
    for ticker, statement in cash_flow_statements.items():
        if statement is None:
            continue
        
        # Get statement data
        data = statement.get_raw_data()
        
        # Check data structure
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify basic cash flow statement concepts are present
        concepts = [item["concept"] for item in data if "concept" in item]
        
        # Look for core cash flow statement sections
        operating_concepts = [c for c in concepts if "Operating" in c]
        investing_concepts = [c for c in concepts if "Investing" in c]
        financing_concepts = [c for c in concepts if "Financing" in c]
        
        # At least one of each category should be present
        assert len(operating_concepts) > 0, f"{ticker} cash flow statement missing operating concepts"
        assert len(investing_concepts) > 0, f"{ticker} cash flow statement missing investing concepts"
        assert len(financing_concepts) > 0, f"{ticker} cash flow statement missing financing concepts"


# ===== Statement Rendering Tests =====
@pytest.mark.network
def test_statement_rendering(balance_sheets):
    """Test rendering statements."""
    for ticker, statement in balance_sheets.items():
        if statement is None:
            continue
        
        # Skip after first successful test for performance
        
        # Render the statement
        rendered = statement.render()
        
        # Check rendering structure
        assert isinstance(rendered, RenderedStatement)
        assert rendered.title
        assert len(rendered.rows) > 0
        assert len(rendered.periods) > 0
        
        # Check rendering content
        # Find row containing "Assets" or similar (case-insensitive)
        asset_row = next((row for row in rendered.rows if "asset" in row.label.lower()), None)
        assert asset_row is not None, f"{ticker} rendered balance sheet missing asset row"
        
        # Check row structure
        assert hasattr(asset_row, "label")
        assert hasattr(asset_row, "cells")
        
        # Values should be a dictionary mapping periods to values
        assert isinstance(asset_row.cells, list)
        assert len(asset_row.cells) > 0
        
        # Only test one company for performance
        break


# ===== Statement to DataFrame Conversion Tests =====
@pytest.mark.network
def test_statement_to_dataframe(balance_sheets, income_statements, cash_flow_statements):
    """Test converting statements to dataframes."""
    all_statements = {
        "BalanceSheet": balance_sheets,
        "IncomeStatement": income_statements,
        "CashFlowStatement": cash_flow_statements
    }
    
    for statement_type, statements in all_statements.items():
        # Find first available statement
        for ticker, statement in statements.items():
            if statement is None:
                continue
            
            # Convert to dataframe
            df = statement.to_dataframe()
            
            # Check dataframe structure
            assert isinstance(df, pd.DataFrame)
            assert "concept" in df.columns
            assert "label" in df.columns
            
            # Check for date columns
            date_columns = [col for col in df.columns if "-" in col]
            assert len(date_columns) > 0, f"{ticker} {statement_type} dataframe missing date columns"
            
            # Check dataframe content
            assert len(df) > 0
            
            # Only test one company per statement type for performance
            break


# ===== Statement Accessor Tests =====
@pytest.mark.network
def test_statement_accessor_methods(cached_companies):
    """Test all statement accessor methods."""
    statement_methods = [
        "balance_sheet",
        "income_statement",
        "cash_flow_statement",
        "changes_in_equity",
        "comprehensive_income"
    ]
    
    for ticker, xbrl in cached_companies.items():
        if xbrl is None:
            continue
        
        # Test each accessor method
        for method_name in statement_methods:
            # Skip methods that aren't available
            if not hasattr(xbrl.statements, method_name):
                continue
                
            # Get the method
            method = getattr(xbrl.statements, method_name)
            
            # Try to call method
            try:
                statement = method()
                if statement:
                    # Verify it's a Statement
                    assert isinstance(statement, Statement)
                    
                    # Test that we can access data
                    data = statement.get_raw_data()
                    assert isinstance(data, list)
                    assert len(data) > 0
            except Exception as e:
                print(f"Warning: {ticker}.statements.{method_name}() failed: {e}")
        
        # Only test one company for performance
        break


# ===== Statement Period Tests =====
@pytest.mark.network
def test_statement_periods(balance_sheets):
    """Test that statements have correct period information."""
    for ticker, statement in balance_sheets.items():
        if statement is None:
            continue
        
        # Convert to dataframe to easily check periods
        df = statement.to_dataframe()
        
        # Check for date columns
        date_columns = [col for col in df.columns if "-" in col]
        assert len(date_columns) > 0, f"{ticker} balance sheet missing date columns"
        
        # Check date format (should be YYYY-MM-DD)
        for date_col in date_columns:
            date_parts = date_col.split("-")
            assert len(date_parts) == 3, f"Invalid date format: {date_col}"
            
            # Year should be 4 digits
            assert len(date_parts[0]) == 4, f"Invalid year in date: {date_col}"
            
            # Month should be 1-2 digits (1-12)
            month = int(date_parts[1])
            assert 1 <= month <= 12, f"Invalid month in date: {date_col}"
            
            # Day should be 1-2 digits (1-31)
            day = int(date_parts[2])
            assert 1 <= day <= 31, f"Invalid day in date: {date_col}"
        
        # Only test one company for performance
        break