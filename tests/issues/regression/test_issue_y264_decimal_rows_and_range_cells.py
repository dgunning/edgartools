"""Decimal-only rows and range cells are data, not headers (edgartools-y264).

The follow-up edgartools-v3ec left open. Fixing the two-up maturity rows took
UnitedHealth's FY2024 10-K from 186 legacy-only numbers to 82, and the closing
note said the residual was "cause unexamined". Examining it found that 69 of the
82 are not our loss at all — they are *legacy* running two figures together
(``$1,000`` + ``2.875%`` rendering as ``$1,0002.875%``), the numeric counterpart
of the word-gluing the parity harness already discounts — and 5 are page-number
footers the new parser correctly drops. The remaining 8 were real, and came from
two more branches of ``_is_header_row``, each missing the same kind of
figures veto that v3ec added to a third.

WHAT WAS BROKEN — 1. THE BUYBACK TABLE. Item 5's issuer-purchases table lost two
of its three months::

    November 30, 2024 | 0.9 | 593.39 | 0.9 | 38.7
    December 31, 2024 | 5.6 | 513.93 | 5.6 | 33.1

A single date matches the period-header pattern, and that branch's list of
"strong data indicators" recognised ``$``, thousands separators, arithmetic and
parenthesised negatives — but *not a plain decimal*. It was the only one of the
three near-identical ``data_pattern`` literals in the function that omitted
``\\d+\\.\\d+``. October survived by luck: its average-price cell carried a stray
``$`` in a column of its own.

WHAT WAS BROKEN — 2. THE STOCK-OPTION ASSUMPTIONS. Three of that table's five
rows were classified as headers::

    Expected volatility | 25.5% - 30.7% | 29.7% - 30.6% | 30.6% - 30.8%

The content-type-ratio branch — the last-resort "mostly text means header" rule
— decided a cell was numeric by stripping ``$%,()``, dropping ``.`` and ``-``,
and calling ``isdigit()``. On a RANGE the spaces either side of the dash
survive, and ``'255  307'.isdigit()`` is False, so every range cell counted as
text. The row scored 4 text against 0 numbers. ``Forfeiture rate 5.0%`` survived
precisely because a single value is not a range — so the rendered filing kept
the two rows nobody asks about and dropped the three carrying the assumptions.

WHAT WAS BROKEN — 3. THE SIBLING BRANCH, on purpose. v3ec observed that the
``year_cells >= 2`` branch had the same missing veto as the branch it fixed, and
left it alone as never-observed. Never-observed is not unobservable, and a
synthetic row is enough to show it: see ``TestTheSiblingBranchWasAlsoMissingIt``.

WHY IT MATTERS. Both real tables answer questions the filing exists to answer —
what the company paid to buy back its own stock, and what volatility assumption
sits under its option expense. Both failed silently: the tables were still
present, still had a header and some rows, and read as complete.

GROUND TRUTH. UnitedHealth Group FY2024 10-K, filed 2025-02-27, read off the
filing itself. Fourth-quarter issuer purchases: October 2.6m shares at $568.70,
November 0.9m at $593.39, December 5.6m at $513.93, total 9.1m at $537.14.
Stock-option assumptions for 2024: risk-free 3.6%-4.4%, expected volatility
25.5%-30.7%, dividend yield 1.4%-1.5%, forfeiture 5.0%, expected life 4.6 years.
"""
from pathlib import Path

import pytest
from lxml import html as lxml_html

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.strategies.table_processing import TableProcessor

FIXTURE = (Path(__file__).parent.parent.parent
           / "fixtures" / "html" / "unh" / "10k" / "unh-10-k-2025-02-27.html")


@pytest.fixture(scope="module")
def unh_markdown():
    assert FIXTURE.exists(), f"committed UNH 10-K fixture is missing: {FIXTURE}"
    return HTMLParser(ParserConfig(form="10-K")).parse(
        FIXTURE.read_text(errors="ignore")).to_markdown()


def data_row(markdown: str, label: str) -> str:
    """The rendered table row whose first cell is ``label``.

    Scoped to the row rather than searching the whole document on purpose. Half
    these figures — 1.4, 5.6, 0.9 — occur in dozens of unrelated tables in a
    10-K, so a bare ``value in markdown`` passes whether or not the row survived.
    One of these assertions was written that way first and stayed green against
    the unfixed parser, which is the failure mode this helper exists to remove.

    A header-classified row is not merely reordered, it is merged into the
    header line and loses its label as a leading cell, so its absence here is
    exactly the defect under test.
    """
    for line in markdown.splitlines():
        if line.startswith(f"| {label} |"):
            return line
    raise AssertionError(
        f"no rendered data row starts with '{label}' — the row was classified "
        "as a header and collapsed into the table's header line"
    )


