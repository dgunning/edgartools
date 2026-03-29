"""
Tests for the ConceptGraph — navigable knowledge graph of XBRL concepts.

Uses AAPL 10-Q fixtures for MetaLinks.json and R*.htm files.
"""
import pytest
from pathlib import Path

from edgar.sgml.metalinks import MetaLinks
from edgar.sgml.concept_extractor import extract_concepts_from_report
from edgar.sgml.concept_extractor import parse_numeric
from edgar.xbrl.concept_graph import Concept, ConceptGraph

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "attachments" / "aapl" / "20250329"


@pytest.fixture(scope="module")
def graph() -> ConceptGraph:
    """Build a ConceptGraph from AAPL 10-Q fixtures."""
    metalinks = MetaLinks.parse((FIXTURE_DIR / "MetaLinks.json").read_text())
    # Parse key reports
    concept_reports = {}
    for htm_file in sorted(FIXTURE_DIR.glob("R*.htm")):
        rkey = htm_file.stem  # "R2", "R4", etc.
        concept_reports[rkey] = extract_concepts_from_report(htm_file.read_text())
    return ConceptGraph.build(metalinks, concept_reports)


class TestConceptGraphBuild:

    def test_build_returns_graph(self, graph):
        assert isinstance(graph, ConceptGraph)

    def test_tag_count(self, graph):
        assert graph.tag_count == 450

    def test_report_count(self, graph):
        assert graph.report_count == 42

    def test_concept_count_with_values(self, graph):
        count = graph.concept_count_with_values
        assert count > 0
        assert count <= graph.tag_count


class TestConceptLookup:

    def test_lookup_by_tag_id(self, graph):
        concept = graph['us-gaap_Assets']
        assert concept is not None
        assert isinstance(concept, Concept)
        assert concept.id == 'us-gaap_Assets'

    def test_lookup_by_label(self, graph):
        concept = graph['Net income']
        assert concept is not None
        assert concept.id == 'us-gaap_NetIncomeLoss'

    def test_lookup_by_total_label(self, graph):
        concept = graph['Total assets']
        assert concept is not None
        assert concept.id == 'us-gaap_Assets'

    def test_lookup_case_insensitive(self, graph):
        concept = graph['net income']
        assert concept is not None

    def test_lookup_missing_returns_none(self, graph):
        assert graph['nonexistent_concept_xyz'] is None

    def test_concept_method(self, graph):
        concept = graph.concept('us-gaap_Assets')
        assert concept is not None
        assert concept.id == 'us-gaap_Assets'

    def test_concepts_are_cached(self, graph):
        c1 = graph['us-gaap_Assets']
        c2 = graph['us-gaap_Assets']
        assert c1 is c2


class TestConceptProperties:

    def test_label(self, graph):
        c = graph['us-gaap_Assets']
        assert c.label == 'Assets' or c.label == 'Total assets'

    def test_full_label(self, graph):
        c = graph['us-gaap_Assets']
        assert c.full_label == 'Assets'

    def test_crdr(self, graph):
        assert graph['us-gaap_Assets'].crdr == 'debit'
        assert graph['us-gaap_NetIncomeLoss'].crdr == 'credit'

    def test_documentation(self, graph):
        c = graph['us-gaap_Assets']
        assert 'economic benefit' in c.documentation

    def test_is_standard(self, graph):
        assert graph['us-gaap_Assets'].is_standard is True

    def test_is_monetary(self, graph):
        assert graph['us-gaap_Assets'].is_monetary is True

    def test_namespace(self, graph):
        assert graph['us-gaap_Assets'].namespace == 'us-gaap'

    def test_localname(self, graph):
        assert graph['us-gaap_Assets'].localname == 'Assets'

    def test_xbrltype(self, graph):
        assert graph['us-gaap_Assets'].xbrltype == 'monetaryItemType'


