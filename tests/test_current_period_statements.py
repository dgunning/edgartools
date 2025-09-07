"""Tests for CurrentPeriod Statement object support (issue #429 follow-up)"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock

from edgar.xbrl.current_period import CurrentPeriodView, CurrentPeriodStatement
from edgar.xbrl.exceptions import StatementNotFound
from edgar.xbrl.rendering import RenderedStatement


class TestCurrentPeriodStatementObjects:
    """Test Statement object support in CurrentPeriodView"""
    
    def test_balance_sheet_returns_statement_object(self):
        """Test that balance_sheet(as_statement=True) returns CurrentPeriodStatement"""
        # Create mock XBRL
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [{'key': 'instant_2024-12-31', 'label': 'December 31, 2024'}]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.entity_name = 'Test Company'
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Balance Sheet'}], 
            'http://test.com/BalanceSheet', 
            'BalanceSheet'
        )
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)
        
        # Create CurrentPeriodView
        current = CurrentPeriodView(mock_xbrl)
        
        # Test as_statement=True
        stmt = current.balance_sheet(as_statement=True)
        
        assert isinstance(stmt, CurrentPeriodStatement)
        assert stmt.canonical_type == 'BalanceSheet'
        assert stmt.period_filter == 'instant_2024-12-31'
        assert stmt.period_label == 'December 31, 2024'
    
    def test_balance_sheet_returns_statement_by_default(self):
        """Test that balance_sheet() returns Statement by default"""
        # Create mock XBRL with statement data
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [{'key': 'instant_2024-12-31', 'label': 'December 31, 2024'}]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Balance Sheet'}], 
            'http://test.com/BalanceSheet', 
            'BalanceSheet'
        )
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)
        
        current = CurrentPeriodView(mock_xbrl)
        
        # Test default behavior - should return Statement now
        stmt = current.balance_sheet()
        
        assert isinstance(stmt, CurrentPeriodStatement)
        assert stmt.canonical_type == 'BalanceSheet'
    
    def test_income_statement_period_selection(self):
        """Test that income statement uses appropriate duration period"""
        # Mock XBRL with instant and duration periods
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [
            {'key': 'instant_2024-12-31', 'label': 'December 31, 2024'},
            {'key': 'duration_2024-01-01_2024-12-31', 'label': 'Year Ended December 31, 2024', 'period_type': 'Annual'}
        ]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Income Statement'}], 
            'http://test.com/IncomeStatement', 
            'IncomeStatement'
        )
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)
        
        current = CurrentPeriodView(mock_xbrl)
        
        # Test that IncomeStatement uses duration period
        stmt = current.income_statement(as_statement=True)
        
        assert stmt.period_filter == 'duration_2024-01-01_2024-12-31'
    
    def test_statement_object_methods(self):
        """Test CurrentPeriodStatement methods work correctly"""
        # Create mock XBRL and statement
        mock_xbrl = Mock()
        mock_xbrl.entity_name = 'Test Company'
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)
        
        # Mock the underlying Statement
        mock_statement = Mock()
        mock_statement.get_raw_data.return_value = [
            {
                'concept': 'us-gaap_Assets',
                'label': 'Total Assets',
                'values': {'instant_2024-12-31': 1000000},
                'level': 1,
                'is_abstract': False,
                'all_names': ['us-gaap_Assets']
            }
        ]
        mock_statement.calculate_ratios.return_value = {'current_ratio': 2.5}
        
        # Create CurrentPeriodStatement
        stmt = CurrentPeriodStatement(
            mock_xbrl,
            'BalanceSheet',
            canonical_type='BalanceSheet',
            period_filter='instant_2024-12-31',
            period_label='December 31, 2024'
        )
        stmt._statement = mock_statement
        
        # Test methods
        raw_data = stmt.get_raw_data()
        assert len(raw_data) == 1
        
        ratios = stmt.calculate_ratios()
        assert ratios['current_ratio'] == 2.5
        
        # Test get_dataframe
        df = stmt.get_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]['concept'] == 'us-gaap_Assets'
        assert df.iloc[0]['value'] == 1000000
    
    def test_get_dataframe_with_raw_concepts(self):
        """Test get_dataframe with raw_concepts=True"""
        mock_xbrl = Mock()
        mock_xbrl.entity_name = 'Test Company'
        
        mock_statement = Mock()
        mock_statement.get_raw_data.return_value = [
            {
                'concept': 'Assets',
                'label': 'Total Assets',
                'values': {'instant_2024-12-31': 1000000},
                'level': 1,
                'is_abstract': False,
                'all_names': ['us-gaap_Assets']
            }
        ]
        
        stmt = CurrentPeriodStatement(
            mock_xbrl,
            'BalanceSheet',
            canonical_type='BalanceSheet',
            period_filter='instant_2024-12-31',
            period_label='December 31, 2024'
        )
        stmt._statement = mock_statement
        
        # Test with raw_concepts=True
        df = stmt.get_dataframe(raw_concepts=True)
        assert df.iloc[0]['concept'] == 'us-gaap:Assets'  # Should convert underscore to colon
        assert 'original_concept' in df.columns
        assert df.iloc[0]['original_concept'] == 'us-gaap_Assets'
    
    def test_debug_info_method(self):
        """Test debug_info method provides useful debugging information"""
        # Create mock XBRL
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [
            {'key': 'instant_2024-12-31', 'label': 'December 31, 2024'},
            {'key': 'duration_2024-01-01_2024-12-31', 'label': 'Year Ended December 31, 2024'}
        ]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.entity_name = 'Test Company'
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_Assets',
                'values': {'instant_2024-12-31': 1000000}
            }
        ]
        
        current = CurrentPeriodView(mock_xbrl)
        
        debug_info = current.debug_info()
        
        # Check structure
        assert 'current_period_key' in debug_info
        assert 'current_period_label' in debug_info
        assert 'total_reporting_periods' in debug_info
        assert 'entity_name' in debug_info
        assert 'periods' in debug_info
        assert 'statements' in debug_info
        
        # Check content
        assert debug_info['entity_name'] == 'Test Company'
        assert debug_info['total_reporting_periods'] == 2
        assert len(debug_info['periods']) == 2
        assert 'BalanceSheet' in debug_info['statements']
        assert 'IncomeStatement' in debug_info['statements']
        assert 'CashFlowStatement' in debug_info['statements']
    
    def test_error_handling_for_missing_statements(self):
        """Test error handling when statements are not found"""
        # Create mock XBRL that will raise StatementNotFound
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [{'key': 'instant_2024-12-31', 'label': 'December 31, 2024'}]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.entity_name = 'Test Company'
        mock_xbrl.find_statement.side_effect = StatementNotFound(
            statement_type='BalanceSheet',
            confidence=0.0,
            found_statements=[],
            entity_name='Test Company',
            reason='Test error'
        )
        
        current = CurrentPeriodView(mock_xbrl)
        
        # Should raise StatementNotFound
        with pytest.raises(StatementNotFound):
            current.balance_sheet(as_statement=True)
    
    def test_all_statement_methods_support_as_statement(self):
        """Test that all statement methods support as_statement parameter"""
        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [{'key': 'instant_2024-12-31', 'label': 'December 31, 2024'}]
        mock_xbrl.period_of_report = '2024-12-31'
        mock_xbrl.find_statement.return_value = ([{'definition': 'Test'}], 'http://test.com', 'TestType')
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'test_concept',
                'label': 'Test Label',
                'values': {'instant_2024-12-31': 100},
                'level': 1,
                'is_abstract': False
            }
        ]
        
        current = CurrentPeriodView(mock_xbrl)
        
        # Test all methods have as_statement parameter
        methods = [
            'balance_sheet',
            'income_statement', 
            'cashflow_statement',
            'statement_of_equity',
            'comprehensive_income'
        ]
        
        for method_name in methods:
            method = getattr(current, method_name)
            
            # Should work with as_statement=True
            stmt = method(as_statement=True)
            assert isinstance(stmt, CurrentPeriodStatement)
            
            # Should work with as_statement=False (to get DataFrame)
            result = method(as_statement=False)
            assert isinstance(result, pd.DataFrame)


class TestCurrentPeriodStatementClass:
    """Direct tests for CurrentPeriodStatement class"""
    
    def test_string_representations(self):
        """Test __repr__ and __str__ methods"""
        mock_xbrl = Mock()
        mock_xbrl.entity_name = 'Test Company'
        mock_xbrl.render_statement.return_value = "Rendered Table"
        
        stmt = CurrentPeriodStatement(
            mock_xbrl,
            'BalanceSheet',
            canonical_type='BalanceSheet',
            period_filter='instant_2024-12-31',
            period_label='December 31, 2024'
        )
        
        # Test __repr__ now returns rich-rendered content (after rich changes)
        repr_str = repr(stmt)
        assert "Rendered Table" in repr_str  # Should contain the rendered table
        
        # Test __str__ also returns rich-rendered content 
        str_result = str(stmt)
        assert "Rendered Table" in str_result
        
        # Test that both __repr__ and __str__ return the same rich content
        assert repr_str == str_result
    
    def test_render_method(self):
        """Test render method passes parameters correctly"""
        mock_xbrl = Mock()
        mock_rendered = Mock(spec=RenderedStatement)
        mock_xbrl.render_statement.return_value = mock_rendered
        
        stmt = CurrentPeriodStatement(
            mock_xbrl,
            'BalanceSheet',
            canonical_type='BalanceSheet',
            period_filter='instant_2024-12-31',
            period_label='December 31, 2024'
        )
        
        # Test render with parameters
        result = stmt.render(standard=False, show_date_range=True, include_dimensions=False)
        
        # Check that render_statement was called with correct parameters
        mock_xbrl.render_statement.assert_called_once_with(
            'BalanceSheet',
            period_filter='instant_2024-12-31',
            standard=False,
            show_date_range=True,
            include_dimensions=False
        )
        assert result == mock_rendered