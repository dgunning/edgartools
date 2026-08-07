"""
Regression test for GH #780: XBRLS.from_filings() should surface quarterly columns
alongside YTD (parity with single-filing XBRL).

Before this fix: stitched income/cash-flow statements emitted a single column per
filing, preferring the longer YTD/annual period when both existed (Issue #475
behavior). The discrete-quarter facts that single-filing XBRL surfaces were
silently dropped during stitching.

The fix adds an opt-in ``include_quarterly`` parameter that surfaces both the
discrete-quarter and YTD/annual periods from each filing. Default behavior is
unchanged.
"""
from __future__ import annotations

import pytest

from edgar import Filing
from edgar.xbrl import XBRLS


# Pinned AAPL accession numbers (10-Qs and 10-Ks) for determinism.
# Filings span fiscal 2025 Q3 → fiscal 2026 Q2, giving us:
#   - 10-Q FY26 Q2 (Mar 28, 2026): discrete-Q (90d) + 6-month YTD
#   - 10-Q FY26 Q1 (Dec 27, 2025): discrete-Q only (Q1 = first quarter)
#   - 10-K FY25      (Sep 27, 2025): annual (363d) + embedded Q4 discrete (90d)
#   - 10-Q FY25 Q3 (Jun 28, 2025): discrete-Q (90d) + 9-month YTD
AAPL_CIK = 320193
AAPL_FILINGS = [
    ("0000320193-26-000013", "2026-05-01", "10-Q"),  # FY26 Q2
    ("0000320193-26-000006", "2026-01-30", "10-Q"),  # FY26 Q1
    ("0000320193-25-000079", "2025-10-31", "10-K"),  # FY25
    ("0000320193-25-000073", "2025-08-01", "10-Q"),  # FY25 Q3
]


@pytest.fixture(scope="module")
def aapl_xbrls() -> XBRLS:
    filings = [
        Filing(form=form, filing_date=date, company="Apple Inc.",
               cik=AAPL_CIK, accession_no=acc)
        for acc, date, form in AAPL_FILINGS
    ]
    xbrls = XBRLS([f.xbrl() for f in filings])
    return xbrls


@pytest.mark.network
def test_default_behavior_unchanged_one_period_per_filing(aapl_xbrls: XBRLS):
    """Regression: default (include_quarterly=False) emits one period per filing."""
    raw = aapl_xbrls.get_statement("IncomeStatement")
    periods = raw["periods"]
    assert len(periods) == 4

    labels = [label for _, label in periods]
    # The Q2 YTD and Q3 YTD are still preferred over the discrete-Q alternatives.
    assert "Q2 YTD Mar 28, 2026" in labels
    assert "Q3 YTD Jun 28, 2025" in labels


@pytest.mark.network
def test_include_quarterly_surfaces_both_columns(aapl_xbrls: XBRLS):
    """
    Ground truth: AAPL FY26 Q2 has both a 90-day discrete-Q period
    (Dec 28, 2025 → Mar 28, 2026) and a 181-day H1 YTD period
    (Sep 28, 2025 → Mar 28, 2026) in the same 10-Q filing. With
    include_quarterly=True both must surface.
    """
    raw = aapl_xbrls.get_statement("IncomeStatement", include_quarterly=True)
    periods = raw["periods"]
    period_keys = [pid for pid, _ in periods]
    period_labels = [label for _, label in periods]

    # Both Q2 columns appear
    assert "duration_2025-12-28_2026-03-28" in period_keys, "discrete Q2 missing"
    assert "duration_2025-09-28_2026-03-28" in period_keys, "Q2 YTD missing"
    assert "Q2 Mar 28, 2026" in period_labels
    assert "Q2 YTD Mar 28, 2026" in period_labels

    # Both Q3 columns appear (FY25 10-Q)
    assert "duration_2025-03-30_2025-06-28" in period_keys, "discrete Q3 missing"
    assert "duration_2024-09-29_2025-06-28" in period_keys, "Q3 YTD missing"


@pytest.mark.network
def test_dataframe_q2_discrete_plus_q1_equals_q2_ytd(aapl_xbrls: XBRLS):
    """
    Hard ground-truth assertion: the H1 FY26 YTD value must equal Q1 + Q2 discrete
    for AAPL Net sales. Public 10-Q values:
      Q1 FY26 (Dec 27, 2025):       $143,756M
      Q2 FY26 (Mar 28, 2026):       $111,184M
      H1 FY26 YTD (Mar 28, 2026):   $254,940M
    """
    stmt = aapl_xbrls.statements.income_statement(include_quarterly=True)
    df = stmt.to_dataframe()

    revenue_concept = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"
    rev = df[df["concept"] == revenue_concept]
    assert not rev.empty, "Net sales row not found"
    row = rev.iloc[0]

    q1 = row["2025-12-27"]                      # Q1 FY26 (90d)
    q2_discrete = row["Q2 Mar 28, 2026"]        # Q2 FY26 discrete (90d)
    q2_ytd = row["Q2 YTD Mar 28, 2026"]         # H1 FY26 YTD (181d)

    assert q1 == 143_756_000_000
    assert q2_discrete == 111_184_000_000
    assert q2_ytd == 254_940_000_000
    assert q1 + q2_discrete == q2_ytd, (
        f"H1 YTD ({q2_ytd}) != Q1 ({q1}) + Q2 discrete ({q2_discrete})"
    )


@pytest.mark.network
def test_dataframe_columns_disambiguated_under_include_quarterly(aapl_xbrls: XBRLS):
    """
    Two periods sharing the same end date (discrete Q + YTD) must produce
    distinct DataFrame columns. Default end-date naming would collide; the
    fix falls back to the disambiguated period_label only when needed.
    """
    stmt_default = aapl_xbrls.statements.income_statement()
    df_default = stmt_default.to_dataframe()
    # Default columns are end-dates only (one per filing, no collisions)
    period_cols_default = [c for c in df_default.columns
                           if c not in ("label", "concept", "standard_concept", "preferred_sign")]
    assert all("-" in c and len(c) == 10 for c in period_cols_default), (
        f"Default columns should be YYYY-MM-DD, got: {period_cols_default}"
    )

    stmt_q = aapl_xbrls.statements.income_statement(include_quarterly=True)
    df_q = stmt_q.to_dataframe()
    # No duplicate columns
    period_cols_q = [c for c in df_q.columns
                     if c not in ("label", "concept", "standard_concept", "preferred_sign")]
    assert len(period_cols_q) == len(set(period_cols_q)), (
        f"Duplicate columns in include_quarterly output: {period_cols_q}"
    )


@pytest.mark.network
def test_balance_sheet_unaffected_by_include_quarterly(aapl_xbrls: XBRLS):
    """Balance sheet uses instant periods only — include_quarterly is a no-op."""
    raw_default = aapl_xbrls.get_statement("BalanceSheet")
    raw_quarterly = aapl_xbrls.get_statement("BalanceSheet", include_quarterly=True)
    assert raw_default["periods"] == raw_quarterly["periods"]