class TestConceptValues:

    def test_value_returns_string(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        assert c is not None
        val = c.value
        assert val is not None
        assert '95,359' in val

    def test_values_returns_dict(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        vals = c.values
        assert isinstance(vals, dict)
        assert len(vals) > 0

    def test_all_values_includes_dimensional(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        all_vals = c.all_values
        # Revenue appears in main + Products + Services sections
        assert len(all_vals) >= 1

    def test_concept_without_values(self, graph):
        """Abstract concepts or concepts only in MetaLinks may have no value."""
        c = graph['us-gaap_OperatingExpensesAbstract']
        if c:
            assert c.value is None


class TestConceptNavigation:

    def test_statements(self, graph):
        c = graph['us-gaap_Assets']
        stmts = c.statements
        assert len(stmts) > 0
        assert any('BALANCE SHEET' in s.upper() for s in stmts)

    def test_notes(self, graph):
        c = graph['us-gaap_NetIncomeLoss']
        # NetIncomeLoss may appear in note reports
        notes = c.notes
        # Just verify it returns a list (may be empty for some concepts)
        assert isinstance(notes, list)

    def test_report_names(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        names = c.report_names
        assert len(names) > 0


class TestCalculationTree:

    def test_children(self, graph):
        c = graph['us-gaap_Assets']
        children = c.children
        assert len(children) == 2
        child_ids = [ch.id for ch in children]
        assert 'us-gaap_AssetsCurrent' in child_ids
        assert 'us-gaap_AssetsNoncurrent' in child_ids

    def test_children_are_concepts(self, graph):
        c = graph['us-gaap_Assets']
        for child in c.children:
            assert isinstance(child, Concept)

    def test_parent(self, graph):
        c = graph['us-gaap_AssetsCurrent']
        if c:
            parent = c.parent
            assert parent is not None
            assert parent.id == 'us-gaap_Assets'

    def test_root_has_no_parent(self, graph):
        c = graph['us-gaap_Assets']
        # Assets is a root in the balance sheet role
        if c.is_root:
            assert c.parent is None

    def test_weight(self, graph):
        c = graph['us-gaap_AssetsCurrent']
        if c:
            assert c.weight == 1.0

    def test_is_root(self, graph):
        assert graph['us-gaap_Assets'].is_root is True

    def test_leaf_has_no_children(self, graph):
        """Walk to a leaf and verify empty children."""
        c = graph['us-gaap_Assets']
        # Walk down until we find a leaf
        current = c
        for _ in range(10):
            children = current.children
            if not children:
                break
            current = children[0]
        assert current.children == []

    def test_calculation_tree(self, graph):
        c = graph['us-gaap_Assets']
        tree = c.calculation_tree(max_depth=3)
        assert 'concept' in tree
        assert tree['concept'].id == 'us-gaap_Assets'
        assert 'children' in tree
        assert len(tree['children']) == 2


class TestSearch:

    def test_search_returns_concepts(self, graph):
        results = graph.search('revenue')
        assert len(results) > 0
        assert all(isinstance(c, Concept) for c in results)

    def test_search_relevance(self, graph):
        results = graph.search('Assets')
        assert results[0].id == 'us-gaap_Assets'

    def test_search_with_category(self, graph):
        all_results = graph.search('income')
        filtered = graph.search('income', category='Statements')
        assert len(filtered) <= len(all_results)

    def test_search_empty(self, graph):
        results = graph.search('zzzznonexistentzzz')
        assert results == []


class TestValidation:

    def test_validate_returns_results(self, graph):
        results = graph.validate()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_validation_result_structure(self, graph):
        results = graph.validate()
        for r in results:
            assert 'parent' in r
            assert 'expected' in r
            assert 'computed' in r
            assert 'difference' in r
            assert 'valid' in r
            assert isinstance(r['parent'], Concept)

    def test_most_validations_pass(self, graph):
        results = graph.validate()
        valid_count = sum(1 for r in results if r['valid'])
        # Most calculation trees should sum correctly (allow some rounding)
        assert valid_count >= len(results) * 0.5


class TestNumericValues:

    def test_concept_numeric_value(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        assert c.numeric_value == 95359.0

    def test_concept_numeric_values(self, graph):
        c = graph['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']
        nv = c.numeric_values
        assert isinstance(nv, dict)
        assert len(nv) > 0
        assert all(isinstance(v, (float, type(None))) for v in nv.values())

    def test_negative_numeric_value(self, graph):
        c = graph['us-gaap_NonoperatingIncomeExpense']
        if c and c.numeric_value is not None:
            assert c.numeric_value == -279.0

    def test_abstract_has_no_numeric_value(self, graph):
        c = graph['us-gaap_OperatingExpensesAbstract']
        if c:
            assert c.numeric_value is None


class TestParseNumeric:

    def test_positive(self):
        assert parse_numeric('$ 95,359') == 95359.0

    def test_negative_parens(self):
        assert parse_numeric('(279)') == -279.0

    def test_decimal(self):
        assert parse_numeric('$ 1.65') == 1.65

    def test_plain_number(self):
        assert parse_numeric('14,994,082') == 14994082.0

    def test_empty(self):
        assert parse_numeric('') is None

    def test_non_numeric(self):
        assert parse_numeric('N/A') is None

    def test_unicode_minus(self):
        assert parse_numeric('−279') == -279.0


class TestDisplay:

    def test_concept_repr(self, graph):
        c = graph['us-gaap_Assets']
        r = repr(c)
        assert 'us-gaap_Assets' in r

    def test_concept_str(self, graph):
        c = graph['us-gaap_Assets']
        s = str(c)
        assert 'Assets' in s

    def test_concept_rich(self, graph):
        c = graph['us-gaap_Assets']
        panel = c.__rich__()
        assert panel is not None

    def test_graph_repr(self, graph):
        r = repr(graph)
        assert 'ConceptGraph' in r
        assert '450' in r


class TestToContext:

    def test_standard_context(self, graph):
        c = graph['us-gaap_Assets']
        ctx = c.to_context()
        assert 'us-gaap_Assets' in ctx
        assert 'debit' in ctx

    def test_full_context(self, graph):
        c = graph['us-gaap_Assets']
        ctx = c.to_context(detail='full')
        assert 'Components' in ctx or 'Appears in' in ctx
