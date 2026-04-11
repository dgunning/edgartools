"""
Agent-specific TOC parser tests.

Tests each agent-specific parser with representative HTML snippets
and verifies the generic fallback still works for unknown agents.
"""
import pytest
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


# --- Minimal HTML snippets per agent ---

WORKIVA_TOC_HTML = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
<tr>
 <td colspan="9"><div><a href="#uuid_10">Part I</a></div></td>
</tr>
<tr>
 <td><a href="#uuid_13">Item 1.</a></td>
 <td><a href="#uuid_13">Business</a></td>
 <td><a href="#uuid_13">1</a></td>
</tr>
<tr>
 <td><a href="#uuid_52">Item 1A.</a></td>
 <td><a href="#uuid_52">Risk Factors</a></td>
 <td><a href="#uuid_52">5</a></td>
</tr>
<tr>
 <td><a href="#uuid_70">Item 1B.</a></td>
 <td><a href="#uuid_70">Unresolved Staff Comments</a></td>
 <td><a href="#uuid_70">15</a></td>
</tr>
<tr>
 <td><a href="#uuid_94">Item 7.</a></td>
 <td><a href="#uuid_94">MD&amp;A</a></td>
 <td><a href="#uuid_94">20</a></td>
</tr>
<tr>
 <td><a href="#uuid_175">Item 8.</a></td>
 <td><a href="#uuid_175">Financial Statements</a></td>
 <td><a href="#uuid_175">30</a></td>
</tr>
</table>
<!-- targets -->
<div id="uuid_10">Part I</div>
<div id="uuid_13">Item 1. Business</div>
<div id="uuid_52">Item 1A. Risk Factors</div>
<div id="uuid_70">Item 1B. Unresolved Staff Comments</div>
<div id="uuid_94">Item 7. MD&A</div>
<div id="uuid_175">Item 8. Financial Statements</div>
</body></html>
"""

DFIN_TOC_HTML = """
<html><body>
<p>INDEX</p>
<table>
<tr>
 <td><a href="#item_1_business">Business</a></td>
 <td>3</td>
</tr>
<tr>
 <td><a href="#item_1a_risk_factors">Risk Factors</a></td>
 <td>10</td>
</tr>
<tr>
 <td><a href="#item_7_management">MD&amp;A</a></td>
 <td>25</td>
</tr>
<tr>
 <td><a href="#item_8_financial">Financial Statements</a></td>
 <td>40</td>
</tr>
<tr>
 <td><a href="#signatures">Signatures</a></td>
 <td>60</td>
</tr>
</table>
<!-- targets -->
<div id="item_1_business">Item 1. Business</div>
<div id="item_1a_risk_factors">Item 1A. Risk Factors</div>
<div id="item_7_management">Item 7. MD&A</div>
<div id="item_8_financial">Item 8. Financial Statements</div>
<div id="signatures">Signatures</div>
</body></html>
"""

NOVAWORKS_TOC_HTML = """
<html><body>
<p><b>INDEX</b></p>
<table>
<tr>
 <td><a href="#part1">PART I</a></td>
</tr>
<tr>
 <td><a href="#part1">ITEM 1. Business.</a></td>
 <td><a class="tocPGNUM" href="#part1">1</a></td>
</tr>
<tr>
 <td><a href="#item1a">ITEM 1A. Risk Factors</a></td>
 <td><a class="tocPGNUM" href="#item1a">9</a></td>
</tr>
<tr>
 <td><a href="#Item1C">ITEM 1C. Cybersecurity</a></td>
 <td><a class="tocPGNUM" href="#Item1C">26</a></td>
</tr>
<tr>
 <td><a href="#item7">ITEM 7. Management's Discussion and Analysis</a></td>
 <td><a class="tocPGNUM" href="#item7">29</a></td>
</tr>
<tr>
 <td><a href="#item8">ITEM 8. Financial Statements</a></td>
 <td><a class="tocPGNUM" href="#item8">35</a></td>
</tr>
</table>
<!-- targets -->
<div id="part1">Part I</div>
<div id="item1a">Item 1A. Risk Factors</div>
<div id="Item1C">Item 1C. Cybersecurity</div>
<div id="item7">Item 7</div>
<div id="item8">Item 8</div>
</body></html>
"""

TOPPAN_TOC_HTML = """
<html><body>
<p>INDEX</p>
<table>
<tr>
 <td><a href="#PARTI_117794"><b>PART&#160;I.</b></a></td>
 <td><span>&#8203;</span></td>
</tr>
<tr>
 <td><a href="#ITEM1BUSINESS_392371">ITEM&#160;1.</a></td>
 <td><a href="#ITEM1BUSINESS_392371">BUSINESS</a></td>
 <td>3</td>
