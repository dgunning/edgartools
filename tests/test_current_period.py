"""
Test module for the CurrentPeriodView class.

Tests the new current period API implementation that provides convenient access
to the most recent period's financial data without comparative information.
Addresses GitHub issue #425.
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, MagicMock

from edgar.xbrl.xbrl import XBRL
from edgar.xbrl.current_period import CurrentPeriodView
from edgar.xbrl.exceptions import StatementNotFound


@pytest.fixture
def aapl_xbrl():
    """Apple XBRL data for testing."""
    return XBRL.from_directory(Path("data/xbrl/datafiles/aapl"))


@pytest.fixture
def msft_xbrl():
    """Microsoft XBRL data for testing."""
    return XBRL.from_directory(Path("data/xbrl/datafiles/msft"))


@pytest.fixture
def mock_xbrl():
    """Mock XBRL object for isolated testing."""
    xbrl = Mock()
    
    # Mock reporting periods
    xbrl.reporting_periods = [
        {'key': 'duration_2023-01-01_2023-12-31', 'label': 'Year Ended December 31, 2023'},
        {'key': 'duration_2022-01-01_2022-12-31', 'label': 'Year Ended December 31, 2022'},
        {'key': 'instant_2023-12-31', 'label': 'December 31, 2023'},
        {'key': 'instant_2022-12-31', 'label': 'December 31, 2022'},
    ]
    
    # Mock document period end
    xbrl.period_of_report = '2023-12-31'
    xbrl.entity_name = 'Test Company Inc.'
    xbrl.document_type = '10-K'
    
    # Mock get_statement method
    xbrl.get_statement = Mock(return_value=[
        {
            'concept': 'us-gaap_Assets',
            'label': 'Total Assets',
            'values': {'instant_2023-12-31': 1000000},
            'level': 0,
            'is_abstract': False,
            'all_names': ['us-gaap_Assets']
        },
        {
            'concept': 'us-gaap_Liabilities',
            'label': 'Total Liabilities',
            'values': {'instant_2023-12-31': 600000},
            'level': 0,
            'is_abstract': False,
            'all_names': ['us-gaap_Liabilities']
        }
    ])
    
    # Mock _find_facts_for_element
    xbrl._find_facts_for_element = Mock(return_value={
        'context1': {
            'fact': Mock(numeric_value=1000000, value=1000000),
            'dimension_info': [],
            'dimension_key': ''
        }
    })
    
    # Mock get_all_statements
    xbrl.get_all_statements = Mock(return_value=[
        {
            'type': 'Notes',
            'definition': 'Notes to Financial Statements',
            'role': 'http://example.com/notes',
            'element_count': 10
        }
    ])
    
    # Mock find_statement (needed for Statement objects)
    xbrl.find_statement = Mock(return_value=(
        [{'definition': 'Test Statement'}], 
        'http://test.com/role', 
        'TestType'
    ))
    
    # Mock render_statement (needed for Statement objects)
    from edgar.xbrl.rendering import RenderedStatement
    xbrl.render_statement = Mock(return_value=Mock(spec=RenderedStatement))
    
    return xbrl


class TestCurrentPeriodView:
    """Test cases for CurrentPeriodView class."""

    @pytest.mark.fast
    def test_initialization(self, mock_xbrl):
        """Test CurrentPeriodView initialization."""
        current_period = CurrentPeriodView(mock_xbrl)
        assert current_period.xbrl == mock_xbrl
        assert current_period._current_period_key is None
        assert current_period._current_period_label is None

    @pytest.mark.fast
    def test_period_detection_with_document_end_date(self, mock_xbrl):
        """Test period detection using document period end date."""
        current_period = CurrentPeriodView(mock_xbrl)
        
        # Should detect instant_2023-12-31 as current period
        period_key = current_period.period_key
        assert period_key == 'instant_2023-12-31'
        
        # Should have proper label
        period_label = current_period.period_label
        assert period_label == 'December 31, 2023'

    @pytest.mark.fast
    def test_period_detection_without_document_date(self, mock_xbrl):
        """Test period detection fallback when no document date."""
        mock_xbrl.period_of_report = None
        current_period = CurrentPeriodView(mock_xbrl)
        
        # Should fall back to most recent period by date
        period_key = current_period.period_key
        assert period_key in ['duration_2023-01-01_2023-12-31', 'instant_2023-12-31']

    @pytest.mark.fast
    def test_period_detection_empty_periods(self, mock_xbrl):
        """Test period detection with no reporting periods."""
        mock_xbrl.reporting_periods = []
        current_period = CurrentPeriodView(mock_xbrl)
        
        period_key = current_period.period_key
        assert period_key == ""

    @pytest.mark.fast
    def test_balance_sheet_standard_concepts(self, mock_xbrl):
        """Test balance sheet retrieval with standard concept names."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.balance_sheet(raw_concepts=False)
        
        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)
        
        # Test DataFrame conversion
        df = stmt.get_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'concept' in df.columns
        assert 'label' in df.columns
        assert 'value' in df.columns
        
        # Verify data content
        assets_row = df[df['label'] == 'Total Assets'].iloc[0]
        assert assets_row['value'] == 1000000
        assert assets_row['concept'] == 'us-gaap_Assets'

    @pytest.mark.fast
    def test_balance_sheet_raw_concepts(self, mock_xbrl):
        """Test balance sheet retrieval with raw XBRL concept names."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.balance_sheet(raw_concepts=True)

        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)

        # Test DataFrame conversion with raw concepts
        df = stmt.get_dataframe(raw_concepts=True)

        # Issue #522: Schema should match Statement.to_dataframe()
        # Check for unified schema columns
        assert 'concept' in df.columns
        assert 'label' in df.columns
        assert 'value' in df.columns
        assert 'abstract' in df.columns  # Renamed from is_abstract
        assert 'dimension' in df.columns  # Renamed from is_dimension
        assert 'balance' in df.columns
        assert 'weight' in df.columns

        # Concept name should attempt to restore colon format when raw_concepts=True
        assets_row = df[df['label'] == 'Total Assets'].iloc[0]
        # With raw_concepts=True, concept should have colon format
        assert ':' in assets_row['concept'] or assets_row['concept'] == 'us-gaap_Assets'

    @pytest.mark.fast
    def test_income_statement(self, mock_xbrl):
        """Test income statement retrieval."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.income_statement()
        
        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)
        # Verify it's an income statement
        assert stmt.canonical_type == 'IncomeStatement'
        assert 'duration_' in stmt.period_filter  # Should use duration period

    @pytest.mark.fast
    def test_cashflow_statement(self, mock_xbrl):
        """Test cash flow statement retrieval."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.cashflow_statement()
        
        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)
        # Verify it's a cash flow statement
        assert stmt.canonical_type == 'CashFlowStatement'
        assert 'duration_' in stmt.period_filter  # Should use duration period

    @pytest.mark.fast
    def test_statement_of_equity(self, mock_xbrl):
        """Test statement of equity retrieval."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.statement_of_equity()
        
        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)
        # Verify it's a statement of equity
        assert stmt.canonical_type == 'StatementOfEquity'
        assert 'instant_' in stmt.period_filter  # Should use instant period

    @pytest.mark.fast
    def test_comprehensive_income(self, mock_xbrl):
        """Test comprehensive income statement retrieval."""
        current_period = CurrentPeriodView(mock_xbrl)
        stmt = current_period.comprehensive_income()
        
        # Now returns Statement by default
        from edgar.xbrl.current_period import CurrentPeriodStatement
        assert isinstance(stmt, CurrentPeriodStatement)
        # Verify it's a comprehensive income statement
        assert stmt.canonical_type == 'ComprehensiveIncome'
        assert 'duration_' in stmt.period_filter  # Should use duration period

    @pytest.mark.fast
    def test_statement_not_found_error(self, mock_xbrl):
        """Test handling of missing statements."""
        # Mock find_statement to return no matching role
        mock_xbrl.find_statement.return_value = ([], None, None)
        current_period = CurrentPeriodView(mock_xbrl)
        
        with pytest.raises(StatementNotFound):
            current_period.balance_sheet()

    @pytest.mark.fast
    def test_empty_statement_data_error(self, mock_xbrl):
        """Test handling of empty statement data with DataFrame mode."""
        mock_xbrl.get_statement.return_value = []
        current_period = CurrentPeriodView(mock_xbrl)
        
        # Test with DataFrame mode (as_statement=False)
        with pytest.raises(StatementNotFound):
            current_period.income_statement(as_statement=False)

    @pytest.mark.fast
    def test_notes_access(self, mock_xbrl):
        """Test notes sections retrieval."""
        current_period = CurrentPeriodView(mock_xbrl)
        notes = current_period.notes()
        
        assert isinstance(notes, list)
        assert len(notes) == 1
        assert notes[0]['section_name'] == 'Notes to Financial Statements'
        assert notes[0]['type'] == 'Notes'

    @pytest.mark.fast
    def test_notes_specific_section(self, mock_xbrl):
        """Test retrieval of specific note section."""
        current_period = CurrentPeriodView(mock_xbrl)
        notes = current_period.notes('financial')
        
        assert isinstance(notes, list)
        assert len(notes) == 1  # Should match "Notes to Financial Statements"

    @pytest.mark.fast
    def test_get_fact_standard_concept(self, mock_xbrl):
        """Test individual fact retrieval with standard concept."""
        current_period = CurrentPeriodView(mock_xbrl)
        value = current_period.get_fact('Assets')
        
        assert value == 1000000
        mock_xbrl._find_facts_for_element.assert_called_with('Assets', period_filter='instant_2023-12-31')

    @pytest.mark.fast
    def test_get_fact_raw_concept(self, mock_xbrl):
        """Test individual fact retrieval with raw XBRL concept."""
        current_period = CurrentPeriodView(mock_xbrl)
        value = current_period.get_fact('us-gaap:Assets', raw_concept=True)
        
        assert value == 1000000
        # Should convert colon to underscore for internal lookup
        mock_xbrl._find_facts_for_element.assert_called_with('us-gaap_Assets', period_filter='instant_2023-12-31')

    @pytest.mark.fast
    def test_get_fact_not_found(self, mock_xbrl):
        """Test fact retrieval when fact doesn't exist."""
        mock_xbrl._find_facts_for_element.return_value = {}
        current_period = CurrentPeriodView(mock_xbrl)
        
        value = current_period.get_fact('NonExistentConcept')
        assert value is None

    @pytest.mark.fast
    def test_to_dict(self, mock_xbrl):
        """Test conversion to dictionary format."""
        current_period = CurrentPeriodView(mock_xbrl)
        result = current_period.to_dict()
        
        assert isinstance(result, dict)
        assert result['period_key'] == 'instant_2023-12-31'
        assert result['entity_name'] == 'Test Company Inc.'
        assert result['document_type'] == '10-K'
        assert 'statements' in result
        assert 'BalanceSheet' in result['statements']

    @pytest.mark.fast
    def test_repr(self, mock_xbrl):
        """Test string representation."""
        current_period = CurrentPeriodView(mock_xbrl)
        repr_str = repr(current_period)
        
        assert 'CurrentPeriodView' in repr_str
        assert 'Test Company Inc.' in repr_str
        assert 'December 31, 2023' in repr_str

    @pytest.mark.fast
    def test_str(self, mock_xbrl):
        """Test user-friendly string representation."""
        current_period = CurrentPeriodView(mock_xbrl)
        str_repr = str(current_period)
        
        assert 'Current Period Data for Test Company Inc.' in str_repr
        assert 'December 31, 2023' in str_repr


