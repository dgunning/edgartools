"""
Tests for MetaLinks.json parser.

Uses the AAPL 10-Q fixture at tests/fixtures/attachments/aapl/20250329/MetaLinks.json.
"""
import pytest
from pathlib import Path

from edgar.sgml.metalinks import MetaLinks, TagDefinition, CalculationEntry, MetaLinksReport, AuthRef

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "attachments" / "aapl" / "20250329" / "MetaLinks.json"


@pytest.fixture(scope="module")
def metalinks() -> MetaLinks:
    return MetaLinks.parse(FIXTURE_PATH.read_text())


class TestMetaLinksParsing:
    """Test that MetaLinks.json is parsed correctly."""

    def test_parse_returns_metalinks(self, metalinks):
        assert isinstance(metalinks, MetaLinks)

    def test_version(self, metalinks):
        assert metalinks.version == "2.2"

    def test_instance_key(self, metalinks):
        assert metalinks.instance_key == "aapl-20250329.htm"

    def test_tag_count(self, metalinks):
        assert metalinks.tag_count == 450

    def test_report_count(self, metalinks):
        assert metalinks.report_count == 42

    def test_stats(self, metalinks):
        assert metalinks.stats['key_standard'] == 183
        assert metalinks.stats['key_custom'] == 14
        assert metalinks.stats['element_count'] == 450
        assert metalinks.stats['context_count'] == 163


