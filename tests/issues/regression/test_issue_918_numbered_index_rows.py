"""Regression tests for GitHub Issue #918 (second defect): item sections
fabricated from numbered table/figure index rows.

Freddie Mac's FY2025 10-K (accession 0001026214-26-000021) mapped every
``part_*_item_N`` onto an MD&A table caption at full confidence —
``obj['Item 11']`` returned 30,514 chars starting at "Table 11 - Other
Investments Portfolio". FMCC's MD&A "List of Tables" index rows
('11' | 'Other Investments Portfolio' | '18') feed the generic TOC scan,
and ``_extract_preceding_item_label`` read the bare row-number cell as
"Item 11" (the page-number range cap doesn't help: 11 is a valid 10-K item
number).

Fixed by context, not per-row validation: a numbered index is recognisable
by its header row, which names the numbering ("Table | Description | Page"),
while a genuine TOC heads its number column "Item" (Morgan Stanley:
"Table of Contents | Part | Item | Page") or has no header at all. Bare
numbers in a table whose header names the numbering as tables/figures/…
are not item numbers. An earlier attempt that corroborated each bare-number
row against its link target silently dropped real items on filers whose
TOC anchors land nowhere near the item headings (MS 10-K: 19 item sections
→ 6) — see PR #919's review.

Unit tests are synthetic (no network); end-to-end assertions are VCR-backed
and pinned to the reported filing. The FMCC 10-Q half of the fix (the GH
#905 phantoms, removed at the source by the same guard) is pinned in
tests/issues/regression/test_issue_905_phantom_part_items.py.

GitHub Issue: https://github.com/dgunning/edgartools/issues/918
"""

import lxml.html
import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer
from tests._offline_filings import offline_filing

pytestmark = pytest.mark.regression

# FMCC-shaped MD&A "List of Tables": the header row names the numbering
# ("Table"), so the bare-number cells are table captions, not item numbers.
# Rows link to the captions exactly like real TOC rows link to headings.
LIST_OF_TABLES_HTML = """
<html><body>
<table>
<tr><td>Table</td><td>Description</td><td>Page</td></tr>
<tr><td>1</td><td><a href="#c1">Summary of Consolidated Statements of Income</a></td><td><a href="#c1">10</a></td></tr>
<tr><td>11</td><td><a href="#c11">Other Investments Portfolio</a></td><td><a href="#c11">18</a></td></tr>
<tr><td>12</td><td><a href="#c12">Single-Family Housing and Mortgage Market</a></td><td><a href="#c12">21</a></td></tr>
<tr><td>13</td><td><a href="#c13">Single-Family Segment Results</a></td><td><a href="#c13">25</a></td></tr>
<tr><td>14</td><td><a href="#c14">Multifamily Segment Results</a></td><td><a href="#c14">30</a></td></tr>
</table>
<div id="c1"></div>
<div>Table 1 - Summary of Consolidated Statements of Income</div>
<div id="c11"></div>
<div>Table 11 - Other Investments Portfolio</div>
<div id="c12"></div>
<div>Table 12 - Single-Family Housing and Mortgage Market</div>
<div id="c13"></div>
<div>Table 13 - Single-Family Segment Results</div>
<div id="c14"></div>
<div>Table 14 - Multifamily Segment Results</div>
</body></html>
"""

# MS-shaped TOC: bare numbers sit in a column explicitly headed "Item"
# (and the leading header cell contains "Table" only as part of "Table of
# Contents", which must NOT trigger the index guard). These labels are the
# ones an earlier per-row-corroboration guard silently dropped — the anchor
# targets here are empty divs far from any heading text, like MS's.
ITEM_COLUMN_TOC_HTML = """
<html><body>
<table>
<tr><td>Table of Contents</td><td>Part</td><td>Item</td><td>Page</td></tr>
<tr><td><a href="#s1">Business</a></td><td>I</td><td>1</td><td><a href="#s1">5</a></td></tr>
<tr><td><a href="#s2">Risk Factors</a></td><td></td><td>1A</td><td><a href="#s2">13</a></td></tr>
<tr><td><a href="#s3">Cybersecurity</a></td><td></td><td>1C</td><td><a href="#s3">25</a></td></tr>
<tr><td><a href="#s4">Executive Compensation</a></td><td>III</td><td>11</td><td><a href="#s4">88</a></td></tr>
</table>
<div id="s1"></div>
<p>Prose that does not repeat the heading.</p>
<div id="s2"></div>
<p>More prose.</p>
<div id="s3"></div>
<p>More prose.</p>
<div id="s4"></div>
<p>More prose.</p>
</body></html>
"""

