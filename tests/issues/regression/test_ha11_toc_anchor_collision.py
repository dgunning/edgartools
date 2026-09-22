"""Two TOC rows on one anchor no longer return the same span twice (edgartools-ha11).

On pg/10q the TOC's Item 5 and Item 6 rows both resolve to the body anchor
``…_115``, and both keys sliced to the identical 2,628 characters. Nothing
raised, both lookups returned real text, and one of them was simply the wrong
item's — the quiet kind of wrong answer, unlike the yrrh failures that returned
222,536 characters for a 975-character section.

THIS WAS NOT UNHANDLED. ``_resolve_anchor_collisions`` was written for GH #920
(Regions Financial: ``obj['Item 7A']`` returning Item 7's MD&A) and separates
colliding anchors whenever the body-header scan can name each item's own anchor.
On this filing that scan returned nothing, so the resolver had no evidence, said
so, and left the mapping alone. The defect was in the evidence, not the policy —
two of them, both in ``_analyze_body_item_headers``:

THE SEPARATOR NEED NOT BE A SPACE
    P&G builds each body heading as a two-cell table row — "Item 5." in one cell,
    "Other Information" in the next — so ``text_content`` reads
    "Item\\xa05.Other Information" with nothing between the period and the title.
    The header pattern required whitespace there (``\\.?\\s+\\S``), so it matched
    NONE of this filing's headings and the scan came back empty. A period may now
    stand in for the separator, but only when a digit does not follow it, which is
    what keeps an 8-K subitem heading ("Item 5.02 Departure of Directors") from
    being read as a bare Item 5.

    The looser read is offered to the collision resolver alone
    (``allow_abutted_title``). That consumer re-points one key already known to
    be wrong; the scan's other two consumers can replace or extend a whole
    filing's mapping, and giving them the same read moved Wells Fargo's 10-K off
    the pattern extractor and onto this scan — the same spans under canonical
    keys instead of semantic ones ('financial_statements' -> 'part_ii_item_8'),
    with gluing in the rendered exhibit tables. A real change, but not one this
    bug is a reason to make.

A PART DIVIDER IS NOT ALWAYS BOLD
    With the headers matching, every Part I item was keyed into Part II: P&G sets
    "PART I. FINANCIAL INFORMATION" at ``font-weight:400`` and only "PART II.
    OTHER INFORMATION" at 700, so the scan's bold gate saw the second divider and
    never the first, leaving the Part context the filing's own table of contents
    had set. An unbold divider is now accepted when the WHOLE text is
    divider-shaped — a bare "PART I", or a Part number, a punctuation separator
    and a short title. "Part II of this report contains …" has no separator and
    does not qualify, which is what keeps prose out of the Part context.

BLAST RADIUS, measured across all 115 fixtures of the four item-based forms by
dumping {section: len(text)} before and after, and flagging any two keys in one
filing whose text is byte-identical. ONE filing changes:

    10-Q  pg/10q    part_ii_item_5   2,628 ->   306   (was Item 6's span)
                    part_ii_item_6   2,628 -> 2,320

Nothing else moved. Of the four filings with byte-identical sibling spans before
the fix, pg is the only one this bug explains: axp/10k's four Part III items
share one span because the filing combines them under a single "ITEMS 10, 11, 12
and 13." heading, which is correct, and the two 20-F duplicates come from a
different mechanism — page-number anchors, and a phantom ``part_iii_item_6`` key
on a form whose Part III is Items 17-19 — tracked as edgartools-rc46.

FIXTURE NOTE. ``tests/fixtures/html`` is TRACKED, so these assertions run in CI.
"""
import pathlib

import pytest

from edgar.company_reports.ten_q import TenQ
from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
PG_10Q = sorted((FIXTURES / "html" / "pg" / "10q").glob("*.html"))[0]


class FixtureFiling:
    """The minimum surface the report classes touch, backed by a local file."""

    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def pg_sections():
    html = PG_10Q.read_text(encoding="utf-8", errors="replace")
    document = HTMLParser(ParserConfig(form="10-Q", detect_sections=True)).parse(html)
    return document.sections


