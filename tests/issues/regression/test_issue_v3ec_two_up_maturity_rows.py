"""Two-up maturity rows are data, not headers (edgartools-v3ec).

WHAT WAS BROKEN. UnitedHealth's long-term debt schedule is laid out *two-up* —
two debt series side by side on every row, each with its own maturity:

    $750 3.5%, Feb 2024 | — | 750 | $850 5.8%, Mar 2036 | 838 | 838

So every data row names two *different* years, and ``_is_header_row``'s
multi-year branch reads that as a 2024-vs-2036 comparison header. 35 of the
table's 40 rows were classified as headers, ``TableNode.rows`` came back with 3,
and the renderer collapsed the rest into almost nothing. Measured against the
legacy rendering, which keeps all 66 rows: the new output retained **2 of 66
maturities and 16 of 66 coupon rates**.

Neither existing guard could catch it. The date-range guard needs a full
"March 1, 2024—March 31, 2024" span; "Feb 2024" is not one. ``_has_prose_cell``
(edgartools-2vzk) needs a cell of 100+ characters; these are short numeric cells.

THE FIX. A row carrying actual figures is a data row however many years it names
— header rows label periods, they do not hold dollar amounts. Currency and
thousands-grouping only, deliberately *not* bare decimals, which turn up in
legitimate header labels where a dollar amount never does.

WHY IT MATTERS. A long-term debt schedule is where the maturity wall lives.
Losing the maturities means the rendered filing cannot answer when the debt comes
due — and it fails silently, with the surrounding narrative ("Carrying Value",
"Commercial paper") still present, so the output reads as complete.

HOW IT WAS FOUND. Not by a bug report — by trying to *discount* it. The markdown
parity harness flagged 186 legacy-only numbers on this filing, and the standing
hypothesis was that they were an artifact of legacy gluing values together
(``$1,000`` + ``2.875%`` rendering as ``$1,0002.875%``). Legacy does glue them.
But checking whether the new side had the pieces separately showed it had neither
— which turned a proposed harness adjustment into this bug. Kept in the docstring
because the near-miss is the lesson: a discount that had been applied on the
original reasoning would have hidden this permanently.

GROUND TRUTH. UnitedHealth FY2024 10-K, filed 2025-02-27. The schedule runs 66
series; ``$1,000 2.875%, Aug 2029`` and ``$750 3.5%, Feb 2024`` were read off the
filing itself.
"""
import re
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.table_nodes import TableNode

FIXTURE = (Path(__file__).parent.parent.parent
           / "fixtures" / "html" / "unh" / "10k" / "unh-10-k-2025-02-27.html")

# One series of the schedule: principal, coupon, maturity.
#
# The whitespace between principal and coupon is optional on purpose, so this
# matches both renderings. Legacy glues them ("$1,0002.875%") — that gluing is
# what sent the original investigation down the wrong path — while the new
# renderer spaces them correctly ("$1,000 2.875%"). Matching both keeps the
# expected counts comparable across the two.
DEBT_ROW_RE = re.compile(r"\$(\d[\d,]*?)\s*(\d\.\d+)%,\s+(\w{3} \d{4})")


@pytest.fixture(scope="module")
def unh_document():
    assert FIXTURE.exists(), f"committed UNH 10-K fixture is missing: {FIXTURE}"
    return HTMLParser(ParserConfig(form="10-K")).parse(
        FIXTURE.read_text(errors="ignore"))


@pytest.fixture(scope="module")
def unh_markdown(unh_document):
    return unh_document.to_markdown()


@pytest.fixture(scope="module")
def debt_table(unh_document):
    for node in unh_document.root.walk():
        if isinstance(node, TableNode) and "Carrying Value as of" in (node.text() or ""):
            return node
    raise AssertionError(
        "UNH's long-term debt schedule (the table headed 'Carrying Value as of') "
        "is absent from the parsed document. That table not being found IS the "
        "v3ec bug's territory, so it fails here rather than skipping."
    )


@pytest.mark.fast
class TestTheScheduleReachesTheOutput:

    def test_a_specific_series_survives(self, unh_markdown):
        """The narrowest statement of the bug: one note, by rate and maturity."""
        assert "2.875" in unh_markdown, "coupon rate of the Aug 2029 notes is missing"
        assert "Aug 2029" in unh_markdown, (
            "maturity of the 2.875% notes is missing — this is the figure a "
            "maturity-wall question needs"
        )

    def test_most_of_the_schedule_survives(self, unh_markdown):
        """Rates and maturities across the whole schedule, not one lucky row.

        Asserted as a floor rather than an exact count: the point is that the
        rows are present at all, and pinning 66 exactly would break on an
        unrelated rendering tweak.
        """
        maturities = sorted({m for _, _, m in DEBT_ROW_RE.findall(unh_markdown)})
        rates = sorted({r for _, r, _ in DEBT_ROW_RE.findall(unh_markdown)})
        assert len(maturities) >= 40, (
            f"only {len(maturities)} distinct maturities rendered; before the fix "
            "the schedule collapsed to 2 of 66"
        )
        assert len(rates) >= 40, f"only {len(rates)} distinct coupon rates rendered"

    def test_the_rows_are_classified_as_data(self, debt_table):
        """The mechanism. Row/header split is what the renderer acts on."""
        rows = debt_table.rows or []
        headers = debt_table.headers or []
        assert len(rows) > 30, (
            f"debt schedule has {len(rows)} data rows and {len(headers)} header "
            "rows; before the fix it was 3 and 37, because every two-up row "
            "names two different maturity years"
        )
        assert len(headers) <= 5, (
            f"{len(headers)} header rows — the multi-year signal is over-firing again"
        )


@pytest.mark.fast
class TestTheHeaderPredicateItself:
    """Direct tests of the veto, so a failure points at the rule not the fixture."""

    @staticmethod
    def _is_header(html_row: str) -> bool:
        from lxml import html as lxml_html

        from edgar.documents.strategies.table_processing import TableProcessor
        tr = lxml_html.fromstring(
            f"<table><tbody>{html_row}</tbody></table>").find(".//tr")
        return bool(TableProcessor(ParserConfig(form="10-K"))._is_header_row(tr))

    def test_a_two_up_maturity_row_is_data(self):
        row = ("<tr><td>$750 3.5%, Feb 2024</td><td>—</td><td>750</td>"
               "<td>$850 5.8%, Mar 2036</td><td>838</td><td>838</td></tr>")
        assert not self._is_header(row), (
            "a row holding dollar amounts is a data row however many years it names"
        )

    def test_a_real_multi_year_header_is_still_a_header(self):
        """The veto must not disarm the signal it was guarding."""
        row = "<tr><td>(in millions)</td><td>2024</td><td>2023</td><td>2022</td></tr>"
        assert self._is_header(row), (
            "a bare multi-year comparison header must still be detected — the "
            "veto keys on figures, and this row has none"
        )

    def test_bare_decimals_do_not_disarm_the_signal(self):
        """Why the veto is currency + thousands-grouping, not any number.

        Decimals appear in legitimate header labels; dollar amounts do not. If
        the veto keyed on decimals too, a header like this would be misread as
        data — the exact inverse of the bug.
        """
        row = "<tr><td>Item 7A.</td><td>2024</td><td>2023</td></tr>"
        assert self._is_header(row)