# Headerless bare-number TOC: no header row at all — legacy behaviour,
# bare numbers within the form's item range are trusted.
HEADERLESS_TOC_HTML = """
<html><body>
<table>
<tr><td>8</td><td><a href="#f8">Financial Statements and Supplementary Data</a></td><td><a href="#f8">40</a></td></tr>
</table>
<div id="f8"></div>
<div>ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA</div>
</body></html>
"""


@pytest.mark.fast
class TestNumberedIndexRows:
    """Bare numbers under a Table/Figure header are captions, not items."""

    def test_list_of_tables_produces_no_items(self):
        mapping = TOCAnalyzer(form="10-K")._analyze_generic_toc(LIST_OF_TABLES_HTML)
        assert not any("item" in key for key in mapping), mapping

    def test_item_headed_column_still_produces_items(self):
        """The MS shape: an explicit Item column, unreachable heading text.

        Per-row target corroboration rejected all of these (PR #919 review:
        MS 10-K dropped from 19 item sections to 6); the header-context
        guard must keep them.
        """
        mapping = TOCAnalyzer(form="10-K")._analyze_generic_toc(ITEM_COLUMN_TOC_HTML)
        assert mapping.get("part_i_item_1") == "s1"
        assert mapping.get("part_i_item_1a") == "s2"
        assert mapping.get("part_i_item_1c") == "s3"
        assert mapping.get("part_iii_item_11") == "s4"

    def test_headerless_bare_number_toc_is_unchanged(self):
        mapping = TOCAnalyzer(form="10-K")._analyze_generic_toc(HEADERLESS_TOC_HTML)
        assert mapping.get("part_ii_item_8") == "f8"

    def test_figure_index_is_also_suppressed(self):
        html = LIST_OF_TABLES_HTML.replace(
            "<td>Table</td>", "<td>Figures:</td>")
        mapping = TOCAnalyzer(form="10-K")._analyze_generic_toc(html)
        assert not any("item" in key for key in mapping), mapping

    def test_mixed_header_with_item_column_is_a_toc(self):
        """"Item" in the same header row outranks the index vocabulary."""
        analyzer = TOCAnalyzer(form="10-K")
        tree = lxml.html.fromstring(
            "<table><tr><td>Table</td><td>Item</td><td>Page</td></tr>"
            "<tr><td>x</td><td id='n'>1</td><td>5</td></tr></table>")
        cell = tree.xpath("//td[@id='n']")[0]
        assert analyzer._cell_in_numbered_index(cell) is False


@pytest.mark.fast
@pytest.mark.vcr
def test_fmcc_10k_items_are_not_table_captions():
    """End-to-end on the reported filing: Freddie Mac FY2025 10-K.

    Before the fix the generic TOC scan built part_i_item_1 … part_iv_item_15
    entirely out of "Table N" captions from the MD&A's List of Tables;
    ``obj['Item 11']`` returned 30,514 chars starting at "Table 11 - Other
    Investments Portfolio". Now no item section exists at all — FMCC's TOC
    carries no genuine item rows — and the named sections resolved from the
    keyword vocabulary don't open on table captions either.
    """
    obj = offline_filing("0001026214-26-000021").obj()

    # .get() — an absent Item 11 is the expected answer here, and the
    # subscript raises on a miss from 6.0 (bead edgartools-07lk.10).
    content = obj.get('Item 11', "")
    assert "Table 11" not in content[:100]

    sections = obj.document.sections
    assert not any("item" in name for name in sections), sorted(sections)
    for name, section in sections.items():
        head = (section.text() or "").strip()[:60]
        assert not head.startswith("Table 1"), (name, head)
