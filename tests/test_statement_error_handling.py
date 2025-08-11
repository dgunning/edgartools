"""Test improved error handling for statement resolution failures."""
import pytest
from unittest.mock import patch, MagicMock
from edgar.xbrl.statements import Statements
from edgar.xbrl.xbrl import XBRL


def test_income_statement_handles_low_confidence_error():
    """Test that income_statement returns None when statement resolution fails."""
    
    # Create a mock XBRL object that will raise an exception
    mock_xbrl = MagicMock()
    mock_xbrl.entity_name = "Test Company"
    mock_xbrl.cik = "1234567"
    mock_xbrl.period_of_report = "2024-12-31"
    
    # Mock find_statement to raise ValueError (low confidence)
    mock_xbrl.find_statement.side_effect = ValueError(
        "Low confidence match for type 'IncomeStatement': 0.10. Found statements: ['Cover']"
    )
    
    # Create Statements instance
    statements = Statements(mock_xbrl)
    
    # Should return None instead of raising exception
    with patch('edgar.core.log') as mock_log:
        result = statements.income_statement()
        
        # Should return None
        assert result is None
        
        # Should log warning with detailed context
        mock_log.warning.assert_called_once()
        warning_message = mock_log.warning.call_args[0][0]
        assert "Failed to resolve incomestatement for Test Company" in warning_message
        assert "CIK: 1234567" in warning_message
        assert "Period: 2024-12-31" in warning_message
        assert "ValueError: Low confidence match" in warning_message


def test_balance_sheet_handles_general_exception():
    """Test that balance_sheet returns None when any exception occurs."""
    
    # Create a mock XBRL object that will raise an exception
    mock_xbrl = MagicMock()
    mock_xbrl.entity_name = "Another Test Company"
    mock_xbrl.cik = "7654321"
    mock_xbrl.period_of_report = "2024-09-30"
    
    # Mock find_statement to raise a general exception
    mock_xbrl.find_statement.side_effect = RuntimeError("Unexpected error")
    
    # Create Statements instance
    statements = Statements(mock_xbrl)
    
    # Mock find_statement_by_primary_concept to also fail
    with patch.object(statements, 'find_statement_by_primary_concept', return_value=None):
        # Should return None instead of raising exception
        with patch('edgar.core.log') as mock_log:
            result = statements.balance_sheet()
            
            # Should return None
            assert result is None
            
            # Should log warning with detailed context
            mock_log.warning.assert_called_once()
            warning_message = mock_log.warning.call_args[0][0]
            assert "Failed to resolve balancesheet for Another Test Company" in warning_message
            assert "CIK: 7654321" in warning_message
            assert "Period: 2024-09-30" in warning_message
            assert "RuntimeError: Unexpected error" in warning_message


def test_cashflow_statement_handles_missing_attributes():
    """Test error handling when XBRL object is missing expected attributes."""
    
    # Create a mock XBRL object with missing attributes
    mock_xbrl = MagicMock()
    # Remove attributes to test fallback to 'Unknown'
    del mock_xbrl.entity_name
    del mock_xbrl.cik
    del mock_xbrl.period_of_report
    
    # Mock find_statement to raise an exception
    mock_xbrl.find_statement.side_effect = KeyError("Missing key")
    
    # Create Statements instance
    statements = Statements(mock_xbrl)
    
    # Should return None and handle missing attributes gracefully
    with patch('edgar.core.log') as mock_log:
        result = statements.cashflow_statement()
        
        # Should return None
        assert result is None
        
        # Should log warning with 'Unknown' values for missing attributes
        mock_log.warning.assert_called_once()
        warning_message = mock_log.warning.call_args[0][0]
        assert "Failed to resolve cashflowstatement for Unknown" in warning_message
        assert "CIK: Unknown" in warning_message
        assert "Period: Unknown" in warning_message
        assert "KeyError: 'Missing key'" in warning_message


def test_statement_of_equity_successful_resolution():
    """Test that successful statement resolution still works normally."""
    
    # Create a mock XBRL object that succeeds
    mock_xbrl = MagicMock()
    mock_xbrl.entity_name = "Success Company"
    mock_xbrl.cik = "1111111"
    mock_xbrl.period_of_report = "2024-12-31"
    
    # Mock successful find_statement
    mock_statements = [{'role': 'test_role'}]
    mock_role = 'test_role'
    mock_xbrl.find_statement.return_value = (mock_statements, mock_role, 'StatementOfEquity')
    
    # Create Statements instance
    statements = Statements(mock_xbrl)
    
    # Should return Statement object (mocked)
    with patch('edgar.xbrl.statements.Statement') as mock_statement_class:
        mock_statement_instance = MagicMock()
        mock_statement_class.return_value = mock_statement_instance
        
        result = statements.statement_of_equity()
        
        # Should return the Statement instance
        assert result == mock_statement_instance
        
        # Should call Statement constructor with correct parameters
        mock_statement_class.assert_called_once_with(
            mock_xbrl, 'test_role', canonical_type="StatementOfEquity"
        )


if __name__ == "__main__":
    test_income_statement_handles_low_confidence_error()
    test_balance_sheet_handles_general_exception()
    test_cashflow_statement_handles_missing_attributes()
    test_statement_of_equity_successful_resolution()
    
    print("✓ All error handling tests passed!")
    print("✓ Statement methods now return None instead of raising exceptions")
    print("✓ Detailed logging provides context for debugging failed resolutions")