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

    def test_item_from_anchor_part_word_boundary(self):
        """Regression (edgartools-dkq0): 'part' must be a real word boundary,
        not a mid-word substring, or anchors like 'counterparties' pollute the
        part context of every item parsed afterward."""
        # Mid-word 'part' must NOT match
        assert self.analyzer._item_from_anchor('counterparties') is None
        assert self.analyzer._item_from_anchor('counterparty-risk') is None
        assert self.analyzer._item_from_anchor('departments') is None
        # Real part anchors still resolve, with any valid left delimiter
        assert self.analyzer._item_from_anchor('part_i') == 'Part I'
        assert self.analyzer._item_from_anchor('part_ii_item_1') == 'Item 1'
        assert self.analyzer._item_from_anchor('#PARTI_658977') == 'Part I'

    def test_build_section_mapping_skips_part_as_section(self):
        """Regression (edgartools-sldz): a Part label is navigation context, not a
        content section. Bare 'Part X' entries (common in the Item 15 exhibit index,
        which cross-references 'Part I, Item 1A \u2026') must not emit malformed keys
        like 'part_iv_part_i', 'part_i_part_ii', or a bare 'Part I'."""
        from edgar.documents.utils.toc_analyzer import TOCSection
        sections = [
            TOCSection(name='Item 1', anchor_id='a1', normalized_name='Item 1',
                       section_type='item', order=1, part='Part I'),
            # Part-as-section leaks \u2014 must be dropped
            TOCSection(name='Part I', anchor_id='ap1', normalized_name='Part I',
                       section_type='part', order=2, part='Part IV'),
            TOCSection(name='Part II', anchor_id='ap2', normalized_name='Part II',
                       section_type='part', order=3, part='Part I'),
            TOCSection(name='Item 15', anchor_id='a15', normalized_name='Item 15',
                       section_type='item', order=4, part='Part IV'),
        ]
        mapping = self.analyzer._build_section_mapping(sections)
        assert mapping == {'part_i_item_1': 'a1', 'part_iv_item_15': 'a15'}
        # No key contains a Part-as-section artifact
        for key in mapping:
            assert 'part_iv_part_i' not in key
            assert 'part_i_part_ii' not in key
            assert key != 'Part I'

    def test_parse_item_strips_zwsp(self):
        """Zero-width spaces should be transparent to parsing."""
        assert self.analyzer._parse_item_from_text('Item\u200b 1A.') == 'Item 1A'


# A link-less TOC (page numbers, no anchors) plus bold body headings, each
# preceded by an empty anchor div \u2014 the Goldman Sachs / Citi 10-K shape.
LINKLESS_TOC_BODY_HTML = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
 <tr><td><span style="font-weight:700">PART I</span></td><td>1</td></tr>
 <tr><td><span style="font-weight:700">Item 1</span></td></tr>
 <tr><td><span>Business</span></td><td>1</td></tr>
 <tr><td><span style="font-weight:700">Item 1A</span></td></tr>
 <tr><td><span>Risk Factors</span></td><td>5</td></tr>
</table>
<div style="font-weight:700">PART I</div>
<div id="anc_19"></div>
<div><span style="font-size:14pt;font-weight:700">Item 1.  Business</span></div>
<div><span>The company operates globally. </span></div>
<div id="anc_52"></div>
<div><span style="font-size:14pt;font-weight:700">Item 1A.  Risk Factors</span></div>
<div><span>We face many risks. </span></div>
<div style="font-weight:700">PART II</div>
<div id="anc_82"></div>
<div><span style="font-size:14pt;font-weight:700">Item 7. Management's Discussion and Analysis</span></div>
<div><span>Results were strong. </span></div>
<div id="anc_90"></div>
<div><span style="font-size:14pt;font-weight:700">Item 8. Financial Statements and Supplementary Data</span></div>
<div><span>See the statements. </span></div>
</body></html>
"""


class TestBodyItemHeaders:
    """Body-header fallback for link-less-TOC filings (edgartools-sldz)."""

    def setup_method(self):
        self.analyzer = TOCAnalyzer(form='10-K')

    def test_body_header_scan_maps_items_to_preceding_anchor(self):
        result = self.analyzer._analyze_body_item_headers(LINKLESS_TOC_BODY_HTML)
        # Each item resolves to the empty anchor div immediately before its heading,
        # with part context tracked from the body's PART dividers.
        assert result == {
            'part_i_item_1': 'anc_19',
            'part_i_item_1a': 'anc_52',
            'part_ii_item_7': 'anc_82',
            'part_ii_item_8': 'anc_90',
        }

    def test_inline_cross_reference_is_not_a_header(self):
        """Prose like 'see Part II, Item 7 \u2026' must not register as a section."""
        html = """
        <html><body>
        <div style="font-weight:700">PART I</div>
        <div id="a1"></div>
        <div><span style="font-size:14pt;font-weight:700">Item 1.  Business</span></div>
        <div><span>For details see Part II, Item 7 of this Form 10-K.</span></div>
        </body></html>
        """
        result = self.analyzer._analyze_body_item_headers(html)
        assert result == {'part_i_item_1': 'a1'}

    def test_bare_toc_item_cells_are_not_headers(self):
        """A bare 'Item 1' TOC cell (no title after the number) is not a heading."""
        html = """
        <html><body>
        <table><tr><td><span style="font-weight:700">Item 1</span></td><td>1</td></tr></table>
        </body></html>
        """
        assert self.analyzer._analyze_body_item_headers(html) == {}

    def test_fallback_only_when_linked_toc_underperforms(self):
        """Floor gating: a 10-K whose linked TOC already yields many canonical
        items must not be overridden by the body-header scan."""
        assert self.analyzer._canonical_item_count(
            {f'part_i_item_{i}': f'a{i}' for i in range(1, 16)}
        ) == 15
        assert self.analyzer._expected_item_floor() == 8
        # Non-10-K forms never trigger the fallback.
        assert TOCAnalyzer(form='20-F')._expected_item_floor() == 0


@pytest.mark.slow
class TestGoldmanSachsSections:
    """Integration: GS 10-K item structure lives only in a link-less TOC; the
    body-header fallback recovers all items with correct content (edgartools-sldz)."""

    GS_FIXTURE = "gs/10k/gs-10-k-2025-02-27.html"

    def _sections(self):
        from pathlib import Path
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        root = Path(__file__).parent / "fixtures" / "html"
        path = root / self.GS_FIXTURE
        if not path.exists():
            pytest.skip(f"GS fixture not available: {path}")
        return parse_html(path.read_text(), ParserConfig(form="10-K")).sections

    def test_gs_recovers_canonical_items(self):
        secs = self._sections()
        # Every item is canonically keyed under its correct part; none of the old
        # garbage (bare 'Part I', 'part_i_part_ii', descriptive risk-mgmt keys).
        for key in ['part_i_item_1', 'part_i_item_1a', 'part_ii_item_7',
                    'part_ii_item_8', 'part_iv_item_15']:
            assert key in secs, f"missing {key}; got {sorted(secs.keys())}"
        assert all('risk_management' not in k for k in secs)
        assert 'Part I' not in secs and 'part_i_part_ii' not in secs

    def test_gs_item_content_is_correct(self):
        secs = self._sections()
        assert secs['part_i_item_1'].text().lstrip().lower().startswith('item 1')
        assert 'goldman sachs' in secs['part_i_item_1'].text().lower()[:300]
        assert 'risk factors' in secs['part_i_item_1a'].text().lower()[:120]
        assert 'financial statements' in secs['part_ii_item_8'].text().lower()[:120]
