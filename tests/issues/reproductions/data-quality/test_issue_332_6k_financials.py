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

from edgar import Company
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
            

# Integration test against a real 6-K.
#
# Explicitly `network`. Without the marker this file's name matches a FAST
# pattern in tests/conftest.py, which put a live Company("ASML") lookup and a
# filings fetch inside `test-fast (3.13)` — a required pull-request check.
#
# It also used to be incapable of failing. An ImportError became a skip, and so
# did every other exception, including the AttributeError on report.financials
# that issue #332 is entirely about. Three failure modes, three green skips.
@pytest.mark.network
@pytest.mark.regression
def test_real_filing_integration():
    """A real 6-K exposes .financials without raising AttributeError (issue #332)."""
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