</tr>
<tr>
 <td><a href="#ITEM1ARISKFACTORS_986989">ITEM&#160;1A.</a></td>
 <td><a href="#ITEM1ARISKFACTORS_986989">RISK FACTORS</a></td>
 <td>21</td>
</tr>
<tr>
 <td><a href="#ITEM7MGMT_123">ITEM&#160;7.</a></td>
 <td><a href="#ITEM7MGMT_123">MANAGEMENT\u2019S DISCUSSION</a></td>
 <td>30</td>
</tr>
<tr>
 <td><a href="#ITEM8FIN_456">ITEM&#160;8.</a></td>
 <td><a href="#ITEM8FIN_456">FINANCIAL STATEMENTS</a></td>
 <td>50</td>
</tr>
</table>
<!-- targets -->
<div id="PARTI_117794">PART I</div>
<div id="ITEM1BUSINESS_392371">Item 1. Business</div>
<div id="ITEM1ARISKFACTORS_986989">Item 1A. Risk Factors</div>
<div id="ITEM7MGMT_123">Item 7. Management</div>
<div id="ITEM8FIN_456">Item 8. Financial Statements</div>
</body></html>
"""


class TestWorkivaTOC:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_finds_all_items(self):
        result = self.analyzer._analyze_workiva_toc(WORKIVA_TOC_HTML)
        assert 'part_i_item_1' in result
        assert 'part_i_item_1a' in result
        assert 'part_i_item_1b' in result
        assert 'part_i_item_7' in result
        assert 'part_i_item_8' in result

    def test_uuid_anchors_mapped(self):
        result = self.analyzer._analyze_workiva_toc(WORKIVA_TOC_HTML)
        assert result['part_i_item_1'] == 'uuid_13'
        assert result['part_i_item_1a'] == 'uuid_52'

    def test_excludes_part_headers(self):
        """Part headers should not appear as standalone entries."""
        result = self.analyzer._analyze_workiva_toc(WORKIVA_TOC_HTML)
        assert 'Part I' not in result
        assert 'part_i' not in result

    def test_page_numbers_excluded(self):
        """Page number links (e.g., '1', '5') should not create entries."""
        result = self.analyzer._analyze_workiva_toc(WORKIVA_TOC_HTML)
        assert len(result) == 5  # Exactly 5 items, no page-number artifacts


class TestDFINTOC:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_finds_items_from_semantic_anchors(self):
        result = self.analyzer._analyze_dfin_toc(DFIN_TOC_HTML)
        # DFIN test HTML has no Part headers, so keys lack part prefix
        assert 'Item 1' in result
        assert 'Item 1A' in result
        assert 'Item 7' in result
        assert 'Item 8' in result

    def test_semantic_anchors_preserved(self):
        result = self.analyzer._analyze_dfin_toc(DFIN_TOC_HTML)
        assert result['Item 1'] == 'item_1_business'
        assert result['Item 1A'] == 'item_1a_risk_factors'

    def test_excludes_non_item_links(self):
        """Signatures and other non-item links should be excluded."""
        result = self.analyzer._analyze_dfin_toc(DFIN_TOC_HTML)
        assert 'signatures' not in result.values()
        assert not any('signature' in k.lower() for k in result)

    def test_dfin_links_fallback(self):
        """When no TOC table exists, falls back to scanning all links."""
        html = """<html><body>
        <a href="#item_1_business">Business</a>
        <a href="#item_7_management">MD&amp;A</a>
        <div id="item_1_business">Content</div>
        <div id="item_7_management">Content</div>
        </body></html>"""
        result = self.analyzer._analyze_dfin_toc(html)
        assert 'Item 1' in result
        assert 'Item 7' in result


class TestNovaworksTOC:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_finds_items_from_combined_text(self):
        result = self.analyzer._analyze_novaworks_toc(NOVAWORKS_TOC_HTML)
        assert 'part_i_item_1' in result
        assert 'part_i_item_1a' in result
        assert 'part_i_item_1c' in result
        assert 'part_i_item_7' in result
        assert 'part_i_item_8' in result

    def test_handles_shared_part_anchor(self):
        """Item 1 correctly maps even when it shares anchor with Part I."""
        result = self.analyzer._analyze_novaworks_toc(NOVAWORKS_TOC_HTML)
        assert result['part_i_item_1'] == 'part1'

    def test_handles_inconsistent_anchor_case(self):
        """#item1a and #Item1C both work (case-insensitive targets)."""
        result = self.analyzer._analyze_novaworks_toc(NOVAWORKS_TOC_HTML)
        assert result['part_i_item_1a'] == 'item1a'
        assert result['part_i_item_1c'] == 'Item1C'

    def test_excludes_part_headers(self):
        """Part headers should not appear as standalone entries."""
        result = self.analyzer._analyze_novaworks_toc(NOVAWORKS_TOC_HTML)
        assert 'Part I' not in result
        assert 'part_i' not in result


