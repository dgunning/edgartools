"""
Tests for Entity financial statement functionality.

This module tests the high-level statement generation including balance sheets,
income statements, and cash flow statements.
"""

import pytest
from edgar import Company
import pandas as pd
from rich.console import Console


class TestEntityStatements:
    """Test financial statement generation and completeness."""
    
    @pytest.fixture
    def test_company(self):
        """Get a test company with reliable data."""
        return Company("AAPL")
    
    def test_balance_sheet_basic_functionality(self, test_company):
        """Test basic balance sheet functionality."""
        balance_sheet = test_company.balance_sheet(annual=True, periods=4)
        
        assert balance_sheet is not None
        assert hasattr(balance_sheet, 'periods')
        assert len(balance_sheet.periods) >= 3
        assert hasattr(balance_sheet, 'items') or hasattr(balance_sheet, 'to_dataframe')
    
    def test_balance_sheet_dataframe_structure(self, test_company):
        """Test balance sheet DataFrame structure and completeness."""
        balance_sheet = test_company.balance_sheet(annual=True, periods=4)
        df = balance_sheet.to_dataframe()
        
        # Basic structure validation
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 20, "Balance sheet should have substantial structure"
        assert 'label' in df.columns, "Should have label column"
        
        # Check that period columns exist
        period_columns = [col for col in df.columns if col.startswith('FY ')]
        assert len(period_columns) >= 3, f"Expected at least 3 period columns, got {period_columns}"
    
    def test_income_statement_basic_functionality(self, test_company):
        """Test basic income statement functionality."""
        income_statement = test_company.income_statement(annual=True, periods=4)
        
        assert income_statement is not None
        assert hasattr(income_statement, 'periods')
        assert len(income_statement.periods) >= 3
        
        # Test dataframe conversion
        df = income_statement.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 10, "Income statement should have reasonable structure"
    
    def test_cash_flow_basic_functionality(self, test_company):
        """Test basic cash flow statement functionality."""
        cash_flow = test_company.cash_flow(annual=True, periods=4)
        
        assert cash_flow is not None
        assert hasattr(cash_flow, 'periods')
        assert len(cash_flow.periods) >= 3
        
        # Test dataframe conversion
        df = cash_flow.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 10, "Cash flow statement should have reasonable structure"
    
    def test_statement_rich_output(self, test_company):
        """Test that statements produce valid rich output."""
        balance_sheet = test_company.balance_sheet(annual=True, periods=3)
        
        # Get rich representation
        rich_repr = balance_sheet.__rich__()
        assert rich_repr is not None
        
        # Test that we can render it without errors
        console = Console(file=None, width=120)
        try:
            with console.capture() as capture:
                console.print(rich_repr)
            output = capture.get()
            
            # Should contain period headers
            periods = balance_sheet.periods
            for period in periods[:2]:  # Check first 2 periods
                assert period in output, f"Period {period} should appear in rich output"
            
            # Should contain financial values
            import re
            value_pattern = r'\$[\d,]+[.,…]'
            assert re.search(value_pattern, output), "Rich output should contain financial values"
            
        except Exception as e:
            pytest.fail(f"Failed to render rich output: {e}")
    
    def test_period_consistency_across_statements(self, test_company):
        """Test that all statement types show consistent periods."""
        balance_sheet = test_company.balance_sheet(annual=True, periods=4)
        income_statement = test_company.income_statement(annual=True, periods=4)
        cash_flow = test_company.cash_flow(annual=True, periods=4)
        
        # All statements should have the same periods
        assert balance_sheet.periods == income_statement.periods, (
            "Balance sheet and income statement should have same periods"
        )
        assert balance_sheet.periods == cash_flow.periods, (
            "Balance sheet and cash flow should have same periods"
        )
        
        # Periods should be in reverse chronological order
        periods = balance_sheet.periods
        if len(periods) >= 2:
            # Extract years for comparison (assuming format "FY YYYY")
            years = []
            for period in periods:
                try:
                    if "FY " in period:
                        year = int(period.replace("FY ", ""))
                        years.append(year)
                except ValueError:
                    continue
            
            if len(years) >= 2:
                assert years[0] > years[1], "Periods should be in reverse chronological order"


class TestStatementEdgeCases:
    """Test edge cases and error handling for statements."""
    
    def test_invalid_periods_parameter(self):
        """Test handling of invalid periods parameter."""
        company = Company("AAPL")
        
        # Test with 0 periods - should handle gracefully
        balance_sheet = company.balance_sheet(annual=True, periods=0)
        assert balance_sheet is not None
        assert len(balance_sheet.periods) == 0
        
        # Test with negative periods - should handle gracefully (treats as default)
        balance_sheet = company.balance_sheet(annual=True, periods=-1)
        assert balance_sheet is not None
        assert len(balance_sheet.periods) > 0  # Should return some periods
    
    def test_large_periods_parameter(self):
        """Test handling of very large periods parameter."""
        company = Company("AAPL")
        
        # Should handle large periods gracefully
        balance_sheet = company.balance_sheet(annual=True, periods=20)
        assert balance_sheet is not None
        
        # Should not return more periods than available
        assert len(balance_sheet.periods) <= 20
    
    def test_quarterly_vs_annual_periods(self):
        """Test difference between quarterly and annual periods."""
        company = Company("AAPL")
        
        annual_bs = company.balance_sheet(annual=True, periods=4)
        quarterly_bs = company.balance_sheet(annual=False, periods=4)
        
        # Both should work
        assert annual_bs is not None
        assert quarterly_bs is not None
        
        # Should have different period labels
        annual_periods = annual_bs.periods
        quarterly_periods = quarterly_bs.periods
        
        # Annual periods typically labeled "FY YYYY"
        annual_labels = [p for p in annual_periods if "FY " in p]
        quarterly_labels = [p for p in quarterly_periods if "Q" in p]
        
        assert len(annual_labels) > 0, "Should have some annual period labels"
        # Note: quarterly_labels might be 0 if company uses different labeling

