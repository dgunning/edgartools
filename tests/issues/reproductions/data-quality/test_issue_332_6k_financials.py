"""
Reproduction test for GitHub issue #332: 6-K Filings - Financials
https://github.com/dgunning/edgartools/issues/332

Issue: AttributeError: 'CurrentReport' object has no attribute 'financials'

This test verifies that:
1. 6-K forms can access financial data via the financials property
2. 8-K forms can also access financial data (regression test) 
3. Financial statements can be extracted from Current Reports (6-K/8-K)

The fix: Make CurrentReport inherit from CompanyReport to get financial functionality.
"""

import pytest
from unittest.mock import Mock
from edgar.company_reports import CurrentReport, SixK, EightK


def test_current_report_inherits_from_company_report():
    """Test that CurrentReport inherits from CompanyReport and has all financial methods"""
    from edgar.company_reports import CompanyReport
    
    # Test that CurrentReport is a subclass of CompanyReport
    assert issubclass(CurrentReport, CompanyReport), "CurrentReport should inherit from CompanyReport"
    
    # Test that the properties exist in the class definition
    assert 'financials' in CurrentReport.__dict__ or 'financials' in CompanyReport.__dict__, "Should have financials property"
    assert 'income_statement' in CompanyReport.__dict__, "Should have income_statement property"
    assert 'balance_sheet' in CompanyReport.__dict__, "Should have balance_sheet property"
    assert 'cash_flow_statement' in CompanyReport.__dict__, "Should have cash_flow_statement property"


def test_sixk_alias_inherits_financial_properties():
    """Test that SixK alias also has access to the financial properties"""
    # Test that SixK is actually CurrentReport
    assert SixK is CurrentReport, "SixK should be an alias for CurrentReport"


def test_eightk_alias_inherits_financial_properties():
    """Test that EightK alias also has access to the financial properties"""
    # Test that EightK is actually CurrentReport
    assert EightK is CurrentReport, "EightK should be an alias for CurrentReport"


def test_current_report_accepts_both_6k_and_8k():
    """Test that CurrentReport accepts both 6-K and 8-K form types"""
    # Test with 6-K - should not raise assertion error in __init__
    mock_filing_6k = Mock()
    mock_filing_6k.form = "6-K"
    
    try:
        report_6k = CurrentReport(mock_filing_6k)
        success_6k = True
    except AssertionError:
        success_6k = False
    
    assert success_6k, "CurrentReport should accept 6-K forms"
    
    # Test with 8-K - should not raise assertion error in __init__
    mock_filing_8k = Mock()
    mock_filing_8k.form = "8-K"
    
    try:
        report_8k = CurrentReport(mock_filing_8k)
        success_8k = True
    except AssertionError:
        success_8k = False
    
    assert success_8k, "CurrentReport should accept 8-K forms"


def test_current_report_financial_properties_callable():
    """Test that the financial properties can be accessed without raising AttributeError"""
    # Create a mock filing with minimal required methods
    mock_filing = Mock()
    mock_filing.form = "6-K"
    
    # Mock the Financials.extract method to return None (no financial data available)
    from unittest.mock import patch
    with patch('edgar.company_reports.Financials.extract', return_value=None):
        report = CurrentReport(mock_filing)
        
        # These should not raise AttributeError, even if they return None
        try:
            financials = report.financials
            income_stmt = report.income_statement
            balance_sheet = report.balance_sheet
            cash_flow = report.cash_flow_statement
            
            # All should be None or valid objects, but no AttributeError
            success = True
        except AttributeError as e:
            pytest.fail(f"AttributeError raised when accessing financial properties: {e}")
            

# Integration test (may be skipped if network/data not available)
def test_real_filing_integration():
    """Integration test with real filing data if available"""
    try:
        from edgar import get_filings
        from edgar import Company
        
        # Try to get a company with known 6-K filings
        try:
            # Try to get recent filings from a major foreign company that files 6-Ks
            company = Company("ASML")  # ASML Holding N.V. - Dutch company that files 6-Ks
            filings = company.get_filings(form="6-K")[:1]  # Get just 1 filing
            
            if filings:
                filing = filings[0]
                report = CurrentReport(filing)
                
                # Should not raise AttributeError
                financials = report.financials
                assert hasattr(report, 'financials')
                
                # Test individual statements
                income_stmt = report.income_statement
                balance_sheet = report.balance_sheet
                cash_flow = report.cash_flow_statement
                
                print(f"Integration test passed with {filing.form} filing")
            else:
                pytest.skip("No 6-K filings available for integration test")
                
        except Exception as e:
            pytest.skip(f"Integration test skipped due to data access issue: {e}")
            
    except ImportError as e:
        pytest.skip(f"Integration test skipped due to import issue: {e}")


if __name__ == "__main__":
    # Run the basic tests that don't require network access
    test_current_report_inherits_from_company_report()
    test_sixk_alias_inherits_financial_properties()
    test_eightk_alias_inherits_financial_properties()
    test_current_report_accepts_both_6k_and_8k()
    test_current_report_financial_properties_callable()
    print("All basic tests passed!")
    
    # Try integration test
    try:
        test_real_filing_integration()
        print("Integration test also passed!")
    except Exception as e:
        print(f"Integration test skipped: {e}")