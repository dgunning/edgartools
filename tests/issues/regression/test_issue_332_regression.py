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
    
    def test_eightk_alias_and_sixk_class(self):
        """Regression: EightK must remain alias for CurrentReport; SixK is its own class"""
        assert EightK is CurrentReport, (
            "REGRESSION: EightK must be an alias for CurrentReport"
        )
        # SixK is now a dedicated class (not an alias for CurrentReport)
        from edgar.company_reports.sixk import SixK as SixKDirect
        assert SixK is SixKDirect, (
            "REGRESSION: SixK must be importable from company_reports"
        )
    
    def test_current_report_accepts_8k_and_sixk_accepts_6k(self):
        """Regression: CurrentReport accepts 8-K; SixK accepts 6-K"""
        # Test 8-K form acceptance
        mock_filing_8k = Mock()
        mock_filing_8k.form = "8-K"

        try:
            CurrentReport(mock_filing_8k)
        except AssertionError as e:
            pytest.fail(f"REGRESSION: CurrentReport should accept 8-K forms. Error: {e}")

        # Test 6-K form acceptance via SixK
        mock_filing_6k = Mock()
        mock_filing_6k.form = "6-K"

        try:
            SixK(mock_filing_6k)
        except AssertionError as e:
            pytest.fail(f"REGRESSION: SixK should accept 6-K forms. Error: {e}")
    
    def test_financial_properties_do_not_raise_attribute_error(self):
        """Regression: Accessing financial properties should not raise AttributeError"""
        mock_filing = Mock()
        mock_filing.form = "6-K"
        mock_filing.attachments = []  # Must be iterable for earnings extraction

        # Mock Financials.extract to return None (simulating no financial data)
        with patch('edgar.financials.Financials.extract', return_value=None):
            report = SixK(mock_filing)

            # These should not raise AttributeError (the original bug)
            try:
                _ = report.financials  # This was the original failing call
            except AttributeError as e:
                pytest.fail(f"REGRESSION: AttributeError raised when accessing financial properties: {e}")
    
    def test_original_error_scenario(self):
        """Regression: Test the exact scenario from the original issue report"""
        # This simulates the user's original code that failed
        mock_filing = Mock()
        mock_filing.form = "6-K"

        # The user was trying to access .financials on a 6-K report
        report = SixK(mock_filing)

        # This line should not raise: AttributeError: object has no attribute 'financials'
        try:
            with patch('edgar.financials.Financials.extract', return_value=None):
                financials = report.financials
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

# Ported here on 2026-08-10 from
# tests/issues/reproductions/data-quality/test_issue_332_6k_financials.py (bead
# edgartools-07lk.24, Tier 2). That file was listed for deletion as a duplicate
# of this one; its mock-based tests were, this one was not. Everything above
# runs against Mock filings, so it proves the class hierarchy is intact and
# nothing about whether a real 6-K survives the pipeline that issue #332 was
# reported against.
@pytest.mark.network
def test_real_filing_integration():
    """A real 6-K exposes .financials without raising AttributeError (issue #332)."""
    from edgar import Company

    # ASML Holding N.V. — a Dutch filer that reports on 6-K rather than 8-K.
    company = Company("ASML")
    filings = company.get_filings(form="6-K")
    assert len(filings) > 0, (
        "ASML returned no 6-K filings. It files them continuously, so an empty "
        "result is a filing-access defect, not a reason to skip."
    )

    filing = filings.latest()
    report = filing.obj()
    assert report is not None, f"filing.obj() returned None for {filing.accession_number}"
    assert isinstance(report, SixK), (
        f"6-K {filing.accession_number} produced {type(report).__name__}, expected SixK"
    )

    # The regression itself: CurrentReport did not inherit from CompanyReport, so
    # this attribute did not exist and raised AttributeError.
    assert hasattr(report, 'financials'), (
        f"{type(report).__name__} has no .financials property — issue #332 has regressed"
    )
    # Access it too. hasattr() alone passes on a property that exists, and the
    # bug was in reading it. Its value may legitimately be None: most 6-Ks carry
    # no XBRL financial statements. Raising is the failure, not returning None.
    report.financials