@pytest.mark.fast
class TestTheBuybackTableSurvives:
    """Item 5, Issuer Purchases of Equity Securities, fourth quarter 2024."""

    @pytest.mark.parametrize("month, shares, price, remaining", [
        ("October 31, 2024", "2.6", "568.70", "39.6"),
        ("November 30, 2024", "0.9", "593.39", "38.7"),
        ("December 31, 2024", "5.6", "513.93", "33.1"),
    ])
    def test_each_month_is_rendered(self, unh_markdown, month, shares, price, remaining):
        """November and December vanished entirely; October survived by luck."""
        row = data_row(unh_markdown, month)
        for what, value in (("shares purchased", shares),
                            ("average price paid", price),
                            ("shares remaining authorised", remaining)):
            assert value in row, f"{month}: {what} ({value}) missing from {row!r}"

    def test_the_quarter_totals_are_present(self, unh_markdown):
        """The total row always survived; it is here so a rewrite keeps it."""
        row = data_row(unh_markdown, "Total")
        assert "9.1" in row and "537.14" in row, row


@pytest.mark.fast
class TestTheStockOptionAssumptionsSurvive:
    """Range-valued rows of the grant-date fair value assumptions table."""

    @pytest.mark.parametrize("label, values", [
        ("Risk-free interest rate", ("3.6", "4.4", "3.8", "4.6", "1.9", "4.3")),
        ("Expected volatility", ("25.5", "30.7", "29.7", "30.6", "30.8")),
        ("Expected dividend yield", ("1.4", "1.5", "1.3", "1.2")),
    ])
    def test_a_range_valued_row_is_rendered(self, unh_markdown, label, values):
        row = data_row(unh_markdown, label)
        missing = [v for v in values if v not in row]
        assert not missing, (
            f"'{label}' rendered without {missing} — the row's range cells were "
            f"counted as text and the row was classified as a header: {row!r}"
        )

    def test_the_single_valued_rows_still_render(self, unh_markdown):
        """These two always survived. Pinned so a fix cannot trade one for the other."""
        assert "5.0%" in data_row(unh_markdown, "Forfeiture rate")
        assert "4.6" in data_row(unh_markdown, "Expected life in years")


def _is_header(html_row: str) -> bool:
    tr = lxml_html.fromstring(
        f"<table><tbody>{html_row}</tbody></table>").find(".//tr")
    return bool(TableProcessor(ParserConfig(form="10-K"))._is_header_row(tr))


@pytest.mark.fast
class TestTheHeaderPredicateItself:
    """Direct tests, so a failure points at the rule rather than the fixture."""

    def test_a_dated_row_of_decimals_is_data(self):
        row = ("<tr><td>November 30, 2024</td><td>0.9</td><td>593.39</td>"
               "<td>0.9</td><td>38.7</td></tr>")
        assert not _is_header(row), (
            "a row of figures is a data row even when its label is a date and "
            "none of those figures carries a dollar sign"
        )

    def test_a_row_of_ranges_is_data(self):
        row = ("<tr><td>Expected volatility</td><td>25.5% - 30.7%</td>"
               "<td>29.7% - 30.6%</td><td>30.6% - 30.8%</td></tr>")
        assert not _is_header(row), (
            "a cell holding a range holds figures; counting it as text makes an "
            "all-ranges data row look like an all-text header"
        )

    @pytest.mark.parametrize("row, why", [
        ("<tr><td></td><td>December 31, 2024</td><td>December 31, 2023</td></tr>",
         "a bare pair of period dates is still a header"),
        ("<tr><td>(in millions)</td><td>2024</td><td>2023</td></tr>",
         "a bare multi-year comparison header is still a header"),
        ("<tr><td>2024</td><td>December 31, 2023</td></tr>",
         "a year cell plus a date phrase, with no figures, is still a header"),
    ])
    def test_genuine_headers_are_still_detected(self, row, why):
        """The vetoes must not disarm the signals they guard."""
        assert _is_header(row), why

    def test_a_lone_currency_symbol_is_still_text(self):
        """``$`` in a column of its own must not count as a figure cell.

        It is how the buyback table is laid out, and treating it as numeric
        would shift the text/number ratio on every financial table in the corpus.
        """
        assert not TableProcessor._is_figure_cell("$")
        assert not TableProcessor._is_figure_cell("—")
        assert not TableProcessor._is_figure_cell("December 31, 2024")
        assert TableProcessor._is_figure_cell("25.5% - 30.7%")
        assert TableProcessor._is_figure_cell("(1,234)")


@pytest.mark.fast
class TestTheSiblingBranchWasAlsoMissingIt:
    """The follow-up v3ec explicitly deferred.

    v3ec added its figures veto to the ``len(years_found) >= 2`` branch only, and
    recorded that the ``year_cells >= 2`` branch below it had the same gap but
    had never been seen to fire. These rows are the demonstration that it does —
    both were classified as headers before the veto was extended.
    """

    def test_a_schedule_laid_out_year_amount_year_amount_is_data(self):
        row = "<tr><td>2024</td><td>$1,000</td><td>2025</td><td>$2,000</td></tr>"
        assert not _is_header(row), (
            "two year cells do not outrank two dollar amounts — this is the "
            "exact shape v3ec predicted would bite this branch"
        )

    def test_a_year_plus_date_phrase_row_carrying_figures_is_data(self):
        row = "<tr><td>2024</td><td>December 31, 2024</td><td>$1,234</td></tr>"
        assert not _is_header(row)