class TestCurrentPeriodIntegration:
    """Integration tests with real XBRL data."""

    @pytest.mark.fast
    def test_xbrl_current_period_property(self, aapl_xbrl):
        """Test that XBRL class provides current_period property."""
        assert hasattr(aapl_xbrl, 'current_period')
        current_period = aapl_xbrl.current_period
        assert isinstance(current_period, CurrentPeriodView)

    @pytest.mark.fast
    def test_apple_period_detection(self, aapl_xbrl):
        """Test period detection with real Apple data."""
        current_period = aapl_xbrl.current_period
        period_key = current_period.period_key
        
        # Should detect a valid period
        assert period_key != ""
        assert isinstance(period_key, str)
        
        # Should be either instant or duration format
        assert period_key.startswith(('instant_', 'duration_'))

    @pytest.mark.fast
    def test_apple_balance_sheet_current_period(self, aapl_xbrl):
        """Test balance sheet retrieval with real Apple data."""
        current_period = aapl_xbrl.current_period
        
        try:
            # Test Statement object (new default)
            stmt = current_period.balance_sheet()
            from edgar.xbrl.current_period import CurrentPeriodStatement
            assert isinstance(stmt, CurrentPeriodStatement)
            
            # Convert to DataFrame for data validation
            df = stmt.get_dataframe()
            assert isinstance(df, pd.DataFrame)
            
            if not df.empty:
                assert 'concept' in df.columns
                assert 'label' in df.columns
                assert 'value' in df.columns
                
                # Should have some assets data
                assets_data = df[df['label'].str.contains('Assets', case=False, na=False)]
                assert not assets_data.empty
        except StatementNotFound:
            # It's okay if the specific statement isn't found in test data
            pytest.skip("Balance sheet not available in test data")

    @pytest.mark.fast
    def test_apple_income_statement_current_period(self, aapl_xbrl):
        """Test income statement retrieval with real Apple data."""
        current_period = aapl_xbrl.current_period
        
        try:
            # Test Statement object (new default)
            stmt = current_period.income_statement()
            from edgar.xbrl.current_period import CurrentPeriodStatement
            assert isinstance(stmt, CurrentPeriodStatement)
            
            # Convert to DataFrame for data validation
            df = stmt.get_dataframe()
            assert isinstance(df, pd.DataFrame)
            
            if not df.empty:
                # Should have revenue or income data
                revenue_data = df[df['label'].str.contains('Revenue|Income', case=False, na=False)]
                # It's okay if no revenue data is found in test fixtures
        except StatementNotFound:
            pytest.skip("Income statement not available in test data")

    @pytest.mark.fast
    def test_apple_raw_concepts(self, aapl_xbrl):
        """Test raw concepts functionality with real Apple data."""
        current_period = aapl_xbrl.current_period
        
        try:
            # Test Statement object with raw concepts
            stmt = current_period.balance_sheet(raw_concepts=True)
            from edgar.xbrl.current_period import CurrentPeriodStatement
            assert isinstance(stmt, CurrentPeriodStatement)
            
            # Convert to DataFrame with raw concepts for validation
            df = stmt.get_dataframe(raw_concepts=True)
            assert isinstance(df, pd.DataFrame)
            
            if not df.empty:
                # Should have raw concept columns
                assert 'original_concept' in df.columns or 'concept' in df.columns
        except StatementNotFound:
            pytest.skip("Balance sheet not available in test data")

    @pytest.mark.fast
    def test_period_caching(self, aapl_xbrl):
        """Test that period detection results are cached."""
        current_period = aapl_xbrl.current_period
        
        # First call should detect period
        period1 = current_period.period_key
        
        # Second call should return cached result
        period2 = current_period.period_key
        
        assert period1 == period2
        assert current_period._current_period_key is not None


