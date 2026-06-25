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
        # DFIN test HTML has no explicit Part headers, but the 10-K schema infers
        # the canonical part from the item number (edgartools-3usf).
        assert 'part_i_item_1' in result
        assert 'part_i_item_1a' in result
        assert 'part_ii_item_7' in result
        assert 'part_ii_item_8' in result

    def test_semantic_anchors_preserved(self):
        result = self.analyzer._analyze_dfin_toc(DFIN_TOC_HTML)
        assert result['part_i_item_1'] == 'item_1_business'
        assert result['part_i_item_1a'] == 'item_1a_risk_factors'

    def test_includes_signatures_named_section(self):
        """Signatures is an allowlisted named section the agent path now keeps.

        Previously the agent parsers dropped it (it carries no Item/Part number),
        so the agent path lost a section the generic parser found (edgartools-rbsx).
        The DFIN snippet has no Part headers, so the key is the bare 'signatures'.
        """
        result = self.analyzer._analyze_dfin_toc(DFIN_TOC_HTML)
        assert 'signatures' in result
        assert result['signatures'] == 'signatures'

    def test_dfin_links_fallback(self):
        """When no TOC table exists, falls back to scanning all links."""
        html = """<html><body>
        <a href="#item_1_business">Business</a>
        <a href="#item_7_management">MD&amp;A</a>
        <div id="item_1_business">Content</div>
        <div id="item_7_management">Content</div>
        </body></html>"""
        result = self.analyzer._analyze_dfin_toc(html)
        assert 'part_i_item_1' in result
        assert 'part_ii_item_7' in result


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
        assert 'part_i_item_1' in result
        assert result['part_i_item_1'] == 'item_1_business'

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
        # Keyword fallback: a title-only row (the "Item N" label split into a
        # different cell) resolves via the schema vocabulary, matching the
        # generic parser, so agent parsers don't drop Item 1 (GH #837).
        assert self.analyzer._parse_item_from_text('Business') == 'Item 1'
        assert self.analyzer._parse_item_from_text('Risk Factors') == 'Item 1A'
        # Explicit "Item N" still wins over the keyword in the same string.
        assert self.analyzer._parse_item_from_text('Item 1A. Risk Factors') == 'Item 1A'
        # Genuinely unmatchable text still returns None.
        assert self.analyzer._parse_item_from_text('21') is None

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

    def test_build_section_mapping_drops_descriptive_noise(self):
        """Regression (edgartools-3au1): the 10-K raw-text fallback leaks
        descriptive titles and exhibit-index prose as top-level sections. Only
        canonical items, bare 'Item N', and allowlisted named sections survive."""
        from edgar.documents.utils.toc_analyzer import TOCSection
        sections = [
            TOCSection(name='Item 1', anchor_id='a1', normalized_name='Item 1',
                       section_type='item', order=1, part='Part I'),
            # Pure descriptive MD&A subsection \u2014 must drop
            TOCSection(name='Risk Management', anchor_id='arm',
                       normalized_name='Risk Management', section_type='other',
                       order=2, part='Part II'),
            # Exhibit-index prose that merely contains an item number \u2014 must drop
            TOCSection(name=', Item 1A', anchor_id='ax',
                       normalized_name=', Item 1A', section_type='item',
                       order=3, part='Part IV'),
            # Allowlisted named section \u2014 must keep
            TOCSection(name='Signatures', anchor_id='asig',
                       normalized_name='Signatures', section_type='other',
                       order=4, part='Part IV'),
            # Item with no detected part \u2014 the 10-K schema infers Part II from the
            # item number, yielding a canonical key (edgartools-3usf).
            TOCSection(name='Item 8', anchor_id='a8', normalized_name='Item 8',
                       section_type='item', order=5, part=None),
        ]
        mapping = self.analyzer._build_section_mapping(sections)
        assert mapping == {
            'part_i_item_1': 'a1',
            'part_iv_signatures': 'asig',
            'part_ii_item_8': 'a8',
        }

    def test_is_valid_section_key(self):
        ok = self.analyzer._is_valid_section_key
        assert ok('part_ii_item_7', 'Item 7')
        assert ok('item_1a', 'Item 1A')
        assert ok('Item 8', 'Item 8')                       # bare, missing prefix
        assert ok('part_iv_signatures', 'Signatures')        # allowlisted named
        # Company-specific item suffixes beyond a-c are valid (Caterpillar labels
        # Executive Officers "Item 1D"); the recognizer admits any single letter.
        assert ok('part_i_item_1d', 'Item 1D')
        assert ok('Item 1D', 'Item 1D')
        assert not ok('part_ii_risk_management', 'Risk Management')
        assert not ok('part_iv_,_item_1a', ', Item 1A')
        assert not ok('part_ii_note_7:__share-based_compensation', 'Note 7: Share-Based Compensation')

    def test_make_section_key_infers_part_for_10k(self):
        """Regression (edgartools-3usf): with no detected part, a 10-K item gets
        its canonical part inferred from the item number, so keys are consistent
        instead of a bare 'Item N'."""
        a = TOCAnalyzer(form='10-K')
        assert a._make_section_key('Item 1', None) == 'part_i_item_1'
        assert a._make_section_key('Item 4', None) == 'part_i_item_4'
        assert a._make_section_key('Item 7', None) == 'part_ii_item_7'
        assert a._make_section_key('Item 9A', None) == 'part_ii_item_9a'
        assert a._make_section_key('Item 14', None) == 'part_iii_item_14'
        assert a._make_section_key('Item 15', None) == 'part_iv_item_15'
        # A detected part always wins over inference.
        assert a._make_section_key('Item 7', 'Part II') == 'part_ii_item_7'

    def test_make_section_key_no_inference_for_10q(self):
        """10-Q items repeat across parts (Part I Item 1 \u2260 Part II Item 1), so the
        part must be detected, never inferred \u2014 the bare key is kept."""
        a = TOCAnalyzer(form='10-Q')
        assert a._make_section_key('Item 1', None) == 'Item 1'
        assert a._make_section_key('Item 1', 'Part II') == 'part_ii_item_1'

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


