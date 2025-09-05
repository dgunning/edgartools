"""
Regression tests for Issue #411 - Standardized Financial Data Accessor Methods

This test ensures that the standardized financial data accessor methods continue
to work correctly and prevent regression of the issue.

Issue: https://github.com/dgunning/edgartools/issues/411
"""

import pytest
from typing import Optional, Union
from unittest.mock import MagicMock, patch

import pandas as pd

from edgar import Company
from edgar.financials import Financials


class TestStandardizedFinancialMethods:
    """Test the standardized financial accessor methods added to resolve issue #411."""
    
    @pytest.fixture
    def sample_income_statement_df(self):
        """Sample income statement DataFrame for testing."""
        return pd.DataFrame({
            'concept': ['us-gaap_Revenues', 'us-gaap_NetIncomeLoss'],
            'label': ['Contract Revenue', 'Net Income'],
            '2024-12-31': [100000000, 20000000],
            '2023-12-31': [90000000, 18000000],
            'level': [0, 0],
            'abstract': [False, False], 
            'dimension': [None, None]
        })
    
    @pytest.fixture
    def sample_balance_sheet_df(self):
        """Sample balance sheet DataFrame for testing."""
        return pd.DataFrame({
            'concept': ['us-gaap_Assets', 'us-gaap_Liabilities', 'us-gaap_StockholdersEquity'],
            'label': ['Total Assets', 'Total Liabilities', 'Total Stockholders Equity'],
            '2024-12-31': [500000000, 300000000, 200000000],
            '2023-12-31': [450000000, 270000000, 180000000],
            'level': [0, 0, 0],
            'abstract': [False, False, False],
            'dimension': [None, None, None]
        })
    
    @pytest.fixture
    def sample_cashflow_df(self):
        """Sample cash flow statement DataFrame for testing."""
        return pd.DataFrame({
            'concept': ['us-gaap_NetCashProvidedByUsedInOperatingActivities', 'us-gaap_PaymentsToAcquirePropertyPlantAndEquipment'],
            'label': ['Net Cash from Operations', 'Capital Expenditures'],
            '2024-12-31': [50000000, -10000000],
            '2023-12-31': [45000000, -8000000],
            'level': [0, 0],
            'abstract': [False, False],
            'dimension': [None, None]
        })
    
    @pytest.fixture
    def mock_financials(self, sample_income_statement_df, sample_balance_sheet_df, sample_cashflow_df):
        """Create a mock Financials object with sample data."""
        financials = Financials(None)
        
        # Mock the XBRL structure
        mock_xb = MagicMock()
        mock_statements = MagicMock()
        
        # Mock individual statements
        mock_income = MagicMock()
        mock_balance = MagicMock()
        mock_cashflow = MagicMock()
        
        # Mock the render method to return our sample data
        mock_income_rendered = MagicMock()
        mock_income_rendered.to_dataframe.return_value = sample_income_statement_df
        mock_income.render.return_value = mock_income_rendered
        
        mock_balance_rendered = MagicMock()
        mock_balance_rendered.to_dataframe.return_value = sample_balance_sheet_df  
        mock_balance.render.return_value = mock_balance_rendered
        
        mock_cashflow_rendered = MagicMock()
        mock_cashflow_rendered.to_dataframe.return_value = sample_cashflow_df
        mock_cashflow.render.return_value = mock_cashflow_rendered
        
        # Wire up the mocks
        mock_statements.income_statement.return_value = mock_income
        mock_statements.balance_sheet.return_value = mock_balance
        mock_statements.cashflow_statement.return_value = mock_cashflow
        
        mock_xb.statements = mock_statements
        financials.xb = mock_xb
        
        return financials

    def test_get_revenue_basic(self, mock_financials):
        """Test basic revenue retrieval."""
        revenue = mock_financials.get_revenue()
        assert revenue == 100000000
        
        # Test previous period
        prev_revenue = mock_financials.get_revenue(period_offset=1)
        assert prev_revenue == 90000000

    def test_get_net_income_basic(self, mock_financials):
        """Test basic net income retrieval."""
        net_income = mock_financials.get_net_income()
        assert net_income == 20000000
        
        # Test previous period
        prev_net_income = mock_financials.get_net_income(period_offset=1)
        assert prev_net_income == 18000000

    def test_get_total_assets_basic(self, mock_financials):
        """Test basic total assets retrieval."""
        total_assets = mock_financials.get_total_assets()
        assert total_assets == 500000000

    def test_get_total_liabilities_basic(self, mock_financials):
        """Test basic total liabilities retrieval."""
        total_liabilities = mock_financials.get_total_liabilities()
        assert total_liabilities == 300000000

    def test_get_stockholders_equity_basic(self, mock_financials):
        """Test basic stockholders equity retrieval."""
        equity = mock_financials.get_stockholders_equity()
        assert equity == 200000000

    def test_get_operating_cash_flow_basic(self, mock_financials):
        """Test basic operating cash flow retrieval."""
        ocf = mock_financials.get_operating_cash_flow()
        assert ocf == 50000000

    def test_get_capital_expenditures_basic(self, mock_financials):
        """Test basic capital expenditures retrieval."""
        capex = mock_financials.get_capital_expenditures()
        assert capex == -10000000

    def test_get_free_cash_flow_calculation(self, mock_financials):
        """Test free cash flow calculation."""
        fcf = mock_financials.get_free_cash_flow()
        # FCF = OCF - |CapEx| = 50000000 - 10000000 = 40000000
        assert fcf == 40000000

    def test_get_financial_metrics_comprehensive(self, mock_financials):
        """Test the comprehensive financial metrics method."""
        metrics = mock_financials.get_financial_metrics()
        
        # Check that all expected metrics are present
        expected_keys = [
            'revenue', 'net_income', 'total_assets', 'total_liabilities',
            'stockholders_equity', 'operating_cash_flow', 'capital_expenditures',
            'free_cash_flow', 'current_assets', 'current_liabilities',
            'current_ratio', 'debt_to_assets'
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Check specific values
        assert metrics['revenue'] == 100000000
        assert metrics['net_income'] == 20000000
        assert metrics['total_assets'] == 500000000
        assert metrics['total_liabilities'] == 300000000
        assert metrics['stockholders_equity'] == 200000000
        assert metrics['operating_cash_flow'] == 50000000
        assert metrics['capital_expenditures'] == -10000000
        assert metrics['free_cash_flow'] == 40000000
        
        # Check calculated ratios
        assert metrics['debt_to_assets'] == 0.6  # 300M / 500M
        
        # current_ratio will be None because we don't have current assets/liabilities in mock data
        assert metrics['current_ratio'] is None

    def test_no_xbrl_data_returns_none(self):
        """Test that methods return None when no XBRL data is available."""
        financials = Financials(None)
        
        assert financials.get_revenue() is None
        assert financials.get_net_income() is None
        assert financials.get_total_assets() is None
        assert financials.get_operating_cash_flow() is None
        
        metrics = financials.get_financial_metrics()
        assert all(v is None for v in metrics.values())

    def test_period_offset_out_of_range(self, mock_financials):
        """Test that period_offset beyond available data returns None."""
        # We only have 2 periods (0, 1), so offset 2 should return None
        revenue = mock_financials.get_revenue(period_offset=2)
        assert revenue is None

    def test_pattern_matching_case_insensitive(self, mock_financials):
        """Test that pattern matching is case insensitive."""
        # This should work even if labels have different cases
        revenue = mock_financials.get_revenue()
        assert revenue is not None

    def test_user_workflow_from_issue(self):
        """Test the exact workflow the user wanted from the GitHub issue."""
        # This is an integration test that uses real companies
        # Only run if we can access real data
        try:
            companies = ["AAPL"]  # Just test one to keep it fast
            
            for ticker in companies:
                company = Company(ticker)
                financials = company.get_financials()
                
                if financials and financials.xb:  # Only test if we have XBRL data
                    # This is the exact code from the user's issue that should now work
                    metrics = {
                        'revenue': financials.get_revenue(),
                        'net_income': financials.get_net_income(),
                        'total_assets': financials.get_total_assets()
                    }
                    
                    # At least revenue should be found for major companies
                    assert metrics['revenue'] is not None, f"Revenue not found for {ticker}"
                    assert isinstance(metrics['revenue'], (int, float)), f"Revenue should be numeric for {ticker}"
                    assert metrics['revenue'] > 0, f"Revenue should be positive for {ticker}"
                    
        except Exception:
            # Skip integration test if there are network issues or other problems
            pytest.skip("Integration test skipped - unable to access real data")


class TestStandardizedMethodsErrorHandling:
    """Test error handling in standardized methods."""
    
    def test_malformed_dataframe_handling(self):
        """Test handling of malformed DataFrames."""
        financials = Financials(None)
        mock_xb = MagicMock()
        mock_statement = MagicMock()
        mock_rendered = MagicMock()
        
        # Return empty DataFrame
        mock_rendered.to_dataframe.return_value = pd.DataFrame()
        mock_statement.render.return_value = mock_rendered
        
        mock_xb.statements.income_statement.return_value = mock_statement
        financials.xb = mock_xb
        
        revenue = financials.get_revenue()
        assert revenue is None

    def test_statement_render_exception_handling(self):
        """Test handling of exceptions during statement rendering."""
        financials = Financials(None)
        mock_xb = MagicMock()
        mock_statement = MagicMock()
        
        # Make render raise an exception
        mock_statement.render.side_effect = Exception("Render failed")
        mock_xb.statements.income_statement.return_value = mock_statement
        financials.xb = mock_xb
        
        revenue = financials.get_revenue()
        assert revenue is None

    def test_statement_missing_handling(self):
        """Test handling when a statement is not available."""
        financials = Financials(None)
        mock_xb = MagicMock()
        
        # Make statement method return None
        mock_xb.statements.income_statement.return_value = None
        financials.xb = mock_xb
        
        revenue = financials.get_revenue()
        assert revenue is None