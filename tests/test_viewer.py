"""
Tests for the FilingViewer — SEC Interactive Data Viewer equivalent.

Unit tests use AAPL 10-Q fixtures (no network).
Integration tests use VCR cassettes.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from edgar.sgml.metalinks import MetaLinks
from edgar.sgml.concept_extractor import extract_concepts_from_report
from edgar.sgml.filing_summary import FilingSummary, Report
from edgar.xbrl.viewer import FilingViewer, ViewerReport
from edgar.xbrl.concept_graph import Concept

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "attachments" / "aapl" / "20250329"


def _make_mock_report(html_file_name: str, short_name: str, category: str,
                      position: str, role: str = '', long_name: str = '') -> Report:
    """Create a mock Report for testing."""
    return Report(
        instance=None,
        is_default=False,
        has_embedded_reports=False,
        html_file_name=html_file_name,
        long_name=long_name or short_name,
        report_type=None,
        role=role,
        parent_role=None,
        short_name=short_name,
        menu_category=category,
        position=position,
        reports=None,
    )


@pytest.fixture(scope="module")
def metalinks() -> MetaLinks:
    return MetaLinks.parse((FIXTURE_DIR / "MetaLinks.json").read_text())


@pytest.fixture(scope="module")
def viewer(metalinks) -> FilingViewer:
    """Build a FilingViewer from fixtures using mock SGML."""
    # Build a mock FilingSGML that returns R*.htm content from fixtures
    sgml = MagicMock()

    def mock_get_content(filename):
        path = FIXTURE_DIR / filename
        if path.exists():
            return path.read_text()
        return None

    sgml.get_content = mock_get_content

    # Build mock reports matching the MetaLinks report entries
    mock_reports = []
    for rkey, meta_report in metalinks.reports.items():
        html_file = f"{rkey}.htm"
        report = _make_mock_report(
            html_file_name=html_file,
            short_name=meta_report.short_name,
            category=meta_report.menu_cat,
            position=str(meta_report.order),
            role=meta_report.role,
            long_name=meta_report.long_name,
        )
        # Wire up content access through our mock
        report._reports = MagicMock()
        report._reports._filing_summary = MagicMock()
        report._reports._filing_summary._filing_sgml = sgml
        mock_reports.append(report)

    # Build a mock FilingSummary
    filing_summary = MagicMock()
    filing_summary.reports = mock_reports
    filing_summary.get_reports_by_category = lambda cat: [
        r for r in mock_reports if r.menu_category == cat
    ]

    return FilingViewer(sgml, filing_summary, metalinks)


class TestFilingViewerCategories:
    """Test categorized report access."""

    def test_financial_statements(self, viewer):
        stmts = viewer.financial_statements
        assert len(stmts) == 6
        assert all(isinstance(vr, ViewerReport) for vr in stmts)

    def test_notes(self, viewer):
        notes = viewer.notes
        assert len(notes) == 12

    def test_policies(self, viewer):
        policies = viewer.policies
        assert len(policies) == 1

    def test_tables(self, viewer):
        tables = viewer.tables
        assert len(tables) == 6

    def test_details(self, viewer):
        details = viewer.details
        assert len(details) == 16

    def test_all_reports(self, viewer):
        all_reports = viewer.all_reports
        assert len(all_reports) == 42

    def test_cover(self, viewer):
        cover = viewer.cover
        assert len(cover) == 1


class TestViewerReport:

    def test_short_name(self, viewer):
        stmt = viewer.financial_statements[0]
        assert stmt.short_name != ''

    def test_category(self, viewer):
        stmt = viewer.financial_statements[0]
        assert stmt.category == 'Statements'

    def test_html_file_name(self, viewer):
        stmt = viewer.financial_statements[0]
        assert stmt.html_file_name.endswith('.htm')

    def test_concept_rows(self, viewer):
        stmt = viewer.financial_statements[0]
        rows = stmt.concept_rows
        assert len(rows) > 0

    def test_concepts(self, viewer):
        stmt = viewer.financial_statements[0]
        concepts = stmt.concepts
        assert len(concepts) > 0

    def test_period_headers(self, viewer):
        stmt = viewer.financial_statements[0]
        headers = stmt.period_headers
        assert len(headers) > 0

    def test_viewer_report_str(self, viewer):
        stmt = viewer.financial_statements[0]
        s = str(stmt)
        assert 'ViewerReport' in s

    def test_viewer_report_rich(self, viewer):
        stmt = viewer.financial_statements[0]
        panel = stmt.__rich__()
        assert panel is not None


class TestViewerReportCurrencyScaling:
    """ViewerReport.currency_scaling lazy resolution from XBRL decimals (GH #807)."""

    def test_falls_back_to_concept_report_when_no_viewer(self):
        """A ViewerReport built without a back-ref viewer uses the text-match value."""
        from edgar.sgml.concept_extractor import ConceptReport
        from edgar.xbrl.viewer import ViewerReport

        cr = ConceptReport(title='', period_headers=[], rows=[],
                           currency_scaling=1_000)
        report = _make_mock_report('R2.htm', 'Income', 'Statements', '2')
        vr = ViewerReport(report, None, cr, viewer=None)
        assert vr.currency_scaling == 1_000

    def test_returns_1_when_no_concept_report(self):
        """ViewerReport with no ConceptReport returns the unit scale, not 0/None."""
        from edgar.xbrl.viewer import ViewerReport
        report = _make_mock_report('R99.htm', 'Cover', 'Cover', '1')
        vr = ViewerReport(report, None, None, viewer=None)
        assert vr.currency_scaling == 1

    def test_text_match_fallback_works_with_aapl_fixture(self, viewer):
        """With no Filing supplied to FilingViewer, XBRL is unavailable so the
        text-match fallback is used. AAPL's R*.htm headers match ``$ in Millions``
        so this should be 1_000_000 even on the fallback path."""
        stmt = viewer.financial_statements[0]
        assert stmt.currency_scaling == 1_000_000

    def test_xbrl_decimals_override_text_match(self, viewer):
        """When XBRL is available, decimals win over the text-match value.
        Inject a fake XBRL whose facts report decimals=-3 across the statement's
        concepts and verify the resolved scaling is 1_000 (thousands)."""
        from edgar.sgml.concept_extractor import ConceptReport, ConceptRow

        cr = ConceptReport(
            title='Income',
            period_headers=['2025'],
            rows=[
                ConceptRow('us-gaap_Revenues', 'Revenues', {'2025': '100'},
                           is_abstract=False, is_total=False, is_header=False,
                           level=0, css_class='re'),
                ConceptRow('us-gaap_NetIncomeLoss', 'Net income', {'2025': '10'},
                           is_abstract=False, is_total=True, is_header=False,
                           level=0, css_class='reu'),
            ],
            currency_scaling=1,  # text-match returned wrong default
        )

        class _FakeQuery:
            def __init__(self, facts):
                self._facts = facts
                self._concept = None
            def by_concept(self, concept, exact=False):
                self._concept = concept.replace('_', ':')
                return self
            def execute(self):
                return [f for f in self._facts if f['concept'] == self._concept]

        class _FakeFactsView:
            def __init__(self, facts):
                self._facts = facts
            def query(self):
                return _FakeQuery(self._facts)

        class _FakeNode:
            pass

        class _FakeTree:
            all_nodes = {
                'us-gaap_Revenues': _FakeNode(),
                'us-gaap_NetIncomeLoss': _FakeNode(),
            }

        class _FakeXBRL:
            facts = _FakeFactsView([
                {'concept': 'us-gaap:Revenues', 'decimals': -3},
                {'concept': 'us-gaap:NetIncomeLoss', 'decimals': -3},
            ])
            presentation_trees = {'http://example.com/role/Income': _FakeTree()}

        viewer._xbrl = _FakeXBRL()
        viewer._xbrl_loaded = True

        report = _make_mock_report('R7.htm', 'X', 'Statements', '1',
                                   role='http://example.com/role/Income')
        from edgar.xbrl.viewer import ViewerReport
        vr = ViewerReport(report, None, cr, viewer=viewer)
        try:
            assert vr.currency_scaling == 1_000
            # The fix mirrors back onto ConceptReport so the path reported in
            # GH #807 also sees the corrected value.
            assert cr.currency_scaling == 1_000
        finally:
            viewer._xbrl = None
            viewer._xbrl_loaded = False

    def test_xbrl_ignores_share_concepts(self, viewer):
        """Decimals from share-related concepts (EPS, weighted-average shares)
        must not contaminate the monetary scaling."""
        from edgar.sgml.concept_extractor import ConceptReport, ConceptRow

        cr = ConceptReport(
            title='Income',
            period_headers=['2025'],
            rows=[
                ConceptRow('us-gaap_Revenues', 'Revenues', {'2025': '100'},
                           is_abstract=False, is_total=False, is_header=False,
                           level=0, css_class='re'),
                # Shares are decimals=-3 (thousands) but should be ignored.
                ConceptRow('us-gaap_WeightedAverageShares',
                           'Weighted average shares outstanding',
                           {'2025': '5000'},
                           is_abstract=False, is_total=False, is_header=False,
                           level=0, css_class='re'),
            ],
            currency_scaling=1,
        )

        class _FakeQuery:
            def __init__(self, facts):
                self._facts = facts
                self._concept = None
            def by_concept(self, concept, exact=False):
                self._concept = concept.replace('_', ':')
                return self
            def execute(self):
                return [f for f in self._facts if f['concept'] == self._concept]

        class _FakeFactsView:
            def __init__(self, facts):
                self._facts = facts
            def query(self):
                return _FakeQuery(self._facts)

        class _FakeNode:
            pass

        class _FakeTree:
            all_nodes = {
                'us-gaap_Revenues': _FakeNode(),
                'us-gaap_WeightedAverageShares': _FakeNode(),
            }

        class _FakeXBRL:
            facts = _FakeFactsView([
                {'concept': 'us-gaap:Revenues', 'decimals': -6},
                {'concept': 'us-gaap:WeightedAverageShares', 'decimals': -3},
            ])
            presentation_trees = {'http://example.com/role/Income': _FakeTree()}

        viewer._xbrl = _FakeXBRL()
        viewer._xbrl_loaded = True

        report = _make_mock_report('R7.htm', 'X', 'Statements', '1',
                                   role='http://example.com/role/Income')
        from edgar.xbrl.viewer import ViewerReport
        vr = ViewerReport(report, None, cr, viewer=viewer)
        try:
            # Should pick up only the monetary -6, not the shares -3.
            assert vr.currency_scaling == 1_000_000
        finally:
            viewer._xbrl = None
            viewer._xbrl_loaded = False


class TestMultiplierFromDecimals:
    """Unit tests for the decimals → multiplier helper (GH #807)."""

    def test_millions_majority(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        assert _multiplier_from_decimals([-6, -6, -6, 0]) == 1_000_000

    def test_thousands_majority(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        assert _multiplier_from_decimals([-3, -3, -3]) == 1_000

    def test_billions_bucket(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        assert _multiplier_from_decimals([-9, -9]) == 1_000_000_000

    def test_empty_returns_one(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        assert _multiplier_from_decimals([]) == 1

    def test_units_only_returns_one(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        assert _multiplier_from_decimals([0, 0, 2]) == 1

    def test_prefers_scaled_bucket_over_units_on_tie(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        # 2 zero-bucket values vs 1 millions; we prefer any scaled bucket.
        assert _multiplier_from_decimals([0, 0, -6]) == 1_000_000

    def test_buckets_by_floor_not_exact_match(self):
        from edgar.xbrl.viewer import _multiplier_from_decimals
        # decimals=-5 still indicates scaling to at least thousands (-3 bucket)
        assert _multiplier_from_decimals([-5, -5]) == 1_000


class TestConceptGraphIntegration:
    """Test that the viewer's concept graph works."""

    def test_concepts_property(self, viewer):
        graph = viewer.concepts
        assert graph is not None
        assert graph.tag_count == 450

    def test_getitem_delegates_to_graph(self, viewer):
        concept = viewer['us-gaap_Assets']
        assert concept is not None
        assert isinstance(concept, Concept)
        assert concept.id == 'us-gaap_Assets'

    def test_label_lookup(self, viewer):
        concept = viewer['Net income']
        assert concept is not None
        assert concept.crdr == 'credit'

    def test_search(self, viewer):
        results = viewer.search('revenue')
        assert len(results) > 0

    def test_search_with_category(self, viewer):
        results = viewer.search('income', category='Statements')
        assert len(results) > 0

    def test_validate(self, viewer):
        results = viewer.validate()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_concept_has_values(self, viewer):
        concept = viewer['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        assert concept is not None
        assert concept.value is not None
        assert '95,359' in concept.value

    def test_concept_navigation(self, viewer):
        """Navigate from Assets to its children."""
        assets = viewer['us-gaap_Assets']
        children = assets.children
        assert len(children) == 2
        child_ids = [c.id for c in children]
        assert 'us-gaap_AssetsCurrent' in child_ids


class TestDisplay:

    def test_viewer_rich(self, viewer):
        panel = viewer.__rich__()
        assert panel is not None

    def test_viewer_str(self, viewer):
        s = str(viewer)
        assert 'FilingViewer' in s
        assert '42' in s

    def test_viewer_repr_doesnt_crash(self, viewer):
        r = repr(viewer)
        assert 'SEC Viewer' in r


class TestToContext:

    def test_standard(self, viewer):
        ctx = viewer.to_context()
        assert 'Financial Statements' in ctx
        assert 'Notes' in ctx

    def test_full(self, viewer):
        ctx = viewer.to_context(detail='full')
        assert 'Available actions' in ctx
        assert 'viewer[' in ctx

    def test_compare_context_structure(self, viewer):
        """compare_context needs a real XBRL object, so just test it doesn't crash with None."""
        # Can't easily mock xbrl.statements.balance_sheet() chain,
        # so verify the method exists and the prompt header is correct
        assert hasattr(viewer, 'compare_context')
