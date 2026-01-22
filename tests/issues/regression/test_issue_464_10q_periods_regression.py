"""
Regression test for GitHub issue #464: Missing comparative periods in 10-Q statements

GitHub Issue: https://github.com/dgunning/edgartools/issues/464
Related Issue: https://github.com/dgunning/edgartools/issues/465

User Report:
- COIN 10-Q Q3 2024 Cash Flow had 26-34 missing values
- COIN 10-Q Q3 2024 Income Statement had 15-16 missing values
- Balance Sheets were complete after v4.20.1

Root Cause:
- v4.20.1 expanded instant period candidates (Balance Sheets) from 4 to 10
- But did NOT apply same approach to duration periods (Income/Cash Flow)
- Duration period selection still used narrow candidate pool

Fix Applied:
- Expanded duration period candidate pool in _select_quarterly_periods()
- Check up to 12 quarterly periods (was ~4)
- Return max_periods * 3 candidates (was max_periods)
- Let data quality filtering choose best ones
- Mirrors successful Balance Sheet fix from v4.20.1

File Modified:
- edgar/xbrl/period_selector.py (_select_quarterly_periods function)

Date Fixed: 2025-10-19
Version: v4.20.2
"""
import pytest
from edgar import Company


# Metadata columns to exclude when looking at period/data columns
METADATA_COLUMNS = [
    'concept', 'label', 'level', 'abstract', 'dimension',
    'balance', 'weight', 'preferred_sign', 'parent_concept', 'parent_abstract_concept',
    'dimension_axis', 'dimension_member', 'dimension_member_label', 'dimension_label',
    'unit', 'point_in_time'
]


# No @pytest.mark.regression needed - auto-applied by conftest.py
@pytest.mark.network
def test_issue_464_coin_10q_comparative_periods():
    """
    Verify COIN 10-Q has comparative periods for analysis.

    This is the exact user-reported scenario from Issue #465.
    The key regression is ensuring we have multiple periods for comparison,
    not specific missing value counts (which vary by filing).
    """
    company = Company("COIN")
    filing = company.get_filings(form="10-Q").latest(1)

    xbrl = filing.xbrl()

    # Cash Flow should have at least 2 comparative periods
    cash_flow = xbrl.statements.cashflow_statement().to_dataframe()
    cf_period_cols = [col for col in cash_flow.columns if col not in METADATA_COLUMNS]

    assert len(cf_period_cols) >= 2, (
        f"Cash Flow has only {len(cf_period_cols)} period(s), expected at least 2 for comparison. "
        f"Periods found: {cf_period_cols}"
    )

    # Income Statement should have at least 2 comparative periods
    income = xbrl.statements.income_statement().to_dataframe()
    income_period_cols = [col for col in income.columns if col not in METADATA_COLUMNS]

    assert len(income_period_cols) >= 2, (
        f"Income Statement has only {len(income_period_cols)} period(s), expected at least 2 for comparison. "
        f"Periods found: {income_period_cols}"
    )


@pytest.mark.network
def test_issue_464_coin_10q_has_comparative_periods():
    """
    Verify COIN 10-Q has at least 2 periods for YoY comparison.
    """
    company = Company("COIN")
    filing = company.get_filings(form="10-Q").latest(1)

    xbrl = filing.xbrl()

    for statement_type in ["cashflow_statement", "income_statement", "balance_sheet"]:
        statement = getattr(xbrl.statements, statement_type)()
        df = statement.to_dataframe()

        period_columns = [col for col in df.columns if col not in METADATA_COLUMNS]

        assert len(period_columns) >= 2, (
            f"{statement_type} has only {len(period_columns)} period(s), "
            f"expected at least 2 for YoY comparison"
        )


@pytest.mark.network
@pytest.mark.parametrize("ticker", ["NVDA", "MSFT", "AAPL"])
def test_issue_464_multiple_companies_10q(ticker):
    """
    Verify fix works across multiple companies' 10-Q filings.

    Tests NVDA, MSFT, AAPL to ensure fix is not company-specific.
    """
    company = Company(ticker)
    filing = company.get_filings(form="10-Q").latest(1)

    xbrl = filing.xbrl()

    for statement_type in ["cashflow_statement", "income_statement"]:
        statement = getattr(xbrl.statements, statement_type)()
        df = statement.to_dataframe()

        period_columns = [col for col in df.columns if col not in METADATA_COLUMNS]

        assert len(period_columns) >= 2, (
            f"{ticker} 10-Q {statement_type} has only {len(period_columns)} period(s), "
            f"expected at least 2 for YoY comparison"
        )


@pytest.mark.network
def test_issue_464_no_regression_in_10k():
    """
    Verify fix did not break 10-K period selection.

    10-K statements should still have comparative periods after fix.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)

    xbrl = filing.xbrl()

    for statement_type in ["balance_sheet", "income_statement", "cashflow_statement"]:
        statement = getattr(xbrl.statements, statement_type)()
        df = statement.to_dataframe()

        period_columns = [col for col in df.columns if col not in METADATA_COLUMNS]

        assert len(period_columns) >= 2, (
            f"10-K {statement_type} has only {len(period_columns)} period(s), "
            f"expected at least 2 for comparative analysis"
        )
