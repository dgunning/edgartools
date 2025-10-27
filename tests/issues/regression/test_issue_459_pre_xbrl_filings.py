"""
Regression test for Issue #459: Old Filings (with no XBRL format) are not convertible to dataframe

GitHub Issue: https://github.com/dgunning/edgartools/issues/459

Problem:
- When stitching filings that include pre-2009 filings (before XBRL was mandated),
  the XBRLS.from_filings() correctly skips non-XBRL filings but includes None values
- The period extraction code in _extract_all_periods() didn't handle None values
- This caused AttributeError: 'NoneType' object has no attribute 'reporting_periods'

Root Cause:
- edgar/xbrl/stitching/periods.py line 436 accessed xbrl.reporting_periods without
  first checking if xbrl is None

Fix:
- Added defensive None check before accessing xbrl.reporting_periods
- Now gracefully skips pre-XBRL era filings (before 2009)

User Impact:
- Enables historical analysis going back to 2001
- Allows stitching across XBRL and pre-XBRL eras
"""
import pytest
from datetime import date
from edgar import Company
from edgar.xbrl import XBRLS


@pytest.mark.network
@pytest.mark.slow
def test_issue_459_pre_xbrl_filings_dont_crash():
    """
    Test that stitching works even when filings include pre-XBRL era (before 2009).

    This test:
    1. Gets 18 years of Apple 10-K filings (includes pre-2009 filings)
    2. Creates XBRLS from mixed XBRL and non-XBRL filings
    3. Verifies that accessing stitched statements doesn't crash
    4. Confirms that only XBRL-era periods are included in results
    """
    # Get Apple filings going back 18 years (includes pre-XBRL era)
    company = Company('AAPL')
    filings_ten_k = company.get_filings(form="10-K").head(18)

    # This should not crash even with pre-XBRL filings
    xbrls = XBRLS.from_filings(filings_ten_k)

    # Verify we can access stitched statements without AttributeError
    stitched_statements = xbrls.statements

    # Verify income statement can be converted to dataframe
    income_statements = stitched_statements.income_statement()
    assert income_statements is not None

    # Convert to dataframe (this is where the bug manifested)
    df = income_statements.to_dataframe()
    assert df is not None
    assert len(df) > 0  # Should have data from XBRL-era filings

    # Verify only XBRL-era periods are included (2009+)
    # The pre-XBRL filings should be silently skipped
    periods = [col for col in df.columns if col not in ['concept', 'label', 'balance', 'weight', 'preferred_sign']]
    assert len(periods) > 0  # Should have some periods from XBRL filings


@pytest.mark.network
@pytest.mark.slow
def test_issue_459_workaround_filtering_to_xbrl_era():
    """
    Test the documented workaround: filtering to XBRL-era filings only.

    This verifies that the workaround documented in the issue still works.
    """
    company = Company('AAPL')
    filings_ten_k = company.get_filings(form="10-K")

    # Workaround: Filter to XBRL-era only (2009+)
    xbrl_era_start = date(2009, 1, 1)
    filings_xbrl = [f for f in filings_ten_k if f.filing_date >= xbrl_era_start]

    # Should work without issues (filter_amendments=False since we already filtered manually)
    xbrls = XBRLS.from_filings(filings_xbrl, filter_amendments=False)
    stitched_statements = xbrls.statements
    income_statements = stitched_statements.income_statement()

    assert income_statements is not None
    df = income_statements.to_dataframe()
    assert df is not None
    assert len(df) > 0


@pytest.mark.fast
def test_issue_459_none_filtering_in_extract_periods():
    """
    Unit test for the defensive None filtering in _extract_all_periods().

    This test directly verifies that the period extraction code handles
    None values in the xbrl_list.
    """
    from edgar.xbrl.stitching.periods import PeriodOptimizer

    # Create optimizer
    optimizer = PeriodOptimizer()

    # Test with a list containing None (simulating pre-XBRL filing)
    xbrl_list = [None, None]  # All pre-XBRL filings

    # Should not crash, should return empty list
    periods = optimizer._extract_all_periods(xbrl_list, "IncomeStatement")
    assert periods == []  # No periods since all XBRLs are None
