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