class TestToppanTOC:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_finds_items_from_split_links(self):
        result = self.analyzer._analyze_toppan_toc(TOPPAN_TOC_HTML)
        assert 'part_i_item_1' in result
        assert 'part_i_item_1a' in result
        assert 'part_i_item_7' in result
        assert 'part_i_item_8' in result

    def test_descriptive_anchors_mapped(self):
        result = self.analyzer._analyze_toppan_toc(TOPPAN_TOC_HTML)
        assert result['part_i_item_1'] == 'ITEM1BUSINESS_392371'
        assert result['part_i_item_1a'] == 'ITEM1ARISKFACTORS_986989'

    def test_zero_width_spaces_stripped(self):
        """Zero-width spaces in text should not affect parsing."""
        result = self.analyzer._analyze_toppan_toc(TOPPAN_TOC_HTML)
        # If ZWS were not stripped, "ITEM\u200b1." might not parse correctly
        assert len(result) == 4

    def test_excludes_part_headers(self):
        """Part headers should not appear as standalone entries."""
        result = self.analyzer._analyze_toppan_toc(TOPPAN_TOC_HTML)
        assert 'Part I' not in result
        assert 'part_i' not in result


class TestTOCDispatch:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_workiva_dispatch(self):
        result = self.analyzer.analyze_toc_structure(WORKIVA_TOC_HTML, agent='Workiva')
        assert 'part_i_item_1' in result
        assert result['part_i_item_1'] == 'uuid_13'

    def test_donnelley_dispatch(self):
        result = self.analyzer.analyze_toc_structure(DFIN_TOC_HTML, agent='Donnelley')
        assert 'Item 1' in result
        assert result['Item 1'] == 'item_1_business'

    def test_novaworks_dispatch(self):
        result = self.analyzer.analyze_toc_structure(NOVAWORKS_TOC_HTML, agent='Novaworks')
        assert 'part_i_item_1' in result

    def test_toppan_dispatch(self):
        result = self.analyzer.analyze_toc_structure(TOPPAN_TOC_HTML, agent='Toppan Merrill')
        assert 'part_i_item_1' in result

    def test_unknown_agent_uses_generic(self):
        """Unknown agent name falls back to generic parser."""
        result = self.analyzer.analyze_toc_structure(WORKIVA_TOC_HTML, agent='UnknownAgent')
        # Generic parser should still find sections via the existing heuristics
        assert len(result) > 0

    def test_none_agent_uses_generic(self):
        """None agent falls back to generic parser."""
        result = self.analyzer.analyze_toc_structure(WORKIVA_TOC_HTML, agent=None)
        assert len(result) > 0


class TestHelperMethods:
    def setup_method(self):
        self.analyzer = TOCAnalyzer()

    def test_parse_item_from_text(self):
        assert self.analyzer._parse_item_from_text('Item 1.') == 'Item 1'
        assert self.analyzer._parse_item_from_text('ITEM 1A.') == 'Item 1A'
        assert self.analyzer._parse_item_from_text('Item 7A. Quantitative') == 'Item 7A'
        assert self.analyzer._parse_item_from_text('Part II') == 'Part II'
        assert self.analyzer._parse_item_from_text('Business') is None

    def test_item_from_anchor(self):
        # DFIN style (underscore-separated)
        assert self.analyzer._item_from_anchor('item_1_business') == 'Item 1'
        assert self.analyzer._item_from_anchor('item_1a_risk_factors') == 'Item 1A'
        # Novaworks style (short anchors)
        assert self.analyzer._item_from_anchor('item7a') == 'Item 7A'
        assert self.analyzer._item_from_anchor('item1a') == 'Item 1A'
        # Toppan style — no clear boundary, returns None (parser uses text extraction)
        assert self.analyzer._item_from_anchor('ITEM1BUSINESS_392371') is None
        # Parts and non-items
        assert self.analyzer._item_from_anchor('part_ii') == 'Part II'
        assert self.analyzer._item_from_anchor('signatures') is None

    def test_parse_item_strips_zwsp(self):
        """Zero-width spaces should be transparent to parsing."""
        assert self.analyzer._parse_item_from_text('Item\u200b 1A.') == 'Item 1A'
