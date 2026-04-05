"""
Unit tests for edgar.entity.statement_builder module.

These tests focus on the dataclasses and pure helper methods without requiring
external data files or network access.
"""

from dataclasses import field
from datetime import date
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from edgar.entity.models import DataQuality, FinancialFact
from edgar.entity.statement_builder import (
    StatementBuilder,
    StatementItem,
    StructuredStatement,
)


# =============================================================================
# Test Fixtures - Sample Data
# =============================================================================

@pytest.fixture
def sample_statement_item():
    """Create a basic statement item for testing."""
    return StatementItem(
        concept='Revenue',
        label='Total Revenue',
        value=1_000_000_000.0,
        depth=0,
        parent_concept=None,
        is_abstract=False,
        is_total=False,
        section='Income',
        confidence=1.0,
        source='fact'
    )


@pytest.fixture
def abstract_statement_item():
    """Create an abstract (header) statement item."""
    return StatementItem(
        concept='RevenueAbstract',
        label='Revenue',
        value=None,
        depth=0,
        parent_concept=None,
        is_abstract=True,
        is_total=False,
        section='Income',
        confidence=1.0,
        source='canonical'
    )


@pytest.fixture
def total_statement_item():
    """Create a total line item."""
    return StatementItem(
        concept='TotalRevenue',
        label='Total Revenue',
        value=5_000_000_000.0,
        depth=0,
        parent_concept=None,
        is_abstract=False,
        is_total=True,
        section='Income',
        confidence=1.0,
        source='fact'
    )


@pytest.fixture
def hierarchical_items():
    """Create a hierarchy of statement items."""
    child1 = StatementItem(
        concept='ProductRevenue',
        label='Product Revenue',
        value=600_000_000.0,
        depth=1,
        parent_concept='Revenue',
        children=[]
    )
    child2 = StatementItem(
        concept='ServiceRevenue',
        label='Service Revenue',
        value=400_000_000.0,
        depth=1,
        parent_concept='Revenue',
        children=[]
    )
    parent = StatementItem(
        concept='Revenue',
        label='Total Revenue',
        value=1_000_000_000.0,
        depth=0,
        parent_concept=None,
        children=[child1, child2]
    )
    return parent, child1, child2


@pytest.fixture
def sample_financial_fact():
    """Create a sample FinancialFact for testing."""
    return FinancialFact(
        concept='us-gaap:Revenue',
        taxonomy='us-gaap',
        label='Total Revenue',
        value=1_000_000_000,
        numeric_value=1_000_000_000.0,
        unit='USD',
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        period_type='duration',
        fiscal_year=2024,
        fiscal_period='FY',
        filing_date=date(2025, 2, 15),
        form_type='10-K',
        accession='0000320193-25-000001',
        statement_type='IncomeStatement',
        is_abstract=False,
        is_total=False,
        section='Revenue'
    )


@pytest.fixture
def sample_facts():
    """Create a list of sample facts for different statements and periods."""
    return [
        FinancialFact(
            concept='us-gaap:Revenue',
            taxonomy='us-gaap',
            label='Total Revenue',
            value=1_000_000_000,
            numeric_value=1_000_000_000.0,
            unit='USD',
            period_end=date(2024, 12, 31),
            fiscal_year=2024,
            fiscal_period='FY',
            filing_date=date(2025, 2, 15),
            statement_type='IncomeStatement'
        ),
        FinancialFact(
            concept='us-gaap:CostOfRevenue',
            taxonomy='us-gaap',
            label='Cost of Revenue',
            value=600_000_000,
            numeric_value=600_000_000.0,
            unit='USD',
            period_end=date(2024, 12, 31),
            fiscal_year=2024,
            fiscal_period='FY',
            filing_date=date(2025, 2, 15),
            statement_type='IncomeStatement'
        ),
        FinancialFact(
            concept='us-gaap:Assets',
            taxonomy='us-gaap',
            label='Total Assets',
            value=5_000_000_000,
            numeric_value=5_000_000_000.0,
            unit='USD',
            period_end=date(2024, 12, 31),
            fiscal_year=2024,
            fiscal_period='FY',
            filing_date=date(2025, 2, 15),
            statement_type='BalanceSheet'
        ),
        FinancialFact(
            concept='us-gaap:Revenue',
            taxonomy='us-gaap',
            label='Total Revenue',
            value=800_000_000,
            numeric_value=800_000_000.0,
            unit='USD',
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period='FY',
            filing_date=date(2024, 2, 15),
            statement_type='IncomeStatement'
        ),
    ]


