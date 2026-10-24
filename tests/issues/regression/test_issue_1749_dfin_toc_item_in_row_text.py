"""Regression: Donnelley contents rows whose item number is only in the row text.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1749

Tesla's 10-Q 0000950170-23-033872 (quarter ended 2023-06-30) has contents rows shaped
``<td>Item 1.</td><td><a href="#financial_statements">Financial Statements</a></td><td>4</td>``.
Neither the anchor nor the link text carries the item number, so ``_analyze_dfin_toc`` skipped
every Part I row and ``tenq['Part I, Item 1']`` returned the 4,395-character contents page.
"""
import pytest
from lxml import html as lxml_html

from edgar.documents.utils.toc_analyzer import TOCAnalyzer

HTML = """<html><body>
<table><tr><td>INDEX</td></tr></table>
<table>
<tr><td>PART I. FINANCIAL INFORMATION</td></tr>
<tr><td>Item 1.</td><td><a href="#financial_statements">Financial Statements</a></td><td>4</td></tr>
<tr><td>Item 3.</td><td><a href="#market_risk">Quantitative and Qualitative Disclosures About Market Risk</a></td><td>30</td></tr>
</table>
<p id="financial_statements">ITEM 1. FINANCIAL STATEMENTS</p><p>body</p>
<p id="market_risk">ITEM 3. QUANTITATIVE</p><p>body</p>
</body></html>"""


def test_item_read_from_row_text_when_anchor_and_link_text_lack_it():
    analyzer = TOCAnalyzer(form='10-Q')
    tree = lxml_html.fromstring(HTML)
    mapping = analyzer._analyze_dfin_toc(HTML, tree)
    assert mapping.get("part_i_item_1") == "financial_statements"
    assert mapping.get("part_i_item_3") == "market_risk"


@pytest.mark.network
@pytest.mark.vcr
def test_tesla_10q_2023q2_part_i_items():
    from edgar import find
    tenq = find("0000950170-23-033872").obj()
    item1 = tenq["Part I, Item 1"]
    assert len(item1) == 65181
    assert item1.startswith("ITEM 1.")
    assert len(tenq["Part I, Item 3"]) == 1682
    assert len(tenq["Part I, Item 4"]) == 1884
    assert len(tenq["Part I, Item 2"]) == 34592


def test_thin_row_text_result_does_not_suppress_generic_scan():
    """JPM's contents page yields one row via row text; the generic scan's 11 items must survive."""
    from pathlib import Path
    html = Path("tests/fixtures/html/jpm/10q/jpm-10-q-2025-08-05.html").read_text(encoding="utf-8")
    generic = TOCAnalyzer(form="10-Q").analyze_toc_structure(html, agent=None)
    via_dfin = TOCAnalyzer(form="10-Q").analyze_toc_structure(html, agent="Donnelley")
    assert len(generic) == 11
    assert via_dfin == generic
