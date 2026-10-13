"""
Regression test for edgartools-llmp.12: Item 16 ran through the exhibit index printed after it.

Item 16, the Form 10-K Summary, is usually one line, but many filers print
Item 15's exhibit index (and schedules) after it, with no heading of its own,
so Item 16 held 10-44k characters of exhibits. The policy decided on
2026-10-13: Item 16 ends at its own text, and the index becomes a non-item
``exhibit_index`` section, so it is still in a section. When Item 15 is the
last item, the index is its own content and stays there.

Two neighbouring defects are pinned here as well. Southern's Item 16 heading
has no anchor, and the body-heading scan took the nearest preceding id, which
was an inline-XBRL fact in Item 15 ("PCAOB ID: 243"), cutting Item 15
mid-sentence. ExxonMobil's Item 16 kept the "FINANCIAL SECTION" divider page
that follows it.
"""
import pytest

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

HTML = FIXTURES_DIR / "html"


def _sections(path):
    html = path.read_text(errors="ignore")
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html).sections


def _text(section):
    return " ".join(section.text().split())


@pytest.mark.parametrize("ticker, fixture, item_16, index_opens", [
    ("ma", "ma-10-k-2025-02-12", "Item 16. Form 10-K summary None.", "EXHIBIT INDEX"),
    ("cvx", "cvx-10-k-2025-02-21", "Item 16. Form 10-K Summary Not applicable.", "EXHIBIT INDEX"),
    ("orcl", "orcl-10-k-2025-06-18", "Item 16. Form 10-K Summary None.", "ORACLE CORPORATION INDEX OF EXHIBITS"),
    ("es", "es-10-k-2024-02-14", "Item 16. Form 10-K Summary Not applicable.", "SCHEDULE I EVERSOURCE ENERGY"),
])
def test_item_16_ends_at_its_own_text_and_the_index_is_its_own_section(ticker, fixture, item_16, index_opens):
    sections = _sections(HTML / ticker / "10k" / f"{fixture}.html")
    assert _text(sections["part_iv_item_16"]) == item_16
    index = sections["exhibit_index"]
    assert _text(index).startswith(index_opens)
    assert index.item is None
    keys = list(sections)
    # It sits after Item 16 and before any Signatures section.
    assert keys.index("exhibit_index") == keys.index("part_iv_item_16") + 1


def test_915358_item_16_heading_anchored_inside_the_heading():
    # The anchor is an empty <span> inside the heading paragraph.
    sections = _sections(HTML / "915358" / "10k" / "915358-10-k-2025-08-27.html")
    assert _text(sections["part_iv_item_16"]).startswith("ITEM 16. FORM 10-K SUMMARY None.")
    assert len(sections["part_iv_item_16"].text()) < 40  # was 10,736
    assert _text(sections["exhibit_index"]).startswith("Index to Exhibits 2.1 Agreement and Plan of Merger")


def test_southern_item_16_does_not_start_on_an_xbrl_fact():
    sections = _sections(HTML / "so" / "10k" / "so-10-k-2026-02-19.html")
    item_15 = _text(sections["part_iv_item_15"])
    assert item_15.endswith("Exhibits for the Registrants are listed in the Exhibit Index at page E-1.")
    assert "PCAOB ID: 243)" in item_15  # was cut at "PCAOB ID:"
    assert _text(sections["part_iv_item_16"]) == "Item 16.FORM 10-K SUMMARY None."
    assert _text(sections["exhibit_index"]).startswith("SCHEDULE II")


def test_exxon_item_16_drops_the_financial_section_divider():
    sections = _sections(HTML / "xom" / "10k" / "xom-10-k-2025-02-19.html")
    assert _text(sections["part_iv_item_16"]) == "ITEM 16. FORM 10-K SUMMARY None."  # was "... None. 30 FINANCIAL SECTION"


def test_an_index_before_item_16_or_after_a_last_item_15_is_untouched():
    # Microsoft prints its index inside Item 15; Item 16 follows it.
    msft = _sections(HTML / "msft" / "10k" / "msft-10-k-2025-07-30.html")
    assert "exhibit_index" not in msft
    assert _text(msft["part_iv_item_16"]) == "ITEM 16. FORM 10-K SUMMARY None."
    # A 2010 10-K has no Item 16; the index after Item 15 is Item 15's own.
    older = _sections(FIXTURES_DIR / "parity_gate" / "10-K" / "0001193125-10-073212.html")
    assert "exhibit_index" not in older
    assert "EXHIBIT INDEX" in older["part_iv_item_15"].text().upper()
