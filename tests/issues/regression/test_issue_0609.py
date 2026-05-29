"""
Regression test for edgartools-0609: cash flow roll-forward rows render
empty + mislabeled (beginning/ending balances collapse to one node).

Bug (FIXED): The cash flow statement's roll-forward cash rows ("Cash,
beginning balances" / "Cash, ending balances") rendered incorrectly: both rows
showed the SAME label ("...ending balances") and both rendered with EMPTY value
cells in the displayed (duration) period columns, even though the underlying
instant facts existed.

Root cause: both presentation arcs to the cash concept (periodStartLabel and
periodEndLabel) collapse to a single PresentationNode keyed by element_id, so the
node's `preferred_label` only retained the last arc and the renderer could not
distinguish or place the period-start vs period-end instant values.

Fix:
- PresentationNode now tracks a per-reference `child_preferred_labels` list, and
  _generate_line_items honors each reference's own preferred label.
- rendering.py and statements.py map periodStart/periodEnd instant facts onto the
  duration columns for any statement (not just StatementOfEquity).

Ground truth (AAPL FY2023 10-K, tests/fixtures/xbrl/aapl/10k_2023):
    Cash, beginning balances  FY2023 = $24,977M  (= FY2022 year-end)
    Cash, ending balances     FY2023 = $30,737M
"""

from pathlib import Path

import pytest

from edgar.richtools import rich_to_text
from edgar.xbrl.xbrl import XBRL

FIXTURE = Path("tests/fixtures/xbrl/aapl/10k_2023")
CASH_CONCEPT = "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"


@pytest.fixture(scope="module")
def aapl_xbrl():
    return XBRL.from_directory(FIXTURE)


@pytest.mark.regression
def test_cashflow_rollforward_labels_distinct(aapl_xbrl):
    """Beginning and ending cash rows must have distinct, correct labels."""
    items = aapl_xbrl.get_statement("CashFlowStatement")
    cash_rows = [i for i in items
                 if i.get("concept") == CASH_CONCEPT and not i.get("is_dimension")]

    assert len(cash_rows) == 2, "Expected beginning + ending cash rows"
    labels = [r["label"].lower() for r in cash_rows]
    assert any(l.endswith("beginning balances") for l in labels), labels
    assert any(l.endswith("ending balances") for l in labels), labels
    # Not both the same
    assert labels[0] != labels[1]


@pytest.mark.regression
def test_cashflow_rollforward_values_dataframe(aapl_xbrl):
    """Beginning/ending instant facts must map onto the duration columns."""
    df = aapl_xbrl.statements.cashflow_statement().to_dataframe()
    value_cols = [c for c in df.columns if c.startswith("20")]
    assert value_cols, "Expected period value columns"
    fy2023 = value_cols[0]   # most-recent fiscal year column
    fy2022 = value_cols[1]

    begin = df[df.label.str.endswith("beginning balances")].iloc[0]
    end = df[df.label.str.endswith("ending balances")].iloc[0]

    # Hand-verified from the filing (in dollars)
    assert begin[fy2023] == 24_977_000_000.0   # beginning of FY2023 = FY2022 close
    assert end[fy2023] == 30_737_000_000.0      # ending of FY2023
    assert begin[fy2022] == 35_929_000_000.0
    assert end[fy2022] == 24_977_000_000.0

    # The roll-forward is internally consistent: each year's beginning equals the
    # prior year's ending.
    assert begin[fy2023] == end[fy2022]


@pytest.mark.regression
def test_cashflow_rollforward_values_rendered(aapl_xbrl):
    """The rich render must show the values too (not blank cells)."""
    text = rich_to_text(aapl_xbrl.statements.cashflow_statement().render(), width=200)
    begin_lines = [l for l in text.splitlines() if "beginning balances" in l.lower()]
    end_lines = [l for l in text.splitlines() if "ending balances" in l.lower()]

    assert begin_lines and any("24,977" in l for l in begin_lines), begin_lines
    assert end_lines and any("30,737" in l for l in end_lines), end_lines


@pytest.mark.regression
def test_equity_rollforward_still_distinct(aapl_xbrl):
    """
    Guard the equity interaction: the same roll-forward machinery must keep the
    Statement of Equity's beginning/ending StockholdersEquity values distinct.
    """
    df = aapl_xbrl.statements.statement_of_equity().to_dataframe()
    se = df[(df["concept"] == "us-gaap_StockholdersEquity") & (df["dimension"] == False)]
    value_cols = [c for c in df.columns if c.startswith("20")]
    assert value_cols

    begin = se[se.label.str.contains("eginning", na=False)].iloc[0]
    end = se[se.label.str.contains("nding", na=False) &
             ~se.label.str.contains("eginning", na=False)].iloc[0]

    col = value_cols[0]
    assert begin[col] != end[col], (begin[col], end[col])
    # Roll-forward consistency: FY beginning equals prior FY ending.
    assert begin[value_cols[0]] == end[value_cols[1]]
