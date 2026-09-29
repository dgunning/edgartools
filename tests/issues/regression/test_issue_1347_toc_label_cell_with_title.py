"""Regression: a TOC row with label and title in one cell keeps its item label.

GH #1347 (FIRSTENERGY CORP 10-K, accession 0001031296-26-000046). The TOC puts
the item label and the title in one cell and links only the page number:

    <td>Item 1. Business</td><td><a href="#..._16">1</a></td>

``TOCAnalyzer._extract_preceding_item_label`` only had end-anchored patterns
("Item 1." with nothing after it, or a bare "1"), so every such row yielded an
empty label and was dropped. The TOC parse collapsed to 3 keys taken from
unrelated rows, and ``part_ii_item_7`` pointed at Item 8's anchor:
``obj["Item 7"]`` returned 306,341 chars opening "ITEM 8. FINANCIAL STATEMENTS".

The fix (patch by @sf1tzp): when no end-anchored pattern matches a cell, accept
a leading "Item N." that is followed by a separator and more text. A bare page
number or a label-only cell never reaches that fallback.

Offline (local fixture).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1347
"""
from pathlib import Path

import lxml.html
import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

_FIXTURE = (Path(__file__).resolve().parents[2]
            / "fixtures" / "html" / "fe" / "10k" / "fe-10-k-2026-02-18.html")


@pytest.fixture(scope="module")
def html():
    return _FIXTURE.read_text()


@pytest.fixture(scope="module")
def sections(html):
    """Parse the FirstEnergy 10-K once for the whole module."""
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html)
    return doc.sections


def test_toc_mapping_recovers_every_item(html):
    """The TOC parse finds all 23 items, not 3 from unrelated rows."""
    mapping = TOCAnalyzer(form="10-K").analyze_toc_structure(html)

    assert len(mapping) == 23
    assert mapping["part_i_item_1"] == "ica465ef67e2145429d1d82300b5da233_16"
    assert mapping["part_i_item_1a"] == "ica465ef67e2145429d1d82300b5da233_52"
    # Before the fix Item 7 held Item 8's anchor (_154) and Item 8 held Item 1A's (_52).
    assert mapping["part_ii_item_7"] == "ica465ef67e2145429d1d82300b5da233_79"
    assert mapping["part_ii_item_8"] == "ica465ef67e2145429d1d82300b5da233_154"
    assert mapping["part_iv_item_15"] == "ica465ef67e2145429d1d82300b5da233_361"


def test_item7_is_mdna_not_item8(sections):
    item7 = sections["part_ii_item_7"].text()
    assert item7.startswith("ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS")
    assert "ITEM 8." not in item7[:200]
    assert len(item7) == 247_046  # tables rendered cell by cell (edgartools-wzgu)


def test_item8_opens_with_its_own_heading(sections):
    item8 = sections["part_ii_item_8"].text()
    assert item8.startswith("ITEM 8.")
    assert "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA" in item8[:80]


def test_item1a_opens_with_risk_factors(sections):
    item1a = sections["part_i_item_1a"].text()
    assert item1a.startswith("ITEM 1A.")
    assert "RISK FACTORS" in item1a[:40]


def _label(row_html: str) -> str:
    tree = lxml.html.fromstring(f"<html><body><table><tr>{row_html}</tr></table></body></html>")
    link = tree.xpath("//a")[0]
    return TOCAnalyzer(form="10-K")._extract_preceding_item_label(link)


@pytest.mark.parametrize("row, expected", [
    # The FirstEnergy shape: label + title in one cell, page number linked.
    ('<td>Item 1. Business</td><td><a href="#b">1</a></td>', "Item 1"),
    # Lowercase label, colon separator: normalised like the other branches.
    ('<td>item 1a: risk factors</td><td><a href="#b">20</a></td>', "Item 1A"),
])
def test_label_and_title_in_one_cell(row, expected):
    assert _label(row) == expected


@pytest.mark.parametrize("row, expected", [
    # Label-only cell: still matched by the end-anchored pattern.
    ('<td>Item 1.</td><td><a href="#b">Business</a></td>', "Item 1"),
    # Bare number within the 10-K item range: still read as an item number.
    ('<td>10</td><td><a href="#b">Business</a></td>', "Item 10"),
    # Bare page number beyond the item range: still no label.
    ('<td>108</td><td><a href="#b">Business</a></td>', ""),
    # Title-only cell next to a linked page number: still no label.
    ('<td>Business</td><td><a href="#b">1</a></td>', ""),
    # "Item N" with no separator is not a label-plus-title cell.
    ('<td>Item 7 continued</td><td><a href="#b">1</a></td>', ""),
])
def test_existing_shapes_unchanged(row, expected):
    assert _label(row) == expected


_XOM_10Q = (Path(__file__).resolve().parents[2]
            / "fixtures" / "html" / "xom" / "10q" / "xom-10-q-2025-08-04.html")


def test_last_toc_item_stops_at_signatures():
    """ExxonMobil's 10-Q TOC has the same label-and-title cells, so the fix moves
    it from the pattern extractor onto the TOC path. There the last item had no
    end anchor and ran into the signature block ("SIGNATURE ... Len M. Fox");
    it now stops at the bare SIGNATURE line, as the pattern path always did."""
    doc = HTMLParser(ParserConfig(form="10-Q")).parse(
        _XOM_10Q.read_text(encoding="utf-8", errors="replace"))
    item6 = doc.sections["part_ii_item_6"]

    assert item6.detection_method == "toc"
    text = item6.text()
    assert text.startswith("ITEM 6. EXHIBITS")
    assert text.rstrip().endswith("** Furnished herewith.")
    assert "Len M. Fox" not in text
