"""
Regression test for GitHub Issue #910:
TTM income statements reported wrong Earnings Per Share values (quarterly EPS was
correct), and the console renderer rounded per-share amounts to whole dollars
while to_dataframe() kept full precision.

Root cause (values): TTMStatementBuilder._trend_for_eps labelled each TTM window
using the as_of fact's SEC-tagged ``fiscal_year``. The SEC tags a quarter
re-filed as a comparative with the FILING's fiscal year, so GOOGL's Q2 2025
(period_end 2025-06-30) carries fy=2026. That produced two windows labelled
"Q2 2026", and the caller's ``period_values`` dict — keyed by that label — let
the older window silently overwrite the current one. Only EPS was affected
because every other concept goes through calculate_ttm_trend(), which already
derives the label from period_end + fiscal-year-end month (GH #793).

Observable symptom: the same TTM period returned different values depending on
how many periods were requested (GOOGL Q2 2026 basic EPS was 20.16 at periods=4
but 9.45 — the trailing year ending Q2 2025 — at periods=8), and the displaced
periods came back NaN.

Root cause (formatting): the renderer formatted anything under $1M as
f"${value:,.0f}", so EPS of 20.16 displayed as "$20".

GitHub Issue: https://github.com/dgunning/edgartools/issues/910
"""
import pandas as pd
import pytest

from edgar import Company
from edgar.ttm.statement import _is_per_share_item

EPS_LABELS = ["Earnings Per Share, Basic", "Earnings Per Share, Diluted"]

VALUE_COLUMNS_EXCLUDED = {
    "label", "depth", "is_total", "is_abstract", "section", "confidence", "concept",
}


def _period_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in VALUE_COLUMNS_EXCLUDED]


# --- Offline: per-share detection drives the display format ---

def test_per_share_detection_matches_eps_and_dividend_concepts():
    assert _is_per_share_item({"concept": "EarningsPerShareBasic", "label": "Earnings Per Share, Basic"})
    assert _is_per_share_item({"concept": "EarningsPerShareDiluted", "label": "Earnings Per Share, Diluted"})
    assert _is_per_share_item(
        {"concept": "CommonStockDividendsPerShareDeclared", "label": "Common Stock, Dividends, Per Share, Declared"}
    )


def test_per_share_detection_excludes_monetary_and_share_count_concepts():
    # Share *counts* are magnitudes, not per-share amounts, and must keep the
    # B/M formatting.
    assert not _is_per_share_item(
        {"concept": "WeightedAverageNumberOfSharesOutstandingBasic", "label": "Shares Outstanding, Basic"}
    )
    assert not _is_per_share_item({"concept": "NetIncomeLoss", "label": "Net Income (Loss)"})
    assert not _is_per_share_item({"concept": "Revenues", "label": "Revenues"})
    # 'eps' is matched as a substring; make sure a bank's deposit lines don't trip it.
    assert not _is_per_share_item({"concept": "Deposits", "label": "Deposits"})
    assert not _is_per_share_item({"concept": "InterestExpenseDeposits", "label": "Interest Expense, Deposits"})


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", ["GOOGL", "TSLA"])
def test_ttm_eps_is_stable_across_period_counts(ticker):
    """The TTM value for a given quarter must not depend on how many periods
    were requested. This is the reported bug: at periods=8 an older window
    overwrote the current one."""
    company = Company(ticker)
    df4 = company.income_statement(periods=4, period="ttm").to_dataframe()
    df8 = company.income_statement(periods=8, period="ttm").to_dataframe()

    shared = [c for c in _period_columns(df4) if c in _period_columns(df8)]
    assert shared, "expected overlapping TTM periods between the two requests"

    for label in EPS_LABELS:
        row4 = df4[df4["label"] == label]
        row8 = df8[df8["label"] == label]
        assert not row4.empty and not row8.empty, f"{ticker}: {label} row missing"
        for column in shared:
            v4 = row4.iloc[0][column]
            v8 = row8.iloc[0][column]
            assert pd.notna(v4) and pd.notna(v8), f"{ticker}: {label} {column} is NaN"
            assert v4 == pytest.approx(v8, rel=1e-9), (
                f"{ticker}: {label} {column} differs by period count: "
                f"periods=4 -> {v4}, periods=8 -> {v8}"
            )


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", ["GOOGL", "TSLA", "AAPL", "NVDA"])
def test_ttm_eps_has_no_missing_periods(ticker):
    """Mislabelled windows collided onto the same key, leaving the periods they
    should have occupied empty. Every requested period must carry a value."""
    df = Company(ticker).income_statement(periods=8, period="ttm").to_dataframe()
    for label in EPS_LABELS:
        row = df[df["label"] == label]
        assert not row.empty, f"{ticker}: {label} row missing"
        missing = [c for c in _period_columns(df) if pd.isna(row.iloc[0][c])]
        assert not missing, f"{ticker}: {label} missing TTM values for {missing}"


@pytest.mark.network
@pytest.mark.regression
def test_ttm_eps_at_fiscal_year_end_matches_reported_annual_eps():
    """Ground truth: a TTM window ending on the fiscal year end covers exactly
    the fiscal year, so it must reconcile with the EPS Alphabet reported.

    GOOGL FY2024 basic EPS = 8.13, FY2025 = 10.91 (us-gaap:EarningsPerShareBasic,
    FY facts). TTM divides TTM net income by the mean of the four quarters'
    weighted-average share counts, so it lands within a fraction of a cent
    rather than exactly.
    """
    df = Company("GOOGL").income_statement(periods=8, period="ttm").to_dataframe()
    basic = df[df["label"] == "Earnings Per Share, Basic"].iloc[0]

    assert basic["Q4 2024"] == pytest.approx(8.13, rel=0.01)
    assert basic["Q4 2025"] == pytest.approx(10.91, rel=0.01)

    # And the current window is the sum of its four quarters, not a stale year:
    # Q3'25 2.89 + Q4'25 2.85 + Q1'26 5.17 + Q2'26 9.23 = 20.14.
    assert basic["Q2 2026"] == pytest.approx(20.14, rel=0.01)


@pytest.mark.network
@pytest.mark.regression
def test_ttm_console_output_keeps_per_share_precision():
    """EPS rendered as '$20' while the dataframe held 20.16. Per-share amounts
    render with 2 decimals; monetary rows keep the B/M magnitude format."""
    from rich.console import Console

    statement = Company("GOOGL").income_statement(periods=4, period="ttm")
    console = Console(width=200, no_color=True)
    with console.capture() as capture:
        console.print(statement)
    rendered = capture.get()

    eps_line = next(line for line in rendered.splitlines() if "Earnings Per Share, Basic" in line)
    assert "20.16" in eps_line, f"expected 2-decimal EPS, got: {eps_line.strip()}"
    assert "$20 " not in eps_line, f"EPS still whole-dollar rounded: {eps_line.strip()}"

    # Monetary lines are unchanged.
    ni_line = next(line for line in rendered.splitlines() if "Net Income (Loss)" in line)
    assert "B" in ni_line, f"expected billions formatting on net income: {ni_line.strip()}"
