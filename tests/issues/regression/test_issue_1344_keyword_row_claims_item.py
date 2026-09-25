"""Regression: a TOC row that only keyword-matches an item no longer claims it.

GH #1344. When a TOC row carries only a title, ``TOCAnalyzer`` resolves it to an
item through the form's keyword vocabulary (``FormSchema.match_text``, the GH
#837 fallback). Two sub-heading title families matched an item's keywords
without being that item:

* "... Summary of Risk Factors" / "Risk Factors Summary" -> Item 1A
* "Index to (Combined Notes to) Financial Statements"    -> Item 8

HERTZ GLOBAL HOLDINGS 10-K (0001657853-25-000015, Workiva path): the row
"CAUTIONARY NOTE REGARDING FORWARD-LOOKING STATEMENTS AND SUMMARY OF RISK
FACTORS" precedes the real "ITEM 1A." rows, and the Workiva row loop keeps the
first claim on a key. Item 1A returned the 8,524-char summary and Item 1 ran on
through the whole of Risk Factors (159,382 chars).

PPL CORP 10-K (0000922224-24-000008, generic path): the only TOC row mapping to
Item 8 was "Index to Combined Notes to Consolidated Financial Statements" — the
real Item 8 row has no link — so Item 8 opened at the notes index and Item 7A
(58,912 chars) ran past the ITEM 8 heading through the primary statements.

The fix: the Item 1A keyword rule excludes "summary" and the Item 8 rule
excludes "index" (10-K; the 10-Q Item 1A rule likewise). Both rows now resolve
to no item, and the key goes to the real row (Hertz) or is recovered from the
body (PPL).

Offline (local fixtures).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1344
"""
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.form_schema import TEN_K_SCHEMA, TEN_Q_SCHEMA
from edgar.documents.parser import HTMLParser
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

_HTML = Path(__file__).resolve().parents[2] / "fixtures" / "html"
_HERTZ = _HTML / "htz" / "10k" / "htz-10-k-2025-02-18.html"
_PPL = _HTML / "ppl" / "10k" / "ppl-10-k-2024-02-16.html"


def _parse(path):
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(path.read_text(encoding="utf-8"))
    return doc.sections


@pytest.fixture(scope="module")
def hertz_sections():
    """Parse the Hertz 10-K once for the module (module scope releases it after)."""
    return _parse(_HERTZ)


@pytest.fixture(scope="module")
def ppl_sections():
    """Parse the PPL 10-K once for the module (module scope releases it after)."""
    return _parse(_PPL)


# --- keyword vocabulary -----------------------------------------------------

@pytest.mark.parametrize("text", [
    "risk factors summary",
    "summary of risk factors",
    "cautionary note regarding forward-looking statements and summary of risk factors",
])
def test_risk_factor_summary_rows_match_no_item(text):
    assert TEN_K_SCHEMA.match_text(text) is None
    assert TEN_Q_SCHEMA.match_text(text) is None


@pytest.mark.parametrize("text", [
    "index to financial statements",
    "index to consolidated financial statements",
    "index to combined notes to consolidated financial statements",
])
def test_financial_statement_index_rows_match_no_item(text):
    assert TEN_K_SCHEMA.match_text(text) is None


@pytest.mark.parametrize("text,item", [
    ("risk factors", "Item 1A"),
    ("financial statements and supplementary data", "Item 8"),
    ("financial statements", "Item 8"),
])
def test_real_item_titles_still_match(text, item):
    assert TEN_K_SCHEMA.match_text(text) == item


def test_parse_item_from_text_drops_sub_heading_rows():
    analyzer = TOCAnalyzer(form="10-K")
    assert analyzer._parse_item_from_text("Risk Factors Summary") is None
    assert analyzer._parse_item_from_text("Summary of Risk Factors") is None
    assert analyzer._parse_item_from_text("Index to Financial Statements") is None
    # The GH #837 title-only rows keep resolving, and explicit labels still win.
    assert analyzer._parse_item_from_text("Risk Factors") == "Item 1A"
    assert analyzer._parse_item_from_text("Business") == "Item 1"
    assert analyzer._parse_item_from_text(
        "Financial Statements and Supplementary Data") == "Item 8"
    assert analyzer._parse_item_from_text("Item 1A. Risk Factors Summary") == "Item 1A"


def test_10q_parse_item_from_text_drops_summary_row():
    analyzer = TOCAnalyzer(form="10-Q")
    assert analyzer._parse_item_from_text("Summary of Risk Factors") is None
    assert analyzer._parse_item_from_text("Risk Factors") == "Item 1A"


# --- Hertz (Workiva path) ---------------------------------------------------

def test_hertz_item_1a_is_the_real_risk_factors(hertz_sections):
    item1a = hertz_sections["part_i_item_1a"].text()
    # Before: 8,524 chars of the cautionary note's risk-factor summary.
    assert len(item1a) == 100_175
    assert "ITEM\xa01A. RISK FACTORS" in item1a[:200]
    assert "CAUTIONARY NOTE" not in item1a[:200]


def test_hertz_item_1_stops_at_item_1a(hertz_sections):
    item1 = hertz_sections["part_i_item_1"].text()
    # Before: 159,382 chars with "ITEM 1A. RISK FACTORS" at offset 59,307.
    assert len(item1) == 59_214
    assert item1.startswith("ITEM\xa01. BUSINESS")
    assert "ITEM\xa01A. RISK FACTORS" not in item1


# --- PPL (generic path) -----------------------------------------------------

def test_ppl_item_7a_stops_at_item_8(ppl_sections):
    item7a = ppl_sections["part_ii_item_7a"].text()
    # Before: 58,912 chars, running through the ITEM 8 heading at offset 27,490.
    assert len(item7a) == 27_483
    assert item7a.startswith("ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK")
    assert "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA" not in item7a


def test_ppl_item_8_opens_on_its_heading(ppl_sections):
    item8 = ppl_sections["part_ii_item_8"].text()
    # Before: 297,733 chars opening on "COMBINED NOTES TO FINANCIAL STATEMENTS".
    assert len(item8) == 329_162
    assert "ITEM 8.\xa0\xa0FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA" in item8[:100]
    assert "CONSOLIDATED STATEMENTS OF INCOME" in item8[:200]
