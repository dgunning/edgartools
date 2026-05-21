"""
Regression test for GitHub issue #822: empty 10-Q income statement and cash
flow for filers with irregular-duration quarters (16-week Q1).

GitHub Issue: https://github.com/dgunning/edgartools/issues/822

User report (mkdeak, 2026-05-21):
- CAVA most recent 10-Q (accession 0001628280-26-036625, period 2026-04-19)
- ``income_statement().to_dataframe()`` returned a single value column
  ``'2025-07-13 (Q3)'`` with zero non-null values for the entire statement.

Root cause:
- ``edgar/xbrl/period_selector.py:_select_quarterly_periods`` bucketed
  duration periods into quarterly (80-100 days) and YTD (150-285 days).
- CAVA's Q1 is a 16-week quarter = 111 days, which fell into a dead zone
  between the buckets and was silently dropped. The parser then picked a
  stray prior-year 83-day period as the "current quarter."
- Same bug affects Red Robin Gourmet Burgers (RRGB) — also a 16-week-Q1
  retail-calendar filer.

Fix:
- Anchor period selection on ``filing.period_of_report`` first; bucket
  logic is now a fallback. Duration is used to disambiguate multiple
  anchors (quarter vs YTD) and to match prior-year comparatives.

Population (measured): ~1% of 10-Q filings — specialty retailers and
restaurants on a 4-4-4-4 retail fiscal calendar with a 16-week Q1.
"""
import pytest

from edgar import Filing


METADATA_COLUMNS = {
    'concept', 'label', 'standard_concept', 'level', 'abstract', 'dimension',
    'is_breakdown', 'dimension_axis', 'dimension_member', 'dimension_member_label',
    'dimension_label', 'balance', 'weight', 'preferred_sign',
    'parent_concept', 'parent_abstract_concept', 'unit', 'point_in_time',
}


CAVA_Q1_2026 = dict(
    form="10-Q", filing_date="2026-05-20",
    company="CAVA GROUP, INC.", cik=1639438,
    accession_no="0001628280-26-036625",
)

RRGB_Q1_2026 = dict(
    form="10-Q", filing_date="2026-05-20",
    company="RED ROBIN GOURMET BURGERS INC",
    cik=1171759,
    accession_no="0001628280-26-036501",
)


def _period_columns(df):
    return [c for c in df.columns if c not in METADATA_COLUMNS]


@pytest.fixture(scope="module")
def cava_q1_2026():
    return Filing(**CAVA_Q1_2026)


@pytest.fixture(scope="module")
def rrgb_q1_2026():
    return Filing(**RRGB_Q1_2026)


@pytest.mark.network
def test_cava_q1_2026_income_statement_current_period_is_anchored(cava_q1_2026):
    """CAVA Q1 fiscal 2026 income statement must surface the current period
    (2026-04-19) — the 111-day 16-week Q1 — not the stray 83-day prior-year
    period that the dead-zone bug used to surface."""
    df = cava_q1_2026.obj().financials.income_statement().to_dataframe()
    period_cols = _period_columns(df)

    assert '2026-04-19' in period_cols, (
        f"Expected '2026-04-19' as a period column for CAVA Q1 fiscal 2026. "
        f"Got: {period_cols}. This is the dead-zone regression — the parser "
        f"is selecting a stray prior-year period instead of the anchor."
    )

    # The buggy column header that should NEVER appear
    assert not any('2025-07-13' in c for c in period_cols), (
        f"Found '2025-07-13' in CAVA Q1 2026 period columns: {period_cols}. "
        f"This is the stray prior-year period the dead-zone bug selected."
    )