# =============================================================================
# Tests for StatementItem
# =============================================================================

class TestStatementItem:
    """Tests for the StatementItem dataclass."""

    def test_statement_item_creation(self, sample_statement_item):
        """Basic creation test."""
        item = sample_statement_item
        assert item.concept == 'Revenue'
        assert item.label == 'Total Revenue'
        assert item.value == 1_000_000_000.0
        assert item.depth == 0
        assert item.is_abstract is False
        assert item.is_total is False
        assert item.source == 'fact'

    def test_statement_item_defaults(self):
        """Test default values for optional fields."""
        item = StatementItem(
            concept='Test',
            label='Test Item',
            value=100.0,
            depth=0,
            parent_concept=None
        )
        assert item.children == []
        assert item.is_abstract is False
        assert item.is_total is False
        assert item.section is None
        assert item.confidence == 1.0
        assert item.source == 'fact'
        assert item.fact is None

    def test_to_dict_basic(self, sample_statement_item):
        """Test conversion to dictionary."""
        result = sample_statement_item.to_dict()

        assert result['concept'] == 'Revenue'
        assert result['label'] == 'Total Revenue'
        assert result['value'] == 1_000_000_000.0
        assert result['depth'] == 0
        assert result['is_abstract'] is False
        assert result['is_total'] is False
        assert result['section'] == 'Income'
        assert result['confidence'] == 1.0
        assert result['source'] == 'fact'
        assert result['children'] == []

    def test_to_dict_with_children(self, hierarchical_items):
        """Test to_dict includes children recursively."""
        parent, child1, child2 = hierarchical_items
        result = parent.to_dict()

        assert len(result['children']) == 2
        assert result['children'][0]['concept'] == 'ProductRevenue'
        assert result['children'][1]['concept'] == 'ServiceRevenue'

    # -------------------------------------------------------------------------
    # Tests for get_display_value
    # -------------------------------------------------------------------------

    def test_get_display_value_billions(self):
        """Values >= 1B should display as billions."""
        item = StatementItem(
            concept='Test', label='Test', value=5_500_000_000.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$5.5B'

    def test_get_display_value_millions(self):
        """Values >= 1M should display as millions."""
        item = StatementItem(
            concept='Test', label='Test', value=250_000_000.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$250.0M'

    def test_get_display_value_thousands(self):
        """Values >= 1K should display as thousands."""
        item = StatementItem(
            concept='Test', label='Test', value=50_000.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$50K'

    def test_get_display_value_small(self):
        """Small values should display as raw numbers."""
        item = StatementItem(
            concept='Test', label='Test', value=500.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$500'

    def test_get_display_value_negative(self):
        """Negative values should be formatted correctly."""
        item = StatementItem(
            concept='Test', label='Test', value=-1_500_000_000.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$-1.5B'

    def test_get_display_value_none_abstract(self):
        """Abstract items with None value should return empty string."""
        item = StatementItem(
            concept='Test', label='Test', value=None,
            depth=0, parent_concept=None, is_abstract=True
        )
        assert item.get_display_value() == ''

    def test_get_display_value_none_placeholder(self):
        """Placeholder items should return '[Missing]'."""
        item = StatementItem(
            concept='Test', label='Test', value=None,
            depth=0, parent_concept=None, source='placeholder'
        )
        assert item.get_display_value() == '[Missing]'

    def test_get_display_value_none_other(self):
        """Other items with None value should return '-'."""
        item = StatementItem(
            concept='Test', label='Test', value=None,
            depth=0, parent_concept=None, source='fact'
        )
        assert item.get_display_value() == '-'

    def test_get_display_value_zero(self):
        """Zero values should display as $0."""
        item = StatementItem(
            concept='Test', label='Test', value=0.0,
            depth=0, parent_concept=None
        )
        assert item.get_display_value() == '$0'

    # -------------------------------------------------------------------------
    # Tests for __rich__
    # -------------------------------------------------------------------------

    def test_rich_returns_tree(self, sample_statement_item):
        """__rich__ should return a Rich Tree object."""
        from rich.tree import Tree
        result = sample_statement_item.__rich__()
        assert isinstance(result, Tree)

    def test_rich_abstract_styling(self, abstract_statement_item):
        """Abstract items should have bold cyan styling."""
        result = abstract_statement_item.__rich__()
        # Just verify it doesn't raise
        assert result is not None

    def test_rich_total_styling(self, total_statement_item):
        """Total items should have bold yellow styling."""
        result = total_statement_item.__rich__()
        assert result is not None

    def test_rich_with_children(self, hierarchical_items):
        """Items with children should include them in the tree."""
        parent, _, _ = hierarchical_items
        result = parent.__rich__()
        # The tree should have children
        assert result is not None

    def test_repr_uses_rich(self, sample_statement_item):
        """__repr__ should use rich formatting."""
        result = repr(sample_statement_item)
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# Tests for StructuredStatement
# =============================================================================

class TestStructuredStatement:
    """Tests for the StructuredStatement dataclass."""

    @pytest.fixture
    def sample_statement(self, hierarchical_items):
        """Create a sample structured statement."""
        parent, _, _ = hierarchical_items
        return StructuredStatement(
            statement_type='IncomeStatement',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=date(2024, 12, 31),
            items=[parent],
            company_name='Test Corp',
            cik='0001234567',
            canonical_coverage=0.85,
            facts_used=10,
            facts_total=15
        )

    def test_structured_statement_creation(self, sample_statement):
        """Basic creation test."""
        assert sample_statement.statement_type == 'IncomeStatement'
        assert sample_statement.fiscal_year == 2024
        assert sample_statement.fiscal_period == 'FY'
        assert sample_statement.company_name == 'Test Corp'
        assert sample_statement.cik == '0001234567'
        assert sample_statement.canonical_coverage == 0.85

    def test_to_dict(self, sample_statement):
        """Test conversion to dictionary."""
        result = sample_statement.to_dict()

        assert result['statement_type'] == 'IncomeStatement'
        assert result['fiscal_year'] == 2024
        assert result['fiscal_period'] == 'FY'
        assert result['period_end'] == '2024-12-31'
        assert result['company_name'] == 'Test Corp'
        assert result['cik'] == '0001234567'
        assert result['canonical_coverage'] == 0.85
        assert result['facts_used'] == 10
        assert result['facts_total'] == 15
        assert len(result['items']) == 1

    def test_to_dict_with_none_period_end(self, hierarchical_items):
        """Test to_dict handles None period_end."""
        parent, _, _ = hierarchical_items
        statement = StructuredStatement(
            statement_type='BalanceSheet',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[parent]
        )
        result = statement.to_dict()
        assert result['period_end'] is None

    def test_flatten_items(self, sample_statement):
        """Test flattening hierarchical items."""
        flat = sample_statement._flatten_items()

        # Should include parent and both children
        assert len(flat) == 3
        concepts = [item.concept for item in flat]
        assert 'Revenue' in concepts
        assert 'ProductRevenue' in concepts
        assert 'ServiceRevenue' in concepts

    def test_flatten_items_empty(self):
        """Test flattening empty items list."""
        statement = StructuredStatement(
            statement_type='IncomeStatement',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[]
        )
        flat = statement._flatten_items()
        assert flat == []

    def test_get_hierarchical_display(self, sample_statement):
        """Test hierarchical text display."""
        result = sample_statement.get_hierarchical_display()

        assert isinstance(result, str)
        assert 'Total Revenue' in result
        assert 'Product Revenue' in result
        assert 'Service Revenue' in result

    def test_get_hierarchical_display_max_depth(self, hierarchical_items):
        """Test max_depth limits display."""
        parent, _, _ = hierarchical_items

        # Create nested hierarchy
        grandchild = StatementItem(
            concept='SubProduct', label='Sub Product', value=100.0,
            depth=2, parent_concept='ProductRevenue', children=[]
        )
        parent.children[0].children = [grandchild]

        statement = StructuredStatement(
            statement_type='IncomeStatement',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[parent]
        )

        # With max_depth=1, grandchild shouldn't appear
        result = statement.get_hierarchical_display(max_depth=1)
        assert 'Sub Product' not in result

    def test_rich_returns_panel(self, sample_statement):
        """__rich__ should return a Rich Panel."""
        from rich.panel import Panel
        result = sample_statement.__rich__()
        assert isinstance(result, Panel)

    def test_rich_with_no_company_name(self, hierarchical_items):
        """Test __rich__ handles missing company name."""
        parent, _, _ = hierarchical_items
        statement = StructuredStatement(
            statement_type='BalanceSheet',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=date(2024, 12, 31),
            items=[parent],
            company_name=None
        )
        result = statement.__rich__()
        assert result is not None

    def test_rich_with_period_end_only(self, hierarchical_items):
        """Test __rich__ with period_end but no fiscal period."""
        parent, _, _ = hierarchical_items
        statement = StructuredStatement(
            statement_type='BalanceSheet',
            fiscal_year=None,
            fiscal_period=None,
            period_end=date(2024, 12, 31),
            items=[parent]
        )
        result = statement.__rich__()
        assert result is not None

    def test_repr(self, sample_statement):
        """Test string representation."""
        result = repr(sample_statement)
        assert isinstance(result, str)


# =============================================================================
# Tests for StatementBuilder Helper Methods
# =============================================================================

class TestStatementBuilderHelpers:
    """Tests for StatementBuilder's internal helper methods."""

    @pytest.fixture
    def builder(self):
        """Create a StatementBuilder with mocked external data."""
        with patch('edgar.entity.statement_builder.load_canonical_structures') as mock_structures, \
             patch('edgar.entity.statement_builder.load_virtual_trees') as mock_trees:
            mock_structures.return_value = {}
            mock_trees.return_value = {}
            return StatementBuilder(cik='0001234567')

    # -------------------------------------------------------------------------
    # Tests for _filter_facts
    # -------------------------------------------------------------------------

    def test_filter_facts_by_statement_type(self, builder, sample_facts):
        """Should filter facts by statement type."""
        result = builder._filter_facts(
            sample_facts, 'IncomeStatement', None, None
        )

        assert len(result) == 3  # 2 income statement facts from 2024 + 1 from 2023
        for fact in result:
            assert fact.statement_type == 'IncomeStatement'

    def test_filter_facts_by_fiscal_year(self, builder, sample_facts):
        """Should filter facts by fiscal year."""
        result = builder._filter_facts(
            sample_facts, 'IncomeStatement', 2024, None
        )

        assert len(result) == 2
        for fact in result:
            assert fact.fiscal_year == 2024

    def test_filter_facts_by_fiscal_period(self, builder, sample_facts):
        """Should filter facts by fiscal period."""
        result = builder._filter_facts(
            sample_facts, 'IncomeStatement', 2024, 'FY'
        )

        assert len(result) == 2
        for fact in result:
            assert fact.fiscal_period == 'FY'

    def test_filter_facts_no_match(self, builder, sample_facts):
        """Should return empty list when no facts match."""
        result = builder._filter_facts(
            sample_facts, 'CashFlowStatement', 2024, 'FY'
        )
        assert result == []

    def test_filter_facts_empty_input(self, builder):
        """Should handle empty input list."""
        result = builder._filter_facts([], 'IncomeStatement', None, None)
        assert result == []

    # -------------------------------------------------------------------------
    # Tests for _create_fact_map
    # -------------------------------------------------------------------------

    def test_create_fact_map_basic(self, builder, sample_facts):
        """Should create map of concept to fact."""
        # Filter to get just income statement facts
        filtered = [f for f in sample_facts if f.statement_type == 'IncomeStatement' and f.fiscal_year == 2024]
        result = builder._create_fact_map(filtered)

        assert 'Revenue' in result
        assert 'CostOfRevenue' in result
        assert len(result) == 2

    def test_create_fact_map_strips_namespace(self, builder):
        """Should strip namespace prefix from concept names."""
        facts = [
            FinancialFact(
                concept='us-gaap:Revenue',
                taxonomy='us-gaap',
                label='Revenue',
                value=100,
                numeric_value=100.0,
                unit='USD',
                filing_date=date(2024, 1, 1)
            )
        ]
        result = builder._create_fact_map(facts)

        assert 'Revenue' in result
        assert 'us-gaap:Revenue' not in result

    def test_create_fact_map_keeps_recent_duplicate(self, builder):
        """Should keep the most recent fact for duplicates."""
        facts = [
            FinancialFact(
                concept='Revenue',
                taxonomy='us-gaap',
                label='Revenue',
                value=100,
                numeric_value=100.0,
                unit='USD',
                filing_date=date(2024, 1, 1)
            ),
            FinancialFact(
                concept='Revenue',
                taxonomy='us-gaap',
                label='Revenue',
                value=200,
                numeric_value=200.0,
                unit='USD',
                filing_date=date(2024, 6, 1)  # More recent
            )
        ]
        result = builder._create_fact_map(facts)

        assert result['Revenue'].numeric_value == 200.0

    def test_create_fact_map_empty_input(self, builder):
        """Should return empty dict for empty input."""
        result = builder._create_fact_map([])
        assert result == {}

    # -------------------------------------------------------------------------
    # Tests for _get_period_end
    # -------------------------------------------------------------------------

    def test_get_period_end_returns_first_available(self, builder, sample_facts):
        """Should return first available period_end."""
        result = builder._get_period_end(sample_facts)
        assert result == date(2024, 12, 31)

    def test_get_period_end_with_none(self, builder):
        """Should return None if no facts have period_end."""
        facts = [
            FinancialFact(
                concept='Test',
                taxonomy='us-gaap',
                label='Test',
                value=100,
                numeric_value=100.0,
                unit='USD',
                period_end=None,
                filing_date=date(2024, 1, 1)
            )
        ]
        result = builder._get_period_end(facts)
        assert result is None

    def test_get_period_end_empty_list(self, builder):
        """Should return None for empty list."""
        result = builder._get_period_end([])
        assert result is None

    # -------------------------------------------------------------------------
    # Tests for _calculate_total
    # -------------------------------------------------------------------------

    def test_calculate_total_from_children(self, builder):
        """Should sum non-abstract children values."""
        children = [
            StatementItem(concept='A', label='A', value=100.0, depth=1, parent_concept='Parent'),
            StatementItem(concept='B', label='B', value=200.0, depth=1, parent_concept='Parent'),
            StatementItem(concept='C', label='C', value=300.0, depth=1, parent_concept='Parent'),
        ]
        result = builder._calculate_total(children)
        assert result == 600.0

    def test_calculate_total_skips_abstract(self, builder):
        """Should skip abstract items in total calculation."""
        children = [
            StatementItem(concept='A', label='A', value=100.0, depth=1, parent_concept='Parent'),
            StatementItem(concept='B', label='B', value=None, depth=1, parent_concept='Parent', is_abstract=True),
            StatementItem(concept='C', label='C', value=200.0, depth=1, parent_concept='Parent'),
        ]
        result = builder._calculate_total(children)
        assert result == 300.0

    def test_calculate_total_skips_none_values(self, builder):
        """Should skip items with None values."""
        children = [
            StatementItem(concept='A', label='A', value=100.0, depth=1, parent_concept='Parent'),
            StatementItem(concept='B', label='B', value=None, depth=1, parent_concept='Parent'),
        ]
        result = builder._calculate_total(children)
        assert result == 100.0

    def test_calculate_total_returns_none_when_no_values(self, builder):
        """Should return None when no children have values."""
        children = [
            StatementItem(concept='A', label='A', value=None, depth=1, parent_concept='Parent'),
            StatementItem(concept='B', label='B', value=None, depth=1, parent_concept='Parent'),
        ]
        result = builder._calculate_total(children)
        assert result is None

    def test_calculate_total_empty_children(self, builder):
        """Should return None for empty children list."""
        result = builder._calculate_total([])
        assert result is None

    # -------------------------------------------------------------------------
    # Tests for _find_unmatched_facts
    # -------------------------------------------------------------------------

    def test_find_unmatched_facts(self, builder):
        """Should find facts not in canonical structure."""
        fact_map = {
            'Revenue': MagicMock(),
            'CustomConcept': MagicMock(),
            'Assets': MagicMock()
        }
        virtual_tree = {
            'nodes': {
                'Revenue': {},
                'CostOfRevenue': {},
                'Assets': {}
            }
        }

        result = builder._find_unmatched_facts(fact_map, virtual_tree)

        assert 'CustomConcept' in result
        assert 'Revenue' not in result
        assert 'Assets' not in result

    def test_find_unmatched_facts_all_matched(self, builder):
        """Should return empty dict when all facts match."""
        fact_map = {'Revenue': MagicMock(), 'Assets': MagicMock()}
        virtual_tree = {'nodes': {'Revenue': {}, 'Assets': {}}}

        result = builder._find_unmatched_facts(fact_map, virtual_tree)
        assert result == {}

    def test_find_unmatched_facts_empty_tree(self, builder):
        """Should return all facts when tree is empty."""
        fact_map = {'Revenue': MagicMock(), 'Assets': MagicMock()}
        virtual_tree = {'nodes': {}}

        result = builder._find_unmatched_facts(fact_map, virtual_tree)
        assert len(result) == 2

    # -------------------------------------------------------------------------
    # Tests for _create_items_from_facts
    # -------------------------------------------------------------------------

    def test_create_items_from_facts(self, builder, sample_financial_fact):
        """Should create statement items from facts."""
        facts = {'Revenue': sample_financial_fact}
        result = builder._create_items_from_facts(facts)

        assert len(result) == 1
        item = result[0]
        assert item.concept == 'Revenue'
        assert item.label == 'Total Revenue'
        assert item.value == 1_000_000_000.0
        assert item.depth == 1  # Default depth
        assert item.confidence == 0.7  # Lower confidence for unmatched
        assert item.source == 'fact'
        assert item.fact == sample_financial_fact

    def test_create_items_from_facts_empty(self, builder):
        """Should return empty list for empty input."""
        result = builder._create_items_from_facts({})
        assert result == []

    # -------------------------------------------------------------------------
    # Tests for _calculate_coverage
    # -------------------------------------------------------------------------

    def test_calculate_coverage(self, builder):
        """Should calculate percentage of matched concepts."""
        builder.virtual_trees = {
            'IncomeStatement': {
                'nodes': {
                    'Revenue': {},
                    'CostOfRevenue': {},
                    'GrossProfit': {},
                    'NetIncome': {}
                }
            }
        }
        fact_map = {'Revenue': MagicMock(), 'CostOfRevenue': MagicMock()}

        result = builder._calculate_coverage(fact_map, 'IncomeStatement')
        assert result == 0.5  # 2 out of 4 concepts matched

    def test_calculate_coverage_unknown_statement_type(self, builder):
        """Should return 0 for unknown statement type."""
        builder.virtual_trees = {}
        result = builder._calculate_coverage({}, 'UnknownType')
        assert result == 0.0

    def test_calculate_coverage_empty_nodes(self, builder):
        """Should return 0 when no canonical nodes."""
        builder.virtual_trees = {'IncomeStatement': {'nodes': {}}}
        result = builder._calculate_coverage({'Revenue': MagicMock()}, 'IncomeStatement')
        assert result == 0.0

    def test_calculate_coverage_full_match(self, builder):
        """Should return 1.0 for full coverage."""
        builder.virtual_trees = {
            'IncomeStatement': {
                'nodes': {'Revenue': {}, 'CostOfRevenue': {}}
            }
        }
        fact_map = {'Revenue': MagicMock(), 'CostOfRevenue': MagicMock()}

        result = builder._calculate_coverage(fact_map, 'IncomeStatement')
        assert result == 1.0


# =============================================================================
# Tests for _build_from_facts
# =============================================================================

class TestBuildFromFacts:
    """Tests for building statements directly from facts."""

    @pytest.fixture
    def builder(self):
        """Create a StatementBuilder with mocked external data."""
        with patch('edgar.entity.statement_builder.load_canonical_structures') as mock_structures, \
             patch('edgar.entity.statement_builder.load_virtual_trees') as mock_trees:
            mock_structures.return_value = {}
            mock_trees.return_value = {}
            return StatementBuilder(cik='0001234567')

    def test_build_from_facts_basic(self, builder):
        """Should build items from facts without canonical structure."""
        facts = {
            'Revenue': FinancialFact(
                concept='Revenue',
                taxonomy='us-gaap',
                label='Revenue',
                value=1000,
                numeric_value=1000.0,
                unit='USD',
                filing_date=date(2024, 1, 1),
                parent_concept=None
            ),
            'CostOfRevenue': FinancialFact(
                concept='CostOfRevenue',
                taxonomy='us-gaap',
                label='Cost of Revenue',
                value=600,
                numeric_value=600.0,
                unit='USD',
                filing_date=date(2024, 1, 1),
                parent_concept=None
            )
        }

        result = builder._build_from_facts(facts)

        assert len(result) == 2
        concepts = [item.concept for item in result]
        assert 'Revenue' in concepts
        assert 'CostOfRevenue' in concepts

    def test_build_from_facts_with_hierarchy(self, builder):
        """Should build hierarchical items from parent relationships."""
        facts = {
            'Revenue': FinancialFact(
                concept='Revenue',
                taxonomy='us-gaap',
                label='Revenue',
                value=1000,
                numeric_value=1000.0,
                unit='USD',
                filing_date=date(2024, 1, 1),
                parent_concept=None
            ),
            'ProductRevenue': FinancialFact(
                concept='ProductRevenue',
                taxonomy='us-gaap',
                label='Product Revenue',
                value=600,
                numeric_value=600.0,
                unit='USD',
                filing_date=date(2024, 1, 1),
                parent_concept='Revenue'
            )
        }

        result = builder._build_from_facts(facts)

        # Should have 1 root with 1 child
        assert len(result) == 1
        assert result[0].concept == 'Revenue'
        assert len(result[0].children) == 1
        assert result[0].children[0].concept == 'ProductRevenue'

    def test_build_from_facts_empty(self, builder):
        """Should return empty list for empty input."""
        result = builder._build_from_facts({})
        assert result == []


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for statement_builder module."""

    def test_statement_item_with_very_large_value(self):
        """Test formatting of very large values."""
        item = StatementItem(
            concept='Test', label='Test', value=999_999_999_999.0,
            depth=0, parent_concept=None
        )
        display = item.get_display_value()
        assert 'B' in display

    def test_statement_item_with_fractional_value(self):
        """Test formatting of fractional values."""
        item = StatementItem(
            concept='Test', label='Test', value=0.5,
            depth=0, parent_concept=None
        )
        display = item.get_display_value()
        assert '$' in display

    def test_structured_statement_empty_items(self):
        """Test statement with no items."""
        statement = StructuredStatement(
            statement_type='IncomeStatement',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[]
        )

        result = statement.to_dict()
        assert result['items'] == []

        flat = statement._flatten_items()
        assert flat == []

    def test_deeply_nested_hierarchy(self):
        """Test deeply nested item hierarchy."""
        # Create 5 levels of nesting
        deepest = StatementItem(
            concept='Level5', label='Level 5', value=100.0,
            depth=4, parent_concept='Level4', children=[]
        )
        level4 = StatementItem(
            concept='Level4', label='Level 4', value=None,
            depth=3, parent_concept='Level3', children=[deepest]
        )
        level3 = StatementItem(
            concept='Level3', label='Level 3', value=None,
            depth=2, parent_concept='Level2', children=[level4]
        )
        level2 = StatementItem(
            concept='Level2', label='Level 2', value=None,
            depth=1, parent_concept='Level1', children=[level3]
        )
        level1 = StatementItem(
            concept='Level1', label='Level 1', value=None,
            depth=0, parent_concept=None, children=[level2]
        )

        statement = StructuredStatement(
            statement_type='Test',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[level1]
        )

        flat = statement._flatten_items()
        assert len(flat) == 5

        # to_dict should serialize all levels
        result = statement.to_dict()
        assert result['items'][0]['children'][0]['children'][0]['children'][0]['children'][0]['concept'] == 'Level5'

    def test_low_confidence_items_display(self):
        """Test display of low confidence items."""
        item = StatementItem(
            concept='Test', label='Test', value=1000.0,
            depth=0, parent_concept=None,
            confidence=0.5  # Low confidence
        )

        # Should still render without error
        result = item.__rich__()
        assert result is not None

    def test_statement_with_low_confidence_items_in_flatten(self):
        """Test counting low confidence items."""
        low_conf = StatementItem(
            concept='LowConf', label='Low Confidence', value=100.0,
            depth=0, parent_concept=None, confidence=0.5
        )
        high_conf = StatementItem(
            concept='HighConf', label='High Confidence', value=200.0,
            depth=0, parent_concept=None, confidence=1.0
        )

        statement = StructuredStatement(
            statement_type='Test',
            fiscal_year=2024,
            fiscal_period='FY',
            period_end=None,
            items=[low_conf, high_conf]
        )

        flat = statement._flatten_items()
        low_conf_count = sum(1 for item in flat if not item.is_abstract and item.confidence < 0.8)
        assert low_conf_count == 1
