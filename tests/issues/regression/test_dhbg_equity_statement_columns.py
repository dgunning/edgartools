"""A statement whose columns are not dates lost every column, so the frame came
back with its rows and nothing else.

bead edgartools-dhbg. The bead's title says "empty DataFrame for all income
statements"; that is not what happens. Income statements are fine -- on the three
filings the bead names, they extract as (29, 15), (38, 3) and (24, 4). The report
that breaks is the STATEMENT OF SHAREHOLDERS' EQUITY, and its shape is (N, 0)
rather than (0, 0).

`FinancialTableExtractor._build_dataframe` kept a column only if its header
matched `PERIOD_PATTERN`, a date regex. An equity roll-forward is broken down by
equity COMPONENT -- 'Total', 'Common stock and additional paid-in capital',
'Retained earnings/(Accumulated deficit)' -- and carries the period in each row
label instead ('Beginning balances at Sep. 30, 2023'). No header matched, so no
column was selected, every row was built with an empty value list, and
`df['Total']` raised KeyError.

Measured across ten filers' latest 10-Ks: 6 statements went from N x 0 to N x 4-8
with their component columns and filed values; the other 57 statements were
byte-identical before and after.

Runs offline against the tracked R6 fixture.
"""

from pathlib import Path

import pytest

from edgar.sgml.table_to_dataframe import extract_statement_dataframe

# Apple's Q2 FY2025 10-Q, condensed statement of shareholders' equity.
R6 = (Path(__file__).resolve().parents[2]
      / "fixtures" / "attachments" / "aapl" / "20250329" / "R6.htm")

# As filed, in dollars after the statement's "in Millions" scaling is applied.
BEGINNING = "Beginning balances at Sep. 30, 2023"
COMPONENTS = {
    "Total": 62_146_000_000,
    "Common stock and additional paid-in capital": 73_812_000_000,
    "Retained earnings/(Accumulated deficit)": -214_000_000,
    "Accumulated other comprehensive income/(loss)": -11_452_000_000,
}


@pytest.fixture(scope="module")
def equity():
    assert R6.exists(), f"missing fixture: {R6}"
    return extract_statement_dataframe(R6.read_text(encoding="utf-8"))


def test_the_component_columns_survive(equity):
    """This is the whole defect: rows present, columns gone."""
    assert equity.shape == (47, 4)
    assert list(equity.columns) == list(COMPONENTS)


def test_the_values_are_the_filed_ones(equity):
    """A frame with columns but wrong numbers would be worse than no frame."""
    row = equity.loc[BEGINNING]
    for component, expected in COMPONENTS.items():
        assert row[component] == expected, component


def test_indexing_a_component_no_longer_raises(equity):
    """The user-visible symptom -- df['Total'] raised KeyError."""
    assert len(equity["Total"]) == 47


def test_the_frame_is_not_reported_as_empty(equity):
    """pandas calls a zero-column frame `.empty`, which is how this hid.

    Two regression tests asserted `.empty` on this very fixture and were green
    because of the defect; both now assert the extraction instead.
    """
    assert not equity.empty


def test_scaling_metadata_is_attached(equity):
    """The header says "$ in Millions"; without it the values are 1e6 too small."""
    assert equity.attrs["units"] == "millions"
    assert equity.attrs["scaling_factor"] == 1_000_000
    assert equity.attrs["currency"] == "USD"
