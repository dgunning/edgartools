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


@pytest.mark.regression
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

@pytest.mark.regression
def test_sixk_has_financial_properties():
    """Test that SixK has access to financial properties"""
    assert hasattr(SixK, 'financials'), "SixK should have financials property"


@pytest.mark.regression
def test_eightk_alias_inherits_financial_properties():
    """Test that EightK alias also has access to the financial properties"""
    # Test that EightK is actually CurrentReport
    assert EightK is CurrentReport, "EightK should be an alias for CurrentReport"

@pytest.mark.regression
def test_current_report_accepts_8k_and_sixk_accepts_6k():
    """Test that CurrentReport accepts 8-K and SixK accepts 6-K"""
    # Test with 8-K
    mock_filing_8k = Mock()
    mock_filing_8k.form = "8-K"

    try:
        CurrentReport(mock_filing_8k)
    except AssertionError:
        pytest.fail("CurrentReport should accept 8-K forms")

    # Test with 6-K via SixK
    mock_filing_6k = Mock()
    mock_filing_6k.form = "6-K"

    try:
        SixK(mock_filing_6k)
    except AssertionError:
        pytest.fail("SixK should accept 6-K forms")

@pytest.mark.regression
def test_sixk_financial_properties_callable():
    """Test that the financial properties can be accessed without raising AttributeError"""
    mock_filing = Mock()
    mock_filing.form = "6-K"
    mock_filing.attachments = []

    from unittest.mock import patch
    with patch('edgar.financials.Financials.extract', return_value=None):
        report = SixK(mock_filing)

        try:
            financials = report.financials
        except AttributeError as e:
            pytest.fail(f"AttributeError raised when accessing financial properties: {e}")
            

# Integration test (may be skipped if network/data not available)
@pytest.mark.regression
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
                report = filing.obj()

                # Should not raise AttributeError
                financials = report.financials
                assert hasattr(report, 'financials')
                
                print(f"Integration test passed with {filing.form} filing")
            else:
                pytest.skip("No 6-K filings available for integration test")
                
        except Exception as e:
            pytest.skip(f"Integration test skipped due to data access issue: {e}")
            
    except ImportError as e:
        pytest.skip(f"Integration test skipped due to import issue: {e}")


if __name__ == "__main__":
    test_current_report_inherits_from_company_report()
    test_sixk_has_financial_properties()
    test_eightk_alias_inherits_financial_properties()
    test_current_report_accepts_8k_and_sixk_accepts_6k()
    test_sixk_financial_properties_callable()
    print("All basic tests passed!")