# A 10-Q TOC whose Part I items are listed before any "Part I" header (only the
# "Part II" header is present as a link) — the jnj/pg shape that left Part I
# items keyless. Both Part I and Part II carry an "Item 1", so a bare key is
# ambiguous and downstream mis-resolves it (edgartools-3usf).
TEN_Q_NO_PART_I_HEADER_HTML = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
 <tr><td><a href="#anc_fin">Item 1.</a></td><td><a href="#anc_fin">Financial Statements</a></td><td>1</td></tr>
 <tr><td><a href="#anc_mda">Item 2.</a></td><td><a href="#anc_mda">Management's Discussion</a></td><td>20</td></tr>
 <tr><td><a href="#anc_mkt">Item 3.</a></td><td><a href="#anc_mkt">Market Risk</a></td><td>40</td></tr>
 <tr><td><a href="#anc_ctl">Item 4.</a></td><td><a href="#anc_ctl">Controls and Procedures</a></td><td>41</td></tr>
 <tr><td colspan="3"><a href="#anc_p2">Part II</a></td></tr>
 <tr><td><a href="#anc_legal">Item 1.</a></td><td><a href="#anc_legal">Legal Proceedings</a></td><td>42</td></tr>
 <tr><td><a href="#anc_exh">Item 6.</a></td><td><a href="#anc_exh">Exhibits</a></td><td>45</td></tr>