@pytest.mark.network
def test_cava_q1_2026_income_statement_revenue_values(cava_q1_2026):
    """Assert specific ground-truth revenue and net income values from the
    CAVA Q1 fiscal 2026 10-Q (period ended April 19, 2026)."""
    df = cava_q1_2026.obj().financials.income_statement().to_dataframe()
    assert '2026-04-19' in df.columns

    # Revenue (CAVA reports Restaurant revenue + CPG revenue and other under
    # a single Revenue concept). The total Revenue row (the non-breakdown
    # parent) should be present.
    revenue_rows = df[
        (df['label'] == 'Revenue')
        & (~df['is_breakdown'].fillna(False))
    ]
    assert len(revenue_rows) >= 1, f"Revenue row missing from CAVA Q1 2026"
    revenue_cur = revenue_rows.iloc[0]['2026-04-19']
    revenue_prior = revenue_rows.iloc[0]['2025-04-20']
    assert revenue_cur == 438270000.0, f"Expected 438270000, got {revenue_cur}"
    assert revenue_prior == 331826000.0, f"Expected 331826000, got {revenue_prior}"

    # Net income
    ni_rows = df[
        df['label'].str.fullmatch('Net income', na=False)
        & (~df['is_breakdown'].fillna(False))
    ]
    assert len(ni_rows) >= 1, "Net income row missing from CAVA Q1 2026"
    ni_cur = ni_rows.iloc[0]['2026-04-19']
    assert ni_cur == 23566000.0, f"Expected net income 23566000, got {ni_cur}"


@pytest.mark.network
def test_cava_q1_2026_cash_flow_is_populated(cava_q1_2026):
    """CAVA Q1 fiscal 2026 cash flow must surface the current 111-day period
    with populated values (not the empty stray prior-year period)."""
    df = cava_q1_2026.obj().financials.cashflow_statement().to_dataframe()
    period_cols = _period_columns(df)

    assert '2026-04-19' in period_cols, (
        f"Expected '2026-04-19' in CAVA Q1 2026 cash flow columns: {period_cols}"
    )

    # The current period must have substantial populated values, not be all-NaN
    # like the dead-zone bug produced.
    non_null = df['2026-04-19'].notna().sum()
    assert non_null >= 15, (
        f"CAVA Q1 2026 cash flow current period has only {non_null} non-null "
        f"values — the dead-zone bug produced 1. Expected substantial data."
    )


@pytest.mark.network
def test_rrgb_q1_2026_income_statement_current_period_is_anchored(rrgb_q1_2026):
    """Red Robin Q1 fiscal 2026 — same 16-week Q1 dead-zone case as CAVA.
    Verifies the fix works across the affected filer cohort, not just CAVA."""
    df = rrgb_q1_2026.obj().financials.income_statement().to_dataframe()
    period_cols = _period_columns(df)

    assert '2026-04-19' in period_cols, (
        f"Expected '2026-04-19' as a period column for RRGB Q1 fiscal 2026. "
        f"Got: {period_cols}. Dead-zone regression for RRGB."
    )


@pytest.mark.network
def test_rrgb_q1_2026_total_revenues_value(rrgb_q1_2026):
    """Ground-truth: RRGB Q1 fiscal 2026 total revenues = $378,261,000."""
    df = rrgb_q1_2026.obj().financials.income_statement().to_dataframe()
    assert '2026-04-19' in df.columns

    rows = df[
        df['label'].str.fullmatch('Total revenues', case=False, na=False)
        & (~df['is_breakdown'].fillna(False))
    ]
    assert len(rows) >= 1, "Total revenues row missing from RRGB Q1 2026"
    cur = rows.iloc[0]['2026-04-19']
    assert cur == 378261000.0, f"Expected total revenues 378261000, got {cur}"


@pytest.mark.network
@pytest.mark.parametrize("filing_kwargs", [CAVA_Q1_2026, RRGB_Q1_2026])
def test_balance_sheet_unaffected(filing_kwargs):
    """The balance sheet path uses instant periods, not duration buckets, so
    it was unaffected by the dead-zone bug. Verify it still works correctly
    for both affected filers — regression guard."""
    filing = Filing(**filing_kwargs)
    df = filing.obj().financials.balance_sheet().to_dataframe()
    period_cols = _period_columns(df)
    assert '2026-04-19' in period_cols, (
        f"Balance sheet missing 2026-04-19 column for {filing_kwargs['company']}. "
        f"Got: {period_cols}"
    )
    # Both period columns should have substantial values
    for col in period_cols:
        assert df[col].notna().sum() >= 20, (
            f"Balance sheet column {col} sparse for {filing_kwargs['company']}"
        )
