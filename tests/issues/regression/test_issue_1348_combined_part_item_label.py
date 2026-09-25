"""Regression: a TOC label reading "Part I, Item 2" names the item, not just the part.

GH #1348 (EDISON INTERNATIONAL 10-Q for Q3 2025, accession
0000827052-25-000100). Each row of this Workiva TOC carries three links to one
anchor — ``[title, page, "Part I, Item 2"]`` — and the TOC has no part-header
rows at all, so the combined label is the row's only part and item evidence.

The bug: ``_parse_item_from_text`` only reads an item label that *opens* with
"Item", so the part regex took "Part I" and discarded ", Item 2". The Workiva
parser then treated every row as a part header and dropped it, and the generic
parser's ``_normalize_section_name`` reduced the row to "Part I", which
``_build_section_mapping`` drops by design. The TOC contributed only
``part_i_signatures``; the pattern extractor supplied a 346,454-char Item 2 that
ran through the financial statements, and Part I Items 1, 3 and 4 were absent
(``obj["PART I, Item 3"]`` returned nothing).

The TOC is also split across two page tables (Part I Items 2, 3, 1 in the first,
Item 4 onward in the second); the Workiva parser read only the second.

The fix: ``TOCAnalyzer._combined_part_item_label`` recognises text that is
*entirely* a combined label and returns both halves. Both parsers use it — the
part is taken per row, before the key is built — and the Workiva parser follows
the TOC into neighbouring tables that carry combined labels. The match is
anchored at both ends so cross-reference prose ("See Part II, Item 7 of our
Annual Report") cannot claim a key (the false-positive family of GH #905/#918).

Offline (local fixture).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1348
"""
from pathlib import Path

import pytest

from edgar.company_reports.ten_q import TenQ
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

_FIXTURE = (Path(__file__).resolve().parents[2]
            / "fixtures" / "html" / "eix" / "10q" / "eix-10-q-2025-10-28.html")


class _FixtureFiling:
    """The minimum surface TenQ touches, backed by the local fixture."""

    filing_date = None
    form = "10-Q"
    company = "EDISON INTERNATIONAL"
    accession_number = "0000827052-25-000100"

    def __init__(self, path: Path):
        self._path = path
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def tenq():
    """Parse the Edison 10-Q once for the whole module."""
    assert _FIXTURE.exists(), f"{_FIXTURE} is tracked and must be present"
    return TenQ(_FixtureFiling(_FIXTURE))


# --- the helper ---------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Part I, Item 2", ("Part I", "Item 2")),
    ("Part II, Item 1", ("Part II", "Item 1")),
    ("Part II Item 5", ("Part II", "Item 5")),          # Edison's own comma-less row
    ("PART II - ITEM 1A", ("Part II", "Item 1A")),
    ("Part I — Item 3.", ("Part I", "Item 3")),
    ("Part I, Item\xa01", ("Part I", "Item 1")),        # Workiva's non-breaking space
    ("Part I,​ Item 2", ("Part I", "Item 2")),     # zero-width space inside the label
    ("  part iv, item 15  ", ("Part IV", "Item 15")),
])
def test_combined_label_names_part_and_item(text, expected):
    assert TOCAnalyzer._combined_part_item_label(text) == expected


@pytest.mark.parametrize("text", [
    "See Part II, Item 7 of our Annual Report",
    "Part II, Item 7 of our Annual Report on Form 10-K",
    "Part I",
    "Item 2",
    "Part I, Item 2. Management's Discussion and Analysis",
    "",
])
def test_anything_but_a_whole_combined_label_is_not_one(text):
    assert TOCAnalyzer._combined_part_item_label(text) is None


def test_a_bare_part_label_still_reads_as_a_part():
    """The part-header path is untouched: "Part I" alone is still a part."""
    an = TOCAnalyzer(form="10-Q")
    assert an._parse_item_from_text("Part I") == "Part I"
    assert an._normalize_section_name("Part II") == "Part II"


def test_normalize_reads_the_item_from_a_combined_label():
    """The generic parser's normaliser returned "Part I" here, dropping the row."""
    an = TOCAnalyzer(form="10-Q")
    assert an._normalize_section_name("Part I, Item 2") == "Item 2"
    assert an._normalize_section_name("PART II - ITEM 1A") == "Item 1A"


# --- both TOC parsers on the real filing ---------------------------------------

_EXPECTED_ITEMS = {
    "part_i_item_1", "part_i_item_2", "part_i_item_3", "part_i_item_4",
    "part_ii_item_1", "part_ii_item_2", "part_ii_item_5", "part_ii_item_6",
}


@pytest.fixture(scope="module")
def html():
    return _FIXTURE.read_text(encoding="utf-8", errors="replace")


def test_workiva_parser_maps_every_item(html):
    """Edison is a Workiva filing; this is the path it actually takes."""
    mapping = TOCAnalyzer(form="10-Q")._analyze_workiva_toc(html)
    assert set(mapping) == _EXPECTED_ITEMS | {"part_ii_signatures"}
    assert mapping["part_i_item_3"] == "ic8d4942da5f84528abe28ed8dec1dd44_106"


def test_generic_parser_maps_every_item(html):
    """The generic fallback found nothing here ({}) before the fix."""
    mapping = TOCAnalyzer(form="10-Q")._analyze_generic_toc(html)
    assert set(mapping) == _EXPECTED_ITEMS
    assert mapping["part_i_item_3"] == "ic8d4942da5f84528abe28ed8dec1dd44_106"


# --- the user-visible sections ---------------------------------------------------

def test_section_set(tenq):
    """Nine sections, where the buggy parse had three (one of them misnamed)."""
    assert sorted(tenq.document.sections) == sorted(_EXPECTED_ITEMS | {"part_ii_signatures"})


@pytest.mark.parametrize("key, opening", [
    ("PART I, Item 1", "CONDENSED CONSOLIDATED FINANCIAL STATEMENTS"),
    ("PART I, Item 2", "MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION"),
    ("PART I, Item 3", "QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK"),
    ("PART I, Item 4", "CONTROLS AND PROCEDURES"),
    ("PART II, Item 1", "LEGAL PROCEEDINGS"),
    ("PART II, Item 2", "UNREGISTERED SALES OF EQUITY SECURITIES AND USE OF PROCEEDS"),
    ("PART II, Item 5", "OTHER INFORMATION"),
    ("PART II, Item 6", "EXHIBITS"),
])
def test_each_item_opens_with_its_own_heading(tenq, key, opening):
    text = tenq[key]
    assert text, f"{key} is empty"
    body = text.removeprefix("Table of Contents").lstrip()
    assert body.startswith(opening), f"{key} opens with {body[:80]!r}"


def test_item_3_is_the_market_risk_stub(tenq):
    """Item 3 was missing; it is a one-paragraph pointer into the MD&A."""
    item3 = tenq["PART I, Item 3"]
    assert len(item3) == 205
    assert 'under the heading "Market Risk Exposures"' in item3


def test_item_4_is_controls_and_stops_before_part_ii(tenq):
    item4 = tenq["PART I, Item 4"]
    assert len(item4) == 1493
    assert "Disclosure Controls and Procedures" in item4
    assert "LEGAL PROCEEDINGS" not in item4


def test_item_2_no_longer_swallows_the_financial_statements(tenq):
    """The pattern-extracted Item 2 was 346,454 chars and ran into Item 1's statements."""
    item2 = tenq["PART I, Item 2"]
    assert len(item2) == 89_652
    assert item2.rstrip().endswith('Summary of Significant Accounting Policies—New Accounting Guidance."')
    assert "QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK" not in item2
