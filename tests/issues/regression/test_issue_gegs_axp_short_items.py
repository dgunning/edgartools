"""Regression: AXP 10-K legitimately-short items aren't over-rescued.

edgartools-gegs (axp, surfaced by the llmp.5 scoring harness). American Express
leaves several items deliberately brief — Item 3 Legal Proceedings is incorporated
by reference ("Refer to Note 12 ..."), Item 4 Mine Safety and Item 9C are "Not
applicable", Item 7A points to the MD&A Risk Management section. Each correctly
extracts to under ~200 chars between its anchors.

The bug: ``get_section_text`` treated *any* sub-200-char item as a mis-anchored
section and called ``_find_actual_item_content``, an HTML-regex rescue built for
TOC anchors that land on a PART header (NovoCure). That rescue ran past the end
anchor and swallowed every following item — Item 3 ballooned to 166KB (all of
Legal + Mine Safety + Item 5 ...), Item 7A to 198KB (the entire Item 8 financial
body).

The fix: skip the rescue when the short extraction already sits on the item's own
heading (``_text_on_item_heading``). A correctly-anchored brief item keeps its
short text; only a genuinely mis-anchored one (no item title in the slice) is
hunted for. The genuine large items (7 MD&A, 8 financials) are unaffected.

Offline (local fixture); asserts the short items stay short and carry their own
content, and the large neighbours they used to swallow stay intact.
"""
from pathlib import Path

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "axp" / "10k" / "axp-10-k-2025-02-07.html"


def _sections():
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_FIXTURE.read_text())
    return doc.sections


def test_item3_legal_proceedings_stays_a_reference_stub():
    """Item 3 keeps its incorporated-by-reference one-liner (was 166KB over-capture)."""
    item3 = _sections()["part_i_item_3"].text()
    assert len(item3) < 500, f"Item 3 over-extracted ({len(item3)} chars) — rescue swallowed neighbours"
    assert "LEGAL PROCEEDINGS" in item3
    assert "Note 12" in item3
    # The swallowed-neighbour signature: Item 5's market text must NOT be present.
    assert "MARKET FOR REGISTRANT" not in item3


def test_item4_mine_safety_stays_not_applicable():
    """Item 4 keeps 'Not applicable' (was 166KB over-capture)."""
    item4 = _sections()["part_i_item_4"].text()
    assert len(item4) < 300, f"Item 4 over-extracted ({len(item4)} chars)"
    assert "MINE SAFETY" in item4
    assert "Not applicable" in item4


def test_item7a_points_to_mda_not_the_financials():
    """Item 7A is a pointer to MD&A Risk Management, not the Item 8 financial body."""
    item7a = _sections()["part_ii_item_7a"].text()
    assert len(item7a) < 500, f"Item 7A over-extracted ({len(item7a)} chars) — swallowed Item 8"
    assert "QUANTITATIVE AND QUALITATIVE" in item7a
    # The over-capture used to pull in the financial statements' MD&A report.
    assert "MANAGEMENT'S REPORT" not in item7a.upper()


def test_large_neighbours_intact():
    """The genuine large items the rescue used to swallow are unchanged."""
    secs = _sections()
    item7 = secs["part_ii_item_7"].text()
    item8 = secs["part_ii_item_8"].text()
    assert len(item7) > 100_000, f"Item 7 MD&A regressed ({len(item7)} chars)"
    assert len(item8) > 100_000, f"Item 8 financials regressed ({len(item8)} chars)"
