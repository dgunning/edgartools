"""A blank cell in an R-file table was reported as the number 0.0.

bead edgartools-nfk3. `FinancialTableExtractor._parse_financial_value` returned
0.0 for an empty cell and for a dash alike. A dash is the financial-table
convention for zero; an empty cell means the filing gives no value on that row.
Across six filers' latest 10-K statements 45% of parsed cells were blank, and
every one of them was reported as a zero that the filing does not state.

The visible case is an equity roll-forward, which leaves the Total column blank
on most rows. Apple's FY2025 10-K (accession 0000320193-25-000079, R7.htm) files
"Common stock issued" as ['Common stock issued', '&#160;', '1,346', '&#160;',
'&#160;'], so the frame said issuing $1,346M of stock moved total equity by zero.

Runs offline against the tracked Apple Q2 FY2025 10-Q fixture (R6.htm), whose
equity statement has the same shape.
"""

import math
from pathlib import Path

import pytest

from edgar.sgml.table_to_dataframe import FinancialTableExtractor, extract_statement_dataframe

R6 = (Path(__file__).resolve().parents[2]
      / "fixtures" / "attachments" / "aapl" / "20250329" / "R6.htm")

parse = FinancialTableExtractor._parse_financial_value


@pytest.fixture(scope="module")
def equity():
    assert R6.exists(), f"missing fixture: {R6}"
    return extract_statement_dataframe(R6.read_text(encoding="utf-8"))


def test_a_blank_total_is_missing_not_zero(equity):
    """The first filed row: [label, blank, 752, blank, blank] -- blank Total, $752M paid-in capital."""
    row = equity[equity.index == "Common stock issued"].iloc[0]
    assert math.isnan(row["Total"])
    assert row["Common stock and additional paid-in capital"] == 752_000_000
    assert math.isnan(row["Retained earnings/(Accumulated deficit)"])


def test_no_cell_in_the_equity_statement_is_a_fabricated_zero(equity):
    """Apple's roll-forward files no zero anywhere, so none may appear."""
    numeric = equity.select_dtypes("number")
    assert int((numeric == 0).sum().sum()) == 0
    assert int(numeric.isna().sum().sum()) == 111


def test_filed_values_still_sum_after_skipping_blanks(equity):
    """NaN keeps pandas' default skipna arithmetic correct: blanks contribute nothing."""
    beginning = equity.loc["Beginning balances at Sep. 30, 2023"]
    components = beginning.drop("Total")
    assert components.sum() == beginning["Total"] == 62_146_000_000


@pytest.mark.parametrize("cell", ["", "   ", "\xa0", "N/A", "n/a", "NA", "NM", "nm", "*", "**"])
def test_cells_that_give_no_value_are_nan(cell):
    assert math.isnan(parse(cell))


@pytest.mark.parametrize("cell", ["—", "–", "‒", "-", " — "])
def test_a_dash_is_still_zero(cell):
    """The blank/dash split, pinned so they cannot collapse back together."""
    assert parse(cell) == 0.0


def test_numbers_are_unchanged():
    assert parse("1,346") == 1346.0
    assert parse("(214)") == -214.0
    assert parse("$ 62,146") == 62146.0
