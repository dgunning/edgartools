#!/usr/bin/env python3
"""
Demo showing improved error handling for statement resolution.
This shows how the system now gracefully handles failures instead of crashing.
"""

from unittest.mock import MagicMock, patch
from edgar.xbrl.statements import Statements


def demo_improved_error_handling():
    """Demonstrate the improved error handling behavior."""
    
    print("=== Before: Exception would crash the application ===")
    print("ValueError: Low confidence match for type 'IncomeStatement': 0.10. Found statements: ['Cover']")
    print("Application would terminate with stack trace\n")
    
    print("=== After: Graceful error handling with detailed logging ===")
    
    # Create a mock XBRL that simulates the problematic filing
    mock_xbrl = MagicMock()
    mock_xbrl.entity_name = "PACS Group, Inc."
    mock_xbrl.cik = "2001184"
    mock_xbrl.period_of_report = "2024-05-21"
    
    # Mock the low confidence error from statement resolution
    mock_xbrl.find_statement.side_effect = ValueError(
        "Low confidence match for type 'IncomeStatement': 0.10. Found statements: ['Cover']"
    )
    
    # Create statements object
    statements = Statements(mock_xbrl)
    
    # Show how the application now handles this gracefully
    with patch('edgar.core.log') as mock_log:
        print("Attempting to get income statement...")
        result = statements.income_statement()
        
        if result is None:
            print("✓ Method returned None instead of crashing")
            print("✓ Application continues running")
            
            # Show the logged warning
            if mock_log.warning.called:
                warning_msg = mock_log.warning.call_args[0][0]
                print(f"\n📋 Logged warning for debugging:")
                print(f"   {warning_msg}")
        
        print(f"\n🔄 Application can continue processing other filings...")
        print(f"    result = {result}")
        print(f"    type(result) = {type(result)}")


def demo_batch_processing_resilience():
    """Show how this helps with batch processing."""
    
    print("\n" + "="*60)
    print("=== Batch Processing Resilience ===")
    print("="*60)
    
    # Simulate processing multiple filings
    test_filings = [
        {"name": "Good Filing Corp", "cik": "1111111", "should_fail": False},
        {"name": "PACS Group, Inc.", "cik": "2001184", "should_fail": True},  # The problematic one
        {"name": "Another Good Corp", "cik": "3333333", "should_fail": False},
    ]
    
    successful_statements = 0
    failed_statements = 0
    
    for filing_info in test_filings:
        mock_xbrl = MagicMock()
        mock_xbrl.entity_name = filing_info["name"]
        mock_xbrl.cik = filing_info["cik"]
        mock_xbrl.period_of_report = "2024-12-31"
        
        if filing_info["should_fail"]:
            # Simulate the resolution failure
            mock_xbrl.find_statement.side_effect = ValueError("Low confidence match")
        else:
            # Simulate successful resolution
            mock_xbrl.find_statement.return_value = ([], "test_role", "IncomeStatement")
        
        statements = Statements(mock_xbrl)
        
        with patch('edgar.core.log'):
            with patch('edgar.xbrl.statements.Statement') as mock_statement:
                mock_statement.return_value = MagicMock() if not filing_info["should_fail"] else None
                
                print(f"Processing {filing_info['name']}...")
                income_stmt = statements.income_statement()
                
                if income_stmt is not None:
                    print(f"  ✓ Successfully got income statement")
                    successful_statements += 1
                else:
                    print(f"  ⚠ Failed to resolve income statement (logged for review)")
                    failed_statements += 1
    
    print(f"\n📊 Batch Processing Results:")
    print(f"   ✓ Successful: {successful_statements}")
    print(f"   ⚠ Failed: {failed_statements}")
    print(f"   🔄 Total processed: {len(test_filings)}")
    print(f"\n✅ Batch processing completed without crashing!")


if __name__ == "__main__":
    demo_improved_error_handling()
    demo_batch_processing_resilience()
    
    print(f"\n" + "="*60)
    print("=== Summary ===")
    print("="*60)
    print("✅ Statement methods now return None instead of raising exceptions")
    print("✅ Detailed error context is logged for debugging")
    print("✅ Batch processing can continue despite individual failures")
    print("✅ Applications remain stable when processing problematic filings")
    print("="*60)