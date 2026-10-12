"""
Regression test for edgartools-llmp.12.2: a partial TOC on a cross-reference
index filer sent the missing items to keyword matching.

GE's 10-K publishes a "FORM 10-K CROSS REFERENCE INDEX" and prints its items
out of order. The TOC detector read part of that index and succeeded with five
items, so the index path (which only ran when the TOC failed) never did, and
the augmenter filled the gaps from the pattern extractor: Item 1 was the index
table itself, Item 1C was 68k characters running into the ICFR report, and
Item 9A was 276k characters starting mid-sentence and running to the end.

``HybridSectionDetector._augment_with_pattern_sections`` now fills missing
items from the filer's index first; the pattern pass only sees what is left.
"""

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

GE = FIXTURES_DIR / "html" / "ge" / "10k" / "ge-10-k-2026-01-29.html"
BAC = FIXTURES_DIR / "html" / "bac" / "10k"


def _parse(path):
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(path.read_text(errors="ignore"))


def test_index_supplies_the_items_a_partial_toc_missed():
    doc = _parse(GE)
    methods = {name: section.detection_method for name, section in doc.sections.items()}
    assert "pattern" not in methods.values(), methods
    # The TOC keeps every item it named; the index adds the rest it locates.
    assert sorted(n for n, m in methods.items() if m == "toc") == [
        "part_i_item_1a", "part_i_item_3", "part_ii_item_7", "part_ii_item_8", "part_iv_item_15"]
    assert sorted(n for n, m in methods.items() if m == "index") == [
        "part_i_item_1", "part_i_item_1c", "part_i_item_2", "part_ii_item_5",
        "part_ii_item_7a", "part_ii_item_9a", "part_iii_item_10"]


def test_item_9a_is_page_32_not_the_back_half_of_the_filing():
    item_9a = _parse(GE).sections["part_ii_item_9a"].text()
    assert len(item_9a) == 3304  # was 276,430 from the pattern pass
    assert item_9a.startswith("MANAGEMENT AND AUDITOR’S REPORTS")
    assert "REPORT OF INDEPENDENT REGISTERED PUBLIC ACCOUNTING FIRM" not in item_9a


def test_item_1c_and_item_1_are_their_own_pages_not_the_index_table():
    doc = _parse(GE)
    item_1c = doc.sections["part_i_item_1c"].text()
    assert len(item_1c) == 6650  # was 68,536
    assert item_1c.startswith("CYBERSECURITY\n\nCYBERSECURITY RISK MANAGEMENT AND STRATEGY.")
    assert "RISK FACTORS" not in item_1c
    item_1 = doc.sections["part_i_item_1"].text()
    assert item_1.startswith("ABOUT GE AEROSPACE.")
    assert "CROSS REFERENCE INDEX" not in item_1


def test_a_filing_without_an_index_still_gets_pattern_sections():
    # bac's TOC omits Item 1C; with no index to consult, the pattern pass still supplies it.
    doc = _parse(next(BAC.glob("*.htm*")))
    item_1c = [s for s in doc.sections.values() if s.item == "1C"]
    assert [s.detection_method for s in item_1c] == ["pattern"]