def test_items_5_and_6_are_different_sections(pg_sections):
    """The bug itself: one span was returned under both keys."""
    item_5 = pg_sections["part_ii_item_5"].text()
    item_6 = pg_sections["part_ii_item_6"].text()

    assert item_5 != item_6
    assert len(item_5) == 306
    assert len(item_6) == 2320
    # Content, not just length — each key must hold ITS item.
    assert item_5.startswith("Item\xa05.Other Information")
    assert "Rule 10b5-1 trading arrangement" in item_5
    assert "Item\xa06.Exhibits" in item_6
    assert "Amended Articles of Incorporation" in item_6


def test_the_collision_is_visible_through_the_report_object():
    """The user-facing surface, which is where the wrong answer was returned."""
    report = TenQ(FixtureFiling(PG_10Q, "10-Q"))

    item_5 = report.get_item_with_part("Part II", "Item 5")
    item_6 = report.get_item_with_part("Part II", "Item 6")

    assert item_5 is not None and item_6 is not None
    assert item_5 != item_6
    assert len(item_5) == 306


def test_body_header_scan_reads_headers_whose_title_abuts_the_period():
    """The evidence the resolver needs: this scan used to return nothing here."""
    html = PG_10Q.read_text(encoding="utf-8", errors="replace")
    analyzer = TOCAnalyzer(form="10-Q")
    tree = analyzer._ensure_tree(html, None)

    # The strict read — what the scan's other consumers still get — finds none
    # of this filing's headings, which is why the collision went unseparated.
    assert analyzer._analyze_body_item_headers(html, tree=tree) == {}

    mapping = analyzer._analyze_body_item_headers(html, tree=tree, allow_abutted_title=True)

    # Every item this filing carries, under the Part it is actually filed in —
    # the Part I items were keyed into Part II while the unbold "PART I."
    # divider was invisible to the scan.
    assert set(mapping) == {
        "part_i_item_1", "part_i_item_2", "part_i_item_3", "part_i_item_4",
        "part_ii_item_1", "part_ii_item_1a", "part_ii_item_2",
        "part_ii_item_5", "part_ii_item_6",
    }
    # Each item must bring its own anchor; a shared one is what the collision
    # resolver cannot separate.
    assert len(set(mapping.values())) == len(mapping)


@pytest.mark.parametrize(
    "text,expected",
    [
        # The heading shape this bead is about: no space after the period.
        ("Item\xa05.Other Information", ("5", "")),
        ("Item 1.Financial Statements", ("1", "")),
        ("ITEM 1A.RISK FACTORS", ("1", "A")),
        # The shapes that already worked stay working.
        ("Item 1A. Risk Factors", ("1", "A")),
        ("Item 15 Exhibits", ("15", "")),
        # An 8-K subitem is NOT a bare item — a digit after the period is the
        # tell, and reading "Item 5.02" as Item 5 would map the wrong span.
        ("Item 5.02 Departure of Directors", None),
        ("Item 4.05 Changes in Registrant's Certifying Accountant", None),
        # A bare TOC cell has no title and is still not a heading.
        ("Item 5.", None),
        # Prose cross-references start with "Part", not "Item N".
        ("Items 1 and 2. Business and Properties", None),
    ],
)
def test_body_item_header_pattern(text, expected):
    match = TOCAnalyzer._BODY_ITEM_HEADER_ABUTTED.match(text)
    assert (match.groups() if match else None) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("PART I", "I"),
        ("PART I. FINANCIAL INFORMATION", "I"),
        ("PART II. OTHER INFORMATION", "II"),
        ("Part III - Directors and Officers", "III"),
        # Prose: no separator after the Part number, so the Part context of
        # every item after it is left alone.
        ("Part II of this report contains forward-looking statements", None),
    ],
)
def test_unbold_part_divider_pattern(text, expected):
    match = TOCAnalyzer._BODY_PART_DIVIDER_STANDALONE.match(text)
    assert (match.group(1).upper() if match else None) == expected
