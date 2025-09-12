"""
Regression test for GitHub issue #332: 6-K Filings - Financials
https://github.com/dgunning/edgartools/issues/332

This test prevents regression of the original issue:
AttributeError: 'CurrentReport' object has no attribute 'financials'

The bug was caused by CurrentReport not inheriting from CompanyReport,
which provides financial functionality. The fix ensures CurrentReport
inherits from CompanyReport so users can access .financials, .income_statement,
.balance_sheet, and .cash_flow_statement properties on 6-K and 8-K filings.
"""

import pytest
from unittest.mock import Mock, patch
from edgar.company_reports import CurrentReport, CompanyReport, SixK, EightK


@pytest.mark.regression
class TestIssue332Regression:
    """Regression tests to prevent the return of issue #332"""
    
    def test_current_report_is_subclass_of_company_report(self):
        """Regression: CurrentReport must inherit from CompanyReport"""
        assert issubclass(CurrentReport, CompanyReport), (
            "REGRESSION: CurrentReport must inherit from CompanyReport to provide financial functionality. "
            "This was the root cause of issue #332."
        )
    
    def test_current_report_has_financial_properties(self):
        """Regression: CurrentReport must have financial properties available"""
        # Check that the financial properties exist in the class hierarchy
        assert hasattr(CompanyReport, 'financials'), (
            "REGRESSION: CompanyReport must have 'financials' property"
        )
        assert hasattr(CompanyReport, 'income_statement'), (
            "REGRESSION: CompanyReport must have 'income_statement' property"
        )
        assert hasattr(CompanyReport, 'balance_sheet'), (
            "REGRESSION: CompanyReport must have 'balance_sheet' property"
        )
        assert hasattr(CompanyReport, 'cash_flow_statement'), (
            "REGRESSION: CompanyReport must have 'cash_flow_statement' property"
        )
    
    def test_aliases_point_to_current_report(self):
        """Regression: SixK and EightK must remain aliases for CurrentReport"""
        assert SixK is CurrentReport, (
            "REGRESSION: SixK must be an alias for CurrentReport"
        )
        assert EightK is CurrentReport, (
            "REGRESSION: EightK must be an alias for CurrentReport"
        )
    
    def test_current_report_accepts_6k_and_8k_forms(self):
        """Regression: CurrentReport must accept both 6-K and 8-K forms"""
        # Test 6-K form acceptance
        mock_filing_6k = Mock()
        mock_filing_6k.form = "6-K"
        
        try:
            CurrentReport(mock_filing_6k)
        except AssertionError as e:
            pytest.fail(f"REGRESSION: CurrentReport should accept 6-K forms. Error: {e}")
        
        # Test 8-K form acceptance
        mock_filing_8k = Mock() 
        mock_filing_8k.form = "8-K"
        
        try:
            CurrentReport(mock_filing_8k)
        except AssertionError as e:
            pytest.fail(f"REGRESSION: CurrentReport should accept 8-K forms. Error: {e}")
    
    def test_financial_properties_do_not_raise_attribute_error(self):
        """Regression: Accessing financial properties should not raise AttributeError"""
        mock_filing = Mock()
        mock_filing.form = "6-K"
        
        # Mock Financials.extract to return None (simulating no financial data)
        with patch('edgar.company_reports.Financials.extract', return_value=None):
            report = CurrentReport(mock_filing)
            
            # These should not raise AttributeError (the original bug)
            try:
                _ = report.financials  # This was the original failing call
                _ = report.income_statement
                _ = report.balance_sheet
                _ = report.cash_flow_statement
            except AttributeError as e:
                pytest.fail(f"REGRESSION: AttributeError raised when accessing financial properties: {e}")
    
    def test_original_error_scenario(self):
        """Regression: Test the exact scenario from the original issue report"""
        # This simulates the user's original code that failed
        mock_filing = Mock()
        mock_filing.form = "6-K" 
        
        # The user was trying to access .financials on a CurrentReport
        report = CurrentReport(mock_filing)
        
        # This line should not raise: AttributeError: 'CurrentReport' object has no attribute 'financials'
        try:
            with patch('edgar.company_reports.Financials.extract', return_value=None):
                financials = report.financials
            # Test passed - no AttributeError raised
        except AttributeError as e:
            pytest.fail(f"REGRESSION: Original issue #332 has returned. AttributeError: {e}")
    
    def test_inheritance_chain_integrity(self):
        """Regression: Ensure the inheritance chain is correct"""
        # CurrentReport -> CompanyReport -> object
        mro = CurrentReport.__mro__
        
        assert CompanyReport in mro, (
            "REGRESSION: CurrentReport must inherit from CompanyReport"
        )
        
        # Ensure CompanyReport comes before object in the MRO
        company_report_index = mro.index(CompanyReport)
        object_index = mro.index(object)
        
        assert company_report_index < object_index, (
            "REGRESSION: CompanyReport should come before object in CurrentReport's MRO"
        )