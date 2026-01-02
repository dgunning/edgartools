#!/usr/bin/env python3
"""
Regression test for GitHub issue #429: income_statement() and cashflow_statement() 
returning empty or incomplete data in version 4.11.0

This test ensures that the CurrentPeriodView correctly selects appropriate 
periods for different statement types:
- Balance sheet: instant periods (point in time)
- Income/Cash flow: duration periods (period of time)
"""

import unittest
import pytest
import edgar
from edgar.xbrl.current_period import CurrentPeriodView


@pytest.mark.regression  
class TestIssue429StatementPeriodRegression(unittest.TestCase):
    """
    Regression tests for issue #429 - statement period selection fix
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.aapl = edgar.Company("AAPL")
        cls.filing = cls.aapl.get_filings(form="10-K").latest()
        cls.xbrl = cls.filing.xbrl()
        cls.current_period = cls.xbrl.current_period
    
    @pytest.mark.regression
    def test_period_selection_method_exists(self):
        """Test that the period selection method exists"""
        self.assertTrue(hasattr(self.current_period, '_get_appropriate_period_for_statement'))
    
    @pytest.mark.regression
    def test_balance_sheet_uses_instant_period(self):
        """Test that balance sheet uses instant periods"""
        period = self.current_period._get_appropriate_period_for_statement('BalanceSheet')
        self.assertTrue(period.startswith('instant_'), 
                       f"BalanceSheet should use instant period, got: {period}")
    
    @pytest.mark.regression
    def test_income_statement_uses_duration_period(self):
        """Test that income statement uses duration periods"""
        period = self.current_period._get_appropriate_period_for_statement('IncomeStatement')
        self.assertTrue(period.startswith('duration_'), 
                       f"IncomeStatement should use duration period, got: {period}")
    
    @pytest.mark.regression
    def test_cashflow_statement_uses_duration_period(self):
        """Test that cash flow statement uses duration periods"""
        period = self.current_period._get_appropriate_period_for_statement('CashFlowStatement')
        self.assertTrue(period.startswith('duration_'), 
                       f"CashFlowStatement should use duration period, got: {period}")
    
    @pytest.mark.regression
    def test_statement_equity_uses_instant_period(self):
        """Test that statement of equity uses instant periods"""
        period = self.current_period._get_appropriate_period_for_statement('StatementOfEquity')
        self.assertTrue(period.startswith('instant_'), 
                       f"StatementOfEquity should use instant period, got: {period}")
    
    @pytest.mark.regression
    def test_comprehensive_income_uses_duration_period(self):
        """Test that comprehensive income uses duration periods"""
        period = self.current_period._get_appropriate_period_for_statement('ComprehensiveIncome')
        self.assertTrue(period.startswith('duration_'), 
                       f"ComprehensiveIncome should use duration period, got: {period}")
    
    @pytest.mark.regression
    def test_balance_sheet_returns_data(self):
        """Test that balance sheet returns meaningful data"""
        # Get Statement object (new default) and convert to DataFrame for testing
        stmt = self.current_period.balance_sheet()
        df = stmt.get_dataframe()
        self.assertGreater(len(df), 10, "Balance sheet should have more than 20 rows")
        
        # Check for typical balance sheet items
        labels = df['label'].str.lower()
        self.assertTrue(any('cash' in label for label in labels), 
                       "Balance sheet should contain cash items")
        self.assertTrue(any('asset' in label for label in labels), 
                       "Balance sheet should contain asset items")
    
    @pytest.mark.regression
    def test_income_statement_returns_data(self):
        """Test that income statement returns meaningful data (this was the main bug)

        Note: As of v5.7.0, include_dimensions defaults to False, so fewer rows.
        """
        # Get Statement object (new default) and convert to DataFrame for testing
        stmt = self.current_period.income_statement()
        df = stmt.get_dataframe()
        self.assertGreater(len(df), 15,
                          f"Income statement should have more than 15 rows, got {len(df)}")
        
        # Check for typical income statement items
        labels = df['label'].str.lower()
        print(labels.tolist())
        revenue_items = any('cost of sales' in label or 'products' in label for label in labels)
        self.assertTrue(revenue_items, "Income statement should contain revenue items")
    
    @pytest.mark.regression
    def test_cashflow_statement_returns_data(self):
        """Test that cash flow statement returns meaningful data (this was the main bug)"""
        # Get Statement object (new default) and convert to DataFrame for testing
        stmt = self.current_period.cashflow_statement()
        df = stmt.get_dataframe()
        self.assertGreater(len(df), 20, 
                          f"Cash flow statement should have more than 20 rows, got {len(df)}")
        
        # Check for typical cash flow items
        labels = df['label'].str.lower()
        operating_items = any('operating' in label or 'net income' in label for label in labels)
        self.assertTrue(operating_items, "Cash flow statement should contain operating items")
    
    @pytest.mark.regression
    def test_unknown_statement_type_fallback(self):
        """Test that unknown statement types fall back to current period"""
        period = self.current_period._get_appropriate_period_for_statement('UnknownStatementType')
        self.assertEqual(period, self.current_period.period_key,
                        "Unknown statement types should use current period as fallback")
    
    @pytest.mark.regression
    def test_issue_429_reproduction(self):
        """
        Reproduce the exact issue from GitHub issue #429:
        - balance_sheet() should return ~30 rows (working)
        - income_statement() should NOT be empty (was broken)
        - cashflow_statement() should return more than 2 rows (was broken)
        """
        # Get Statement objects (new default) and convert to DataFrames for testing
        balance_sheet_stmt = self.current_period.balance_sheet()
        income_statement_stmt = self.current_period.income_statement()
        cash_flow_stmt = self.current_period.cashflow_statement()
        
        balance_sheet = balance_sheet_stmt.get_dataframe()
        income_statement = income_statement_stmt.get_dataframe()
        cash_flow = cash_flow_stmt.get_dataframe()
        
        # Issue reproduction assertions
        self.assertGreater(len(balance_sheet), 25, 
                          "Balance sheet should have around 30 rows (this was working)")
        self.assertGreater(len(income_statement), 0, 
                          "Income statement should NOT be empty (this was the main bug)")
        self.assertGreater(len(cash_flow), 2, 
                          "Cash flow should have more than 2 rows (this was broken)")
        
        # Verify we actually have meaningful data, not just empty rows
        income_values = income_statement[income_statement['value'].notna()]
        cashflow_values = cash_flow[cash_flow['value'].notna()]
        
        self.assertGreater(len(income_values), 10, 
                          "Income statement should have meaningful values")
        self.assertGreater(len(cashflow_values), 10, 
                          "Cash flow statement should have meaningful values")


class TestCurrentPeriodViewPeriodSelection(unittest.TestCase):
    """
    Unit tests specifically for the period selection logic
    """
    
    def setUp(self):
        """Set up test fixtures"""
        self.aapl = edgar.Company("AAPL")
        self.filing = self.aapl.get_filings(form="10-K").latest()
        self.current_period = self.filing.xbrl().current_period
    
    @pytest.mark.regression
    def test_period_selection_consistency(self):
        """Test that period selection is consistent across calls"""
        balance_period_1 = self.current_period._get_appropriate_period_for_statement('BalanceSheet')
        balance_period_2 = self.current_period._get_appropriate_period_for_statement('BalanceSheet')
        
        self.assertEqual(balance_period_1, balance_period_2,
                        "Period selection should be consistent")
        
        income_period_1 = self.current_period._get_appropriate_period_for_statement('IncomeStatement')
        income_period_2 = self.current_period._get_appropriate_period_for_statement('IncomeStatement')
        
        self.assertEqual(income_period_1, income_period_2,
                        "Period selection should be consistent")
    
    @pytest.mark.regression
    def test_period_selection_correctness(self):
        """Test that the correct periods are selected based on statement type"""
        # Get the periods for verification
        balance_period = self.current_period._get_appropriate_period_for_statement('BalanceSheet')
        income_period = self.current_period._get_appropriate_period_for_statement('IncomeStatement')
        cashflow_period = self.current_period._get_appropriate_period_for_statement('CashFlowStatement')
        
        # Balance sheet should use instant, others should use duration
        self.assertTrue(balance_period.startswith('instant_'))
        self.assertTrue(income_period.startswith('duration_'))
        self.assertTrue(cashflow_period.startswith('duration_'))
        
        # Income and cashflow should use the same period (duration ending same date)
        self.assertEqual(income_period, cashflow_period,
                        "Income and cashflow statements should use same duration period")


if __name__ == '__main__':
    unittest.main()