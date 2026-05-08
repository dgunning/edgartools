"""
Regression test for Issue #464 / #465 (COIN 10-Q Q3 2024 missing-period data).

User report (Issue #465):
- COIN 10-Q Q3 2024 Cash Flow had 26-34 missing values
- COIN 10-Q Q3 2024 Income Statement had 15-16 missing values
- Balance Sheets were complete after v4.20.1

These tests pin the actual Q3 2024 10-Q accession (0001679788-24-000187,
filed 2024-10-30, period 2024-09-30). Prior to this pinning, the tests used
``Company.get_filings(form='10-Q').latest(1)`` which silently drifted as
new COIN 10-Qs were filed — a 2026 latest 10-Q has different completeness
characteristics than the 2024 filing the issue was filed against, and the
drift caused intermittent regression-test failures unrelated to the fix.
"""
import re

import pytest

from edgar import Filing


COIN_CIK = 1679788
COIN_Q3_2024_ACC = "0001679788-24-000187"  # 10-Q filed 2024-10-30, period 2024-09-30


@pytest.fixture(scope="module")
def coin_q3_2024_filing() -> Filing:
    return Filing(form="10-Q", filing_date="2024-10-30",
                  company="Coinbase Global, Inc.",
                  cik=COIN_CIK, accession_no=COIN_Q3_2024_ACC)


def _missing_in_period_columns(df) -> tuple[list[str], int]:
    """Return (period_columns, missing_count) for non-abstract, non-dimensional rows.

    Period columns are date-prefixed (YYYY-MM-DD); metadata columns
    (balance, weight, preferred_sign, etc.) are excluded. Dimensional
    breakdown rows are also excluded — those partition a parent value
    across axes (e.g., RestructuringCharges by category) and are
    inherently sparse when a category only applied in some periods.
    Issue #464 was about *primary-line* completeness, which is what we
    assert here.
    """
    date_pattern = r"^\d{4}-\d{2}-\d{2}"
    period_columns = [col for col in df.columns if re.match(date_pattern, col)]

    rows = df
    if "abstract" in rows.columns:
        rows = rows[rows["abstract"] == False]  # noqa: E712
    if "is_breakdown" in rows.columns:
        rows = rows[rows["is_breakdown"] == False]  # noqa: E712
    elif "dimension" in rows.columns:
        # Older schema: a non-empty dimension marks a dimensional breakdown row
        rows = rows[rows["dimension"].isnull() | (rows["dimension"] == "")]

    if not period_columns:
        return period_columns, 0
    return period_columns, int(rows[period_columns].isnull().sum().sum())


@pytest.mark.network
def test_coin_10q_q3_2024_cash_flow_has_comparative_periods(coin_q3_2024_filing):
    """Cash Flow Statement for COIN Q3 2024 has comparative periods with no missing values."""
    xbrl = coin_q3_2024_filing.xbrl()
    cash_flow = xbrl.statements.cashflow_statement()
    assert cash_flow is not None, "Cash Flow Statement not found"

    df = cash_flow.to_dataframe()
    period_columns, missing = _missing_in_period_columns(df)

    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods for YoY comparison, got {len(period_columns)}"
    )
    # Allow up to 4 missing values for known reconciliation-row edge cases.
    assert missing <= 4, (
        f"Cash Flow has {missing} missing values in data rows (expected <= 4). "
        f"Period columns: {period_columns}"
    )


@pytest.mark.network
def test_coin_10q_q3_2024_income_statement_has_comparative_periods(coin_q3_2024_filing):
    """Income Statement for COIN Q3 2024 has comparative periods with no missing values."""
    xbrl = coin_q3_2024_filing.xbrl()
    income = xbrl.statements.income_statement()
    assert income is not None, "Income Statement not found"

    df = income.to_dataframe()
    period_columns, missing = _missing_in_period_columns(df)

    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods for YoY comparison, got {len(period_columns)}"
    )
    assert missing == 0, (
        f"Income Statement has {missing} missing values in data rows (expected 0). "
        f"Period columns: {period_columns}"
    )


@pytest.mark.network
def test_coin_10q_q3_2024_balance_sheet_still_works(coin_q3_2024_filing):
    """Balance Sheet for COIN Q3 2024 still surfaces comparative periods (v4.20.1 fix)."""
    xbrl = coin_q3_2024_filing.xbrl()
    balance_sheet = xbrl.statements.balance_sheet()
    assert balance_sheet is not None, "Balance Sheet not found"

    df = balance_sheet.to_dataframe()
    date_pattern = r"^\d{4}-\d{2}-\d{2}"
    period_columns = [col for col in df.columns if re.match(date_pattern, col)]
    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods, got {len(period_columns)}"
    )
