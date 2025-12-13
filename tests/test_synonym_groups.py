"""
Tests for the Unified Synonym Management System.

Tests cover:
- SynonymGroup dataclass functionality
- SynonymGroups manager operations
- Reverse lookup (tag identification)
- User-defined group registration
- JSON import/export
"""

import json
import pytest
from pathlib import Path

from edgar.standardization import (
    SynonymGroup,
    SynonymGroups,
    ConceptInfo,
    get_synonym_groups,
)
from edgar.standardization.synonym_groups import reset_synonym_groups


class TestSynonymGroup:
    """Tests for the SynonymGroup dataclass."""

    def test_basic_creation(self):
        """Test basic SynonymGroup creation."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['Revenues', 'Revenue', 'SalesRevenueNet'],
            description='Total revenue',
            category='income_statement'
        )
        assert group.name == 'revenue'
        assert len(group.synonyms) == 3
        assert group.description == 'Total revenue'
        assert group.category == 'income_statement'

    def test_name_normalization(self):
        """Test that names are normalized to lowercase with underscores."""
        group = SynonymGroup(name='Net Income', synonyms=['NetIncome'])
        assert group.name == 'net_income'

        group2 = SynonymGroup(name='Operating-Income', synonyms=['OperatingIncome'])
        assert group2.name == 'operating_income'

    def test_namespace_stripping(self):
        """Test that namespace prefixes are stripped from synonyms."""
        group = SynonymGroup(
            name='revenue',
            synonyms=[
                'us-gaap:Revenues',
                'us-gaap:Revenue',
                'Revenues',  # Already without namespace
            ]
        )
        # All should have namespaces stripped
        assert 'Revenues' in group.synonyms
        assert 'Revenue' in group.synonyms
        assert 'us-gaap:Revenues' not in group.synonyms

    def test_underscore_namespace_stripping(self):
        """Test stripping of underscore-format namespaces (us-gaap_Revenue)."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['us-gaap_Revenues', 'usgaap_Revenue']
        )
        # The first one should be stripped (us-gaap), second should not match pattern
        assert 'Revenues' in group.synonyms

    def test_contains_tag(self):
        """Test contains_tag method."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['Revenues', 'Revenue']
        )
        assert group.contains_tag('Revenues')
        assert group.contains_tag('us-gaap:Revenues')
        assert not group.contains_tag('NetIncome')

    def test_get_tags_with_namespace(self):
        """Test getting tags with namespace prefix."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['Revenues', 'Revenue'],
            namespace='us-gaap'
        )
        tags = group.get_tags_with_namespace()
        assert 'us-gaap:Revenues' in tags
        assert 'us-gaap:Revenue' in tags

        # Custom namespace
        tags_custom = group.get_tags_with_namespace('custom')
        assert 'custom:Revenues' in tags_custom

    def test_to_dict(self):
        """Test serialization to dictionary."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['Revenues'],
            description='Test',
            category='income_statement'
        )
        d = group.to_dict()
        assert d['name'] == 'revenue'
        assert d['synonyms'] == ['Revenues']
        assert d['description'] == 'Test'
        assert d['category'] == 'income_statement'

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'name': 'revenue',
            'synonyms': ['Revenues', 'Revenue'],
            'description': 'Test revenue',
            'category': 'income_statement'
        }
        group = SynonymGroup.from_dict(data)
        assert group.name == 'revenue'
        assert len(group.synonyms) == 2
        assert group.description == 'Test revenue'


class TestSynonymGroups:
    """Tests for the SynonymGroups manager."""

    def test_builtin_groups_loaded(self):
        """Test that built-in groups are loaded by default."""
        synonyms = SynonymGroups()
        assert len(synonyms) > 40  # Should have 40+ built-in groups
        assert 'revenue' in synonyms
        assert 'net_income' in synonyms
        assert 'capex' in synonyms

    def test_no_builtin_groups(self):
        """Test creating instance without built-in groups."""
        synonyms = SynonymGroups(load_builtin=False)
        assert len(synonyms) == 0
        assert 'revenue' not in synonyms

    def test_get_group(self):
        """Test getting a group by name."""
        synonyms = SynonymGroups()
        revenue = synonyms.get_group('revenue')
        assert revenue is not None
        assert revenue.name == 'revenue'
        assert len(revenue.synonyms) > 0

    def test_get_group_normalization(self):
        """Test that get_group normalizes the name."""
        synonyms = SynonymGroups()
        # All these should find the same group
        assert synonyms.get_group('revenue') is not None
        assert synonyms.get_group('Revenue') is not None
        assert synonyms.get_group('net_income') is not None
        assert synonyms.get_group('net-income') is not None
        assert synonyms.get_group('Net Income') is not None

    def test_get_group_not_found(self):
        """Test that get_group returns None for unknown groups."""
        synonyms = SynonymGroups()
        assert synonyms.get_group('nonexistent') is None

    def test_get_synonyms(self):
        """Test get_synonyms convenience method."""
        synonyms = SynonymGroups()
        tags = synonyms.get_synonyms('revenue')
        assert len(tags) > 0
        assert 'RevenueFromContractWithCustomerExcludingAssessedTax' in tags or 'Revenues' in tags

    def test_get_synonyms_not_found(self):
        """Test get_synonyms returns empty list for unknown groups."""
        synonyms = SynonymGroups()
        tags = synonyms.get_synonyms('nonexistent')
        assert tags == []

    def test_identify_concept(self):
        """Test reverse lookup of tags to concepts."""
        synonyms = SynonymGroups()

        # Test basic lookup
        info = synonyms.identify_concept('NetIncomeLoss')
        assert info is not None
        assert info.name == 'net_income'
        assert info.tag == 'NetIncomeLoss'

        # Test with namespace prefix
        info2 = synonyms.identify_concept('us-gaap:Revenues')
        assert info2 is not None
        assert info2.name == 'revenue'

    def test_identify_concept_not_found(self):
        """Test identify_concept returns None for unknown tags."""
        synonyms = SynonymGroups()
        info = synonyms.identify_concept('CompletelyUnknownTag')
        assert info is None

    def test_list_groups(self):
        """Test listing all group names."""
        synonyms = SynonymGroups()
        groups = synonyms.list_groups()
        assert len(groups) > 40
        assert 'revenue' in groups
        assert 'net_income' in groups
        # Should be sorted
        assert groups == sorted(groups)

    def test_list_groups_by_category(self):
        """Test listing groups filtered by category."""
        synonyms = SynonymGroups()

        income_groups = synonyms.list_groups(category='income_statement')
        assert 'revenue' in income_groups
        assert 'net_income' in income_groups
        assert 'total_assets' not in income_groups  # Balance sheet

        balance_groups = synonyms.list_groups(category='balance_sheet')
        assert 'total_assets' in balance_groups
        assert 'revenue' not in balance_groups

        cash_flow_groups = synonyms.list_groups(category='cash_flow')
        assert 'capex' in cash_flow_groups
        assert 'operating_cash_flow' in cash_flow_groups

    def test_list_categories(self):
        """Test listing available categories."""
        synonyms = SynonymGroups()
        categories = synonyms.list_categories()
        assert 'income_statement' in categories
        assert 'balance_sheet' in categories
        assert 'cash_flow' in categories

    def test_register_group(self):
        """Test registering a custom group."""
        synonyms = SynonymGroups()
        initial_count = len(synonyms)

        group = synonyms.register_group(
            name='custom_metric',
            synonyms=['CustomTag1', 'CustomTag2'],
            description='A custom metric',
            category='metrics'
        )

        assert group.name == 'custom_metric'
        assert len(synonyms) == initial_count + 1
        assert 'custom_metric' in synonyms

        # Should be identifiable
        info = synonyms.identify_concept('CustomTag1')
        assert info is not None
        assert info.name == 'custom_metric'

    def test_register_group_override(self):
        """Test that user groups can override built-in groups."""
        synonyms = SynonymGroups()

        # Override revenue with custom tags
        synonyms.register_group(
            name='revenue',
            synonyms=['MyCustomRevenue'],
            description='Custom revenue definition'
        )

        revenue = synonyms.get_group('revenue')
        assert 'MyCustomRevenue' in revenue.synonyms

    def test_unregister_group(self):
        """Test unregistering a user-defined group."""
        synonyms = SynonymGroups()

        # Register a custom group
        synonyms.register_group(
            name='temp_group',
            synonyms=['TempTag']
        )
        assert 'temp_group' in synonyms

        # Unregister it
        result = synonyms.unregister_group('temp_group')
        assert result is True
        assert 'temp_group' not in synonyms

    def test_unregister_builtin_group_fails(self):
        """Test that built-in groups cannot be unregistered."""
        synonyms = SynonymGroups()
        result = synonyms.unregister_group('revenue')
        assert result is False
        assert 'revenue' in synonyms  # Still exists

    def test_contains(self):
        """Test __contains__ method."""
        synonyms = SynonymGroups()
        assert 'revenue' in synonyms
        assert 'nonexistent' not in synonyms

    def test_iter(self):
        """Test iteration over group names."""
        synonyms = SynonymGroups()
        names = list(synonyms)
        assert len(names) > 40
        assert 'revenue' in names

    def test_repr(self):
        """Test string representation."""
        synonyms = SynonymGroups()
        repr_str = repr(synonyms)
        assert 'SynonymGroups' in repr_str
        assert 'groups=' in repr_str


class TestSynonymGroupsIO:
    """Tests for JSON import/export functionality."""

    def test_export_user_groups_only(self, tmp_path):
        """Test exporting only user-defined groups."""
        synonyms = SynonymGroups()
        synonyms.register_group(
            name='custom1',
            synonyms=['Tag1']
        )
        synonyms.register_group(
            name='custom2',
            synonyms=['Tag2']
        )

        export_path = tmp_path / 'export.json'
        synonyms.export_to_json(export_path)

        with open(export_path) as f:
            data = json.load(f)

        assert len(data['groups']) == 2
        names = [g['name'] for g in data['groups']]
        assert 'custom1' in names
        assert 'custom2' in names
        assert 'revenue' not in names  # Built-in not exported

    def test_export_all_groups(self, tmp_path):
        """Test exporting all groups including built-in."""
        synonyms = SynonymGroups()
        synonyms.register_group(name='custom1', synonyms=['Tag1'])

        export_path = tmp_path / 'export_all.json'
        synonyms.export_to_json(export_path, include_builtin=True)

        with open(export_path) as f:
            data = json.load(f)

        assert len(data['groups']) > 40  # Built-in + custom
        names = [g['name'] for g in data['groups']]
        assert 'custom1' in names
        assert 'revenue' in names

    def test_import_groups(self, tmp_path):
        """Test importing groups from JSON."""
        # Create a JSON file
        data = {
            'version': '1.0',
            'groups': [
                {
                    'name': 'imported_group',
                    'synonyms': ['ImportedTag1', 'ImportedTag2'],
                    'description': 'Imported group',
                    'category': 'custom'
                }
            ]
        }
        import_path = tmp_path / 'import.json'
        with open(import_path, 'w') as f:
            json.dump(data, f)

        # Import
        synonyms = SynonymGroups()
        count = synonyms.import_from_json(import_path)

        assert count == 1
        assert 'imported_group' in synonyms
        group = synonyms.get_group('imported_group')
        assert 'ImportedTag1' in group.synonyms

    def test_from_file(self, tmp_path):
        """Test creating instance from file."""
        data = {
            'version': '1.0',
            'groups': [
                {
                    'name': 'custom_from_file',
                    'synonyms': ['FileTag'],
                    'description': 'From file'
                }
            ]
        }
        file_path = tmp_path / 'config.json'
        with open(file_path, 'w') as f:
            json.dump(data, f)

        synonyms = SynonymGroups.from_file(file_path)

        # Should have both built-in and file groups
        assert 'revenue' in synonyms
        assert 'custom_from_file' in synonyms


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_synonym_groups()

    def test_get_synonym_groups_singleton(self):
        """Test that get_synonym_groups returns the same instance."""
        instance1 = get_synonym_groups()
        instance2 = get_synonym_groups()
        assert instance1 is instance2

    def test_reset_singleton(self):
        """Test resetting the singleton."""
        instance1 = get_synonym_groups()
        reset_synonym_groups()
        instance2 = get_synonym_groups()
        assert instance1 is not instance2


class TestBuiltinGroups:
    """Tests for specific built-in synonym groups."""

    @pytest.fixture
    def synonyms(self):
        return SynonymGroups()

    def test_revenue_group(self, synonyms):
        """Test revenue synonym group."""
        revenue = synonyms.get_group('revenue')
        assert revenue is not None
        assert revenue.category == 'income_statement'
        # Should include common revenue tags
        tags = revenue.synonyms
        assert any('Revenue' in tag for tag in tags)

    def test_net_income_group(self, synonyms):
        """Test net income synonym group."""
        net_income = synonyms.get_group('net_income')
        assert net_income is not None
        assert 'NetIncomeLoss' in net_income.synonyms

    def test_capex_group(self, synonyms):
        """Test capital expenditure synonym group."""
        capex = synonyms.get_group('capex')
        assert capex is not None
        assert capex.category == 'cash_flow'
        assert 'PaymentsToAcquirePropertyPlantAndEquipment' in capex.synonyms

    def test_operating_lease_payments(self, synonyms):
        """Test operating lease payments group (Discussion #495)."""
        leases = synonyms.get_group('operating_lease_payments')
        assert leases is not None
        assert leases.category == 'cash_flow'
        assert 'OperatingLeasePayments' in leases.synonyms

    def test_stockholders_equity(self, synonyms):
        """Test stockholders equity group."""
        equity = synonyms.get_group('stockholders_equity')
        assert equity is not None
        assert 'StockholdersEquity' in equity.synonyms
        # Should also include alternative names
        assert any('Equity' in tag for tag in equity.synonyms)

    def test_total_assets(self, synonyms):
        """Test total assets group."""
        assets = synonyms.get_group('total_assets')
        assert assets is not None
        assert 'Assets' in assets.synonyms


class TestMultiGroupMembership:
    """Tests for multi-group membership functionality."""

    def test_identify_concepts_single_group(self):
        """Test identify_concepts returns single match for unique tags."""
        synonyms = SynonymGroups()
        infos = synonyms.identify_concepts('NetIncomeLoss')
        assert len(infos) == 1
        assert infos[0].name == 'net_income'

    def test_identify_concepts_empty_for_unknown(self):
        """Test identify_concepts returns empty list for unknown tags."""
        synonyms = SynonymGroups()
        infos = synonyms.identify_concepts('CompletelyUnknownTag')
        assert infos == []

    def test_identify_concepts_multiple_groups(self):
        """Test identify_concepts returns multiple matches when tag in multiple groups."""
        synonyms = SynonymGroups()

        # Register a custom group that uses a tag from an existing group
        synonyms.register_group(
            name='depreciation_adjustment',
            synonyms=['DepreciationAndAmortization'],  # Also in depreciation_and_amortization
            description='D&A as cash flow adjustment',
            category='cash_flow'
        )

        infos = synonyms.identify_concepts('DepreciationAndAmortization')
        assert len(infos) == 2

        # Check both groups are returned
        names = [info.name for info in infos]
        assert 'depreciation_and_amortization' in names
        assert 'depreciation_adjustment' in names

        # Check categories are different
        categories = [info.category for info in infos]
        assert 'income_statement' in categories
        assert 'cash_flow' in categories

    def test_identify_concept_returns_first_match(self):
        """Test identify_concept returns first match when tag in multiple groups."""
        synonyms = SynonymGroups()

        # Register a custom group that uses a tag from an existing group
        synonyms.register_group(
            name='depreciation_adjustment',
            synonyms=['DepreciationAndAmortization'],
            description='D&A as cash flow adjustment',
            category='cash_flow'
        )

        # identify_concept should return first (builtin comes before user-defined)
        info = synonyms.identify_concept('DepreciationAndAmortization')
        assert info is not None
        assert info.name == 'depreciation_and_amortization'  # First registered
        assert info.category == 'income_statement'

    def test_filter_by_category(self):
        """Test filtering multi-group results by category."""
        synonyms = SynonymGroups()

        # Register a custom group for cash flow context
        synonyms.register_group(
            name='depreciation_adjustment',
            synonyms=['DepreciationAndAmortization'],
            description='D&A as cash flow adjustment',
            category='cash_flow'
        )

        infos = synonyms.identify_concepts('DepreciationAndAmortization')

        # Filter to cash_flow context
        cash_flow_infos = [i for i in infos if i.category == 'cash_flow']
        assert len(cash_flow_infos) == 1
        assert cash_flow_infos[0].name == 'depreciation_adjustment'

        # Filter to income_statement context
        income_infos = [i for i in infos if i.category == 'income_statement']
        assert len(income_infos) == 1
        assert income_infos[0].name == 'depreciation_and_amortization'

    def test_unregister_removes_from_multi_group_index(self):
        """Test unregistering a group updates the multi-group index correctly."""
        synonyms = SynonymGroups()

        # Register custom group
        synonyms.register_group(
            name='custom_depr',
            synonyms=['DepreciationAndAmortization'],
            category='metrics'
        )

        # Should have 2 groups for the tag
        infos = synonyms.identify_concepts('DepreciationAndAmortization')
        assert len(infos) == 2

        # Unregister custom group
        result = synonyms.unregister_group('custom_depr')
        assert result is True

        # Should now have only 1 group
        infos = synonyms.identify_concepts('DepreciationAndAmortization')
        assert len(infos) == 1
        assert infos[0].name == 'depreciation_and_amortization'


class TestConceptInfo:
    """Tests for the ConceptInfo dataclass."""

    def test_concept_info_properties(self):
        """Test ConceptInfo property accessors."""
        group = SynonymGroup(
            name='revenue',
            synonyms=['Revenues'],
            description='Total revenue',
            category='income_statement'
        )
        info = ConceptInfo(
            name='revenue',
            tag='us-gaap:Revenues',
            group=group
        )

        assert info.name == 'revenue'
        assert info.tag == 'us-gaap:Revenues'
        assert info.synonyms == ['Revenues']
        assert info.description == 'Total revenue'
        assert info.category == 'income_statement'