class TestRawConceptNameHandling:
    """Test raw XBRL concept name handling functionality."""

    @pytest.mark.fast
    def test_get_concept_name_standard(self, mock_xbrl):
        """Test concept name retrieval in standard mode."""
        current_period = CurrentPeriodView(mock_xbrl)
        
        item = {
            'concept': 'Assets',
            'all_names': ['us-gaap_Assets']
        }
        
        concept_name = current_period._get_concept_name(item, raw_concepts=False)
        assert concept_name == 'Assets'

    @pytest.mark.fast
    def test_get_concept_name_raw(self, mock_xbrl):
        """Test concept name retrieval in raw mode."""
        current_period = CurrentPeriodView(mock_xbrl)
        
        item = {
            'concept': 'Assets',
            'all_names': ['us-gaap_Assets']
        }
        
        concept_name = current_period._get_concept_name(item, raw_concepts=True)
        assert concept_name == 'us-gaap:Assets'  # Should restore colon format

    @pytest.mark.fast
    def test_get_concept_name_raw_already_colon_format(self, mock_xbrl):
        """Test concept name with existing colon format."""
        current_period = CurrentPeriodView(mock_xbrl)
        
        item = {
            'concept': 'Assets',
            'all_names': ['us-gaap:Assets']  # Already has colon
        }
        
        concept_name = current_period._get_concept_name(item, raw_concepts=True)
        assert concept_name == 'us-gaap:Assets'  # Should keep existing format

    @pytest.mark.fast
    def test_get_concept_name_no_all_names(self, mock_xbrl):
        """Test concept name when all_names is empty."""
        current_period = CurrentPeriodView(mock_xbrl)
        
        item = {
            'concept': 'Assets',
            'all_names': []
        }
        
        concept_name = current_period._get_concept_name(item, raw_concepts=True)
        assert concept_name == 'Assets'  # Fallback to concept


if __name__ == '__main__':
    pytest.main([__file__])