</table>
<div id="anc_fin"></div><div>Item 1. Financial Statements body</div>
<div id="anc_mda"></div><div>Item 2. MD&amp;A body</div>
<div id="anc_mkt"></div><div>Item 3. Market Risk body</div>
<div id="anc_ctl"></div><div>Item 4. Controls body</div>
<div id="anc_p2"></div>
<div id="anc_legal"></div><div>Item 1. Legal Proceedings body</div>
<div id="anc_exh"></div><div>Item 6. Exhibits body</div>
</body></html>
"""


class TestTenQPartSeed:
    """Part-I seeding for 10-Q TOC walks (edgartools-3usf, 10-Q half).

    A 10-Q opens with Part I, so items before any Part header are Part I — never
    a bare 'Item N' that downstream resolves to the Part II item of the same
    number (Item 1: Financial Statements vs Legal Proceedings)."""

    def test_pre_header_items_get_part_i(self):
        mapping = TOCAnalyzer(form='10-Q').analyze_toc_structure(
            TEN_Q_NO_PART_I_HEADER_HTML
        )
        # Part I items (before the only "Part II" header) are part_i_*, not bare.
        assert mapping.get('part_i_item_1') == 'anc_fin'
        assert mapping.get('part_i_item_2') == 'anc_mda'
        assert mapping.get('part_i_item_4') == 'anc_ctl'
        # Part II items (after the header) stay part_ii_*; Item 1 does not collide.
        assert mapping.get('part_ii_item_1') == 'anc_legal'
        assert mapping.get('part_ii_item_6') == 'anc_exh'
        # No bare keys leak through.
        assert not any(k.lower().startswith('item ') for k in mapping)

    def test_10k_walk_unseeded(self):
        """The seed is 10-Q-only; a 10-K walk still starts with no part context
        (it infers the part from the item number instead)."""
        a = TOCAnalyzer(form='10-K')
        assert a.schema.seed_part is None


class TestTenQGroundTruth:
    """Ground-truth keys/content from real 10-Q fixtures (edgartools-3usf)."""

    def _sections(self, ticker, fixture):
        from pathlib import Path
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        path = Path(__file__).parent / "fixtures" / "html" / fixture
        if not path.exists():
            pytest.skip(f"{ticker} 10-Q fixture not available: {path}")
        return parse_html(path.read_text(), ParserConfig(form="10-Q")).sections

    def test_jnj_part_i_item_1_is_financial_statements(self):
        secs = self._sections('jnj', 'jnj/10q/jnj-10-q-2025-07-24.html')
        # Every key is canonically part-prefixed — no bare 'Item N'.
        assert not any(k.lower().startswith('item ') for k in secs)
        # The same item number resolves to different content in each part:
        # Part I Item 1 = Financial Statements, Part II Item 1 = Legal Proceedings.
        assert 'financial statements' in secs['part_i_item_1'].text().lower()[:60]
        assert 'legal proceedings' in secs['part_ii_item_1'].text().lower()[:60]

    def test_pg_item_1_no_longer_bare(self):
        secs = self._sections('pg', 'pg/10q/pg-10-q-2025-04-24.html')
        # No *raw* key is a bare 'Item N' (membership via __contains__ still
        # resolves 'Item 1' → part_i_item_1 for backward compat — that's expected).
        assert not any(k.lower().startswith('item ') for k in secs.keys())
        assert 'financial statements' in secs['part_i_item_1'].text().lower()[:60]


class TestCaterpillarItem1D:
    """Company-specific item suffix from a real fixture (edgartools-sldz cat
    follow-up). Caterpillar labels 'Information about our Executive Officers' as
    Item 1D — a legitimate non-standard suffix the recognizer must accept."""

    def test_cat_item_1d_is_canonical_and_correct(self):
        from pathlib import Path
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        path = Path(__file__).parent / "fixtures" / "html" / "cat/10k/cat-10-k-2025-02-14.html"
        if not path.exists():
            pytest.skip(f"cat 10-K fixture not available: {path}")
        secs = parse_html(path.read_text(), ParserConfig(form="10-K")).sections
        # The full Part I item-1 family resolves, including the company-specific 1D.
        for key in ['part_i_item_1', 'part_i_item_1a', 'part_i_item_1b',
                    'part_i_item_1c', 'part_i_item_1d']:
            assert key in secs, f"missing {key}; got {sorted(secs.keys())}"
        # 1D is the Executive Officers section, correctly bounded (not a phantom).
        assert 'executive officers' in secs['part_i_item_1d'].text().lower()[:80]
        # Every key is now canonically shaped — no non-canonical leakage.
        canon = TOCAnalyzer._CANONICAL_ITEM_KEY
        assert all(canon.match(k) for k in secs.keys()), \
            f"non-canonical: {[k for k in secs if not canon.match(k)]}"


class TestSilentFailureObservability:
    """The TOC analyzer must not swallow failures silently (edgartools-hk9w):
    the agent-parser fallthrough and internal errors emit debug logs so the
    degradation path is diagnosable."""

    def test_agent_fallthrough_logs(self, caplog):
        """When a named agent parser finds nothing and we degrade to the generic
        scan, a debug log identifies which parser fell through."""
        import logging
        analyzer = TOCAnalyzer(form='10-K')
        # HTML with no Workiva TOC structure -> _analyze_workiva_toc returns {} ->
        # fallthrough to generic.
        html = "<html><body><p>No table of contents here.</p></body></html>"
        with caplog.at_level(logging.DEBUG, logger='edgar.documents.utils.toc_analyzer'):
            analyzer.analyze_toc_structure(html, agent='Workiva')
        assert any('Workiva' in r.message and 'generic' in r.message.lower()
                   for r in caplog.records), \
            f"no fallthrough log; records={[r.message for r in caplog.records]}"

    def test_no_blanket_silent_except(self):
        """Guard: no 'except Exception:' in the analyzer is immediately followed by
        a bare 'pass' — every catch logs or is a narrowed typed catch."""
        import re
        from pathlib import Path
        import edgar.documents.utils.toc_analyzer as mod
        src = Path(mod.__file__).read_text().splitlines()
        offenders = [i + 1 for i, line in enumerate(src)
                     if line.strip() == 'except Exception:'
                     and src[i + 1].strip() == 'pass']
        assert not offenders, f"silent 'except Exception: pass' at lines {offenders}"
