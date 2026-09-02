"""`Report.get_dataframe()` returned an empty DataFrame for every filing.

Bead: edgartools-yq1l. Found while doing edgartools-07lk.3, which had to account
for `edgar/sgml/table_to_dataframe.py` — the last live non-legacy importer of
`edgar.files`.

WHAT WAS BROKEN. The module is wired for the MODERN parser: it imports
`TableNode` from `edgar.documents.table_nodes` and `extract_statement_dataframe`
parses with `HTMLParser`. But `extract_table_to_dataframe` read
`table_node._processed`, a cached_property that exists only on the LEGACY
`TableNode` in `edgar/files/html.py`. The modern node has no such attribute, so
every call raised `AttributeError` — and the bare `except Exception` returned
`pd.DataFrame()`, turning a hard failure into a plausible empty result.

Measured before the fix: 642 of 642 tables across 21 real filings raised, and
0 of 42 Apple R-files produced a non-empty frame. After: 41 of 42. The one that
stays empty is R6, a checkbox page whose tables hold a single "X" — empty is the
right answer there, which is why the assertion below is on named statements
rather than on a count.

WHY NO TEST CAUGHT IT. `tests/test_table_extraction.py` called the extractor and
PRINTED, and guarded its only value checks behind `if not df2.empty:` — so the
empty result skipped every assertion it had. It also built half its evidence
with the LEGACY `Document`, which is the parser that does have `_processed`, and
so exercised a path `extract_statement_dataframe` never takes.

THE ASSERTIONS BELOW ARE FILED VALUES, not shapes. Apple's Q2 FY2025 10-Q
(period ended 2025-03-29) reports net sales of $95,359 million for the three
months and $219,659 million for the six.
"""
import pathlib

import pytest

from edgar.sgml.table_to_dataframe import extract_statement_dataframe

pytestmark = pytest.mark.fast

# Tracked fixture: the R-file for Apple's Q2 FY2025 condensed consolidated
# statements of operations.
R2 = (pathlib.Path(__file__).parent.parent.parent
      / "fixtures" / "attachments" / "aapl" / "20250329" / "R2.htm")


@pytest.fixture(scope="module")
def income_statement():
    return extract_statement_dataframe(R2.read_text(encoding="utf-8"))


def test_income_statement_is_not_empty(income_statement):
    """The failure this bead was filed for: always `(0, 0)`."""
    assert not income_statement.empty
    assert income_statement.shape == (24, 4)


def test_net_sales_matches_the_filed_figures(income_statement):
    """Values, not existence. $ in millions, so the frame carries them scaled."""
    three_months = "3 Months Ended Mar. 29, 2025"
    six_months = "6 Months Ended Mar. 29, 2025"

    assert income_statement.loc["Net sales", three_months].iloc[0] == 95_359_000_000
    assert income_statement.loc["Net sales", six_months].iloc[0] == 219_659_000_000
    assert income_statement.loc["Gross margin", three_months] == 44_867_000_000
    assert income_statement.loc["Operating income", three_months] == 29_589_000_000


def test_period_columns_line_up_with_the_figures_beneath_them(income_statement):
    """The stub column is not labelled by the period header row.

    Apple's income statement has a 5-wide body and a 4-wide date row. Padding
    that row on the LEFT — the natural way to write it — put "Mar. 29, 2025" on
    the line-item column and shifted every date one column away from the figures
    it describes. The frame still parsed and still had the right shape; every
    number in it was simply attributed to the wrong period.
    """
    assert list(income_statement.columns) == [
        "3 Months Ended Mar. 29, 2025",
        "3 Months Ended Mar. 30, 2024",
        "6 Months Ended Mar. 29, 2025",
        "6 Months Ended Mar. 30, 2024",
    ]
    # The prior-year comparatives, which is the check that fails if the columns
    # are merely relabelled rather than realigned.
    assert income_statement.loc["Gross margin", "3 Months Ended Mar. 30, 2024"] == 42_271_000_000


def test_money_scale_ignores_a_share_count_scale(income_statement):
    """The header reads "shares in Thousands, $ in Millions".

    Taking the first units match read "Thousands" and scaled every monetary
    figure by 1,000 — three orders of magnitude low, from a header that states
    the right scale a few words later.
    """
    assert income_statement.attrs["units"] == "millions"
    assert income_statement.attrs["scaling_factor"] == 1_000_000


def test_currency_is_not_read_out_of_the_word_unaudited(income_statement):
    """`AUD` with no word boundary matches inside "Unaudited", which appears in
    the title of essentially every unaudited interim statement — so this
    statement reported Australian dollars."""
    assert income_statement.attrs["currency"] == "USD"


def test_period_type_is_duration_for_an_income_statement(income_statement):
    assert income_statement.attrs["period_type"] == "duration"


def test_a_table_with_nothing_financial_in_it_is_still_empty():
    """R6 holds single-cell "X" tables. Empty is correct; the fix must not
    manufacture a frame out of them."""
    r6 = R2.parent / "R6.htm"
    assert extract_statement_dataframe(r6.read_text(encoding="utf-8")).empty