class TestTagDefinition:
    """Test tag definition parsing and properties."""

    def test_get_tag_by_id(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        assert tag is not None
        assert isinstance(tag, TagDefinition)

    def test_assets_tag_fields(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        assert tag.xbrltype == 'monetaryItemType'
        assert tag.nsuri == 'http://fasb.org/us-gaap/2024'
        assert tag.localname == 'Assets'
        assert tag.crdr == 'debit'
        assert tag.label == 'Assets'
        assert tag.total_label == 'Total assets'
        assert 'present right to economic benefit' in tag.documentation

    def test_net_income_tag(self, metalinks):
        tag = metalinks.get_tag('us-gaap_NetIncomeLoss')
        assert tag is not None
        assert tag.crdr == 'credit'
        assert tag.terse_label == 'Net income'
        assert 'attributable to the parent' in tag.documentation

    def test_custom_tag_no_crdr(self, metalinks):
        """Custom tags (company-specific) typically have no crdr."""
        tag = metalinks.get_tag('aapl_A0.000Notesdue2025Member')
        assert tag is not None
        assert tag.crdr is None
        assert tag.xbrltype == 'domainItemType'

    def test_namespace_property(self, metalinks):
        assert metalinks.get_tag('us-gaap_Assets').namespace == 'us-gaap'
        assert metalinks.get_tag('aapl_A0.000Notesdue2025Member').namespace == 'aapl'

    def test_is_standard(self, metalinks):
        assert metalinks.get_tag('us-gaap_Assets').is_standard is True
        assert metalinks.get_tag('aapl_A0.000Notesdue2025Member').is_standard is False

    def test_is_monetary(self, metalinks):
        assert metalinks.get_tag('us-gaap_Assets').is_monetary is True
        assert metalinks.get_tag('aapl_A0.000Notesdue2025Member').is_monetary is False

    def test_is_member(self, metalinks):
        assert metalinks.get_tag('aapl_A0.000Notesdue2025Member').is_member is True
        assert metalinks.get_tag('us-gaap_Assets').is_member is False

    def test_presentation_roles(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        assert len(tag.presentation) >= 1
        assert any('BalanceSheet' in r or 'BALANCESHEET' in r for r in tag.presentation)

    def test_missing_tag_returns_none(self, metalinks):
        assert metalinks.get_tag('nonexistent_Tag') is None

    def test_auth_ref_ids(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        assert len(tag.auth_ref_ids) > 0
        assert all(isinstance(rid, str) for rid in tag.auth_ref_ids)


class TestLabelLookup:
    """Test looking up tags by human-readable label."""

    def test_get_tag_by_terse_label(self, metalinks):
        tag = metalinks.get_tag_by_label('Net income')
        assert tag is not None
        assert tag.tag_id == 'us-gaap_NetIncomeLoss'

    def test_get_tag_by_label_case_insensitive(self, metalinks):
        tag = metalinks.get_tag_by_label('net income')
        assert tag is not None
        assert tag.tag_id == 'us-gaap_NetIncomeLoss'

    def test_get_tag_by_total_label(self, metalinks):
        tag = metalinks.get_tag_by_label('Total assets')
        assert tag is not None
        assert tag.tag_id == 'us-gaap_Assets'

    def test_missing_label_returns_none(self, metalinks):
        assert metalinks.get_tag_by_label('This Label Does Not Exist') is None


class TestCalculationTree:
    """Test calculation relationship navigation."""

    def test_assets_is_calculation_root(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        assert tag.is_root_in(balance_sheet_role) is True

    def test_assets_children(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        children = metalinks.get_calculation_children('us-gaap_Assets', balance_sheet_role)
        assert len(children) == 2
        child_ids = [c.tag_id for c in children]
        assert 'us-gaap_AssetsCurrent' in child_ids
        assert 'us-gaap_AssetsNoncurrent' in child_ids

    def test_calculation_children_ordered(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        children = metalinks.get_calculation_children('us-gaap_Assets', balance_sheet_role)
        # AssetsCurrent should come before AssetsNoncurrent
        assert children[0].tag_id == 'us-gaap_AssetsCurrent'
        assert children[1].tag_id == 'us-gaap_AssetsNoncurrent'

    def test_net_income_has_parent_in_comprehensive_income(self, metalinks):
        tag = metalinks.get_tag('us-gaap_NetIncomeLoss')
        comp_income_role = [r for r in tag.calculations if 'COMPREHENSIVE' in r.upper()][0]
        entry = tag.calculation_in(comp_income_role)
        assert entry is not None
        assert entry.parent_tag == 'us-gaap_ComprehensiveIncomeNetOfTax'
        assert entry.weight == 1.0

    def test_net_income_is_root_in_operations(self, metalinks):
        tag = metalinks.get_tag('us-gaap_NetIncomeLoss')
        ops_role = [r for r in tag.calculations if 'OPERATIONS' in r.upper()][0]
        assert tag.is_root_in(ops_role) is True

    def test_get_calculation_roots(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        roots = metalinks.get_calculation_roots(balance_sheet_role)
        root_ids = [r.tag_id for r in roots]
        assert 'us-gaap_Assets' in root_ids

    def test_get_calculation_tree(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        tree = metalinks.get_calculation_tree('us-gaap_Assets', balance_sheet_role)
        assert tree['tag'].tag_id == 'us-gaap_Assets'
        assert len(tree['children']) == 2
        # Children should have their own children
        for child in tree['children']:
            assert 'tag' in child
            assert 'children' in child

    def test_leaf_has_no_children(self, metalinks):
        """A leaf concept (no children) should have empty children list in tree."""
        tag = metalinks.get_tag('us-gaap_Assets')
        balance_sheet_role = [r for r in tag.presentation if 'BALANCESHEET' in r.upper()][0]
        tree = metalinks.get_calculation_tree('us-gaap_Assets', balance_sheet_role, max_depth=10)
        # Walk to a leaf
        def find_leaf(node):
            if not node.get('children'):
                return node
            for child in node['children']:
                leaf = find_leaf(child)
                if leaf:
                    return leaf
            return None
        leaf = find_leaf(tree)
        assert leaf is not None
        assert leaf['children'] == []


class TestReports:
    """Test report metadata parsing."""

    def test_report_count(self, metalinks):
        assert len(metalinks.reports) == 42

    def test_get_report_by_key(self, metalinks):
        report = metalinks.get_report('R2')
        assert report is not None
        assert isinstance(report, MetaLinksReport)

    def test_report_fields(self, metalinks):
        report = metalinks.get_report('R2')
        assert report.group_type == 'statement'
        assert report.menu_cat == 'Statements'
        assert 'OPERATIONS' in report.short_name.upper()
        assert report.order == 2

    def test_reports_by_category(self, metalinks):
        statements = metalinks.get_reports_by_category('Statements')
        assert len(statements) == 6
        notes = metalinks.get_reports_by_category('Notes')
        assert len(notes) == 12
        policies = metalinks.get_reports_by_category('Policies')
        assert len(policies) == 1
        tables = metalinks.get_reports_by_category('Tables')
        assert len(tables) == 6
        details = metalinks.get_reports_by_category('Details')
        assert len(details) == 16

    def test_reports_by_category_sorted(self, metalinks):
        statements = metalinks.get_reports_by_category('Statements')
        orders = [r.order for r in statements]
        assert orders == sorted(orders)

    def test_first_anchor(self, metalinks):
        report = metalinks.get_report('R2')
        assert report.first_anchor is not None
        assert 'Revenue' in report.first_anchor or 'revenue' in report.first_anchor.lower()


class TestAuthRefs:
    """Test authoritative reference parsing."""

    def test_auth_ref_count(self, metalinks):
        assert len(metalinks._auth_refs) > 900

    def test_get_auth_ref(self, metalinks):
        ref = metalinks.get_auth_ref('r0')
        assert ref is not None
        assert isinstance(ref, AuthRef)
        assert ref.publisher == 'FASB'
        assert 'fasb.org' in ref.uri

    def test_get_auth_refs_for_tag(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        refs = metalinks.get_auth_refs_for_tag(tag)
        assert len(refs) > 0
        assert all(isinstance(r, AuthRef) for r in refs)
        assert any(r.publisher == 'FASB' for r in refs)


class TestSearch:
    """Test tag search functionality."""

    def test_search_by_label(self, metalinks):
        results = metalinks.search('revenue')
        assert len(results) > 0
        # The top result should have 'revenue' in its label
        top = results[0]
        assert 'revenue' in top.terse_label.lower() or 'revenue' in top.label.lower()

    def test_search_exact_match_first(self, metalinks):
        results = metalinks.search('Assets')
        assert results[0].tag_id == 'us-gaap_Assets'

    def test_search_by_documentation(self, metalinks):
        results = metalinks.search('economic benefit')
        assert len(results) > 0

    def test_search_with_category_filter(self, metalinks):
        all_results = metalinks.search('income')
        filtered = metalinks.search('income', category='Statements')
        assert len(filtered) <= len(all_results)
        # All filtered results should appear in statement roles
        statement_reports = metalinks.get_reports_by_category('Statements')
        statement_roles = {r.role for r in statement_reports}
        for tag in filtered:
            assert any(r in statement_roles for r in tag.presentation)

    def test_search_no_results(self, metalinks):
        results = metalinks.search('zzzznonexistenttermzzzz')
        assert results == []


class TestRepr:

    def test_metalinks_repr(self, metalinks):
        r = repr(metalinks)
        assert 'MetaLinks' in r
        assert '450' in r
        assert '42' in r

    def test_tag_repr(self, metalinks):
        tag = metalinks.get_tag('us-gaap_Assets')
        r = repr(tag)
        assert 'us-gaap_Assets' in r
        assert 'debit' in r

    def test_tag_repr_no_crdr(self, metalinks):
        tag = metalinks.get_tag('aapl_A0.000Notesdue2025Member')
        r = repr(tag)
        assert 'crdr' not in r
