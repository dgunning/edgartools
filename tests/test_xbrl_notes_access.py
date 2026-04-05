"""
Tests for XBRL notes/disclosures convenience methods.

Verifies that xbrl.notes(), xbrl.disclosures(), xbrl.list_tables(),
xbrl.get_table(), and xbrl.get_disclosure() correctly delegate to
the Statements class.
"""
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


@pytest.fixture
def mock_xbrl():
    """Create a mock XBRL object with proper initialization."""
    from edgar.xbrl.xbrl import XBRL
    xbrl = XBRL()
    # Set up presentation_trees for get_disclosure tests
    xbrl.parser.presentation_roles = {}
    xbrl.parser.presentation_trees = {
        'http://company.com/role/IncomeStatement': MagicMock(),
        'http://company.com/role/DebtDisclosure': MagicMock(),
        'http://company.com/role/RevenueRecognition': MagicMock(),
    }
    return xbrl


@pytest.fixture
def mock_statements():
    """Create a mock Statements object."""
    return MagicMock()


class TestNotes:
    """Test xbrl.notes() delegates to Statements.notes()."""

    def test_notes_delegates_to_statements(self, mock_xbrl, mock_statements):
        mock_notes = [MagicMock(), MagicMock()]
        mock_statements.notes.return_value = mock_notes
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.notes()
        assert result == mock_notes
        mock_statements.notes.assert_called_once()

    def test_notes_returns_list(self, mock_xbrl, mock_statements):
        mock_statements.notes.return_value = []
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.notes()
        assert isinstance(result, list)


class TestDisclosures:
    """Test xbrl.disclosures() delegates to Statements.disclosures()."""

    def test_disclosures_delegates_to_statements(self, mock_xbrl, mock_statements):
        mock_disclosures = [MagicMock(), MagicMock(), MagicMock()]
        mock_statements.disclosures.return_value = mock_disclosures
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.disclosures()
        assert result == mock_disclosures
        mock_statements.disclosures.assert_called_once()

    def test_disclosures_returns_list(self, mock_xbrl, mock_statements):
        mock_statements.disclosures.return_value = []
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.disclosures()
        assert isinstance(result, list)


class TestListTables:
    """Test xbrl.list_tables() delegates to Statements.get_statements_by_category()."""

    def test_list_tables_returns_categorized_dict(self, mock_xbrl, mock_statements):
        mock_categories = {
            'statement': [{'definition': 'Income Statement', 'index': 0}],
            'note': [{'definition': 'Note 3 - Debt', 'index': 5}],
            'disclosure': [{'definition': 'Revenue Recognition', 'index': 10}],
            'document': [],
            'other': [],
        }
        mock_statements.get_statements_by_category.return_value = mock_categories
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.list_tables()
        assert 'statement' in result
        assert 'note' in result
        assert 'disclosure' in result
        assert len(result['statement']) == 1
        assert len(result['note']) == 1

    def test_list_tables_has_all_category_keys(self, mock_xbrl, mock_statements):
        mock_categories = {
            'statement': [], 'note': [], 'disclosure': [],
            'document': [], 'other': [],
        }
        mock_statements.get_statements_by_category.return_value = mock_categories
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.list_tables()
        assert set(result.keys()) == {'statement', 'note', 'disclosure', 'document', 'other'}


class TestGetTable:
    """Test xbrl.get_table() delegates to Statements.get()."""

    def test_get_table_delegates_to_statements_get(self, mock_xbrl, mock_statements):
        mock_statement = MagicMock()
        mock_statements.get.return_value = mock_statement
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.get_table("debt")
        assert result == mock_statement

    def test_get_table_returns_none_for_no_match(self, mock_xbrl, mock_statements):
        mock_statements.get.return_value = None
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            result = mock_xbrl.get_table("nonexistent table")
        assert result is None

    def test_get_table_passes_name_through(self, mock_xbrl, mock_statements):
        mock_statements.get.return_value = None
        with patch.object(type(mock_xbrl), 'statements', new_callable=PropertyMock, return_value=mock_statements):
            mock_xbrl.get_table("revenue recognition")
        mock_statements.get.assert_called_once_with("revenue recognition")


class TestGetDisclosure:
    """Test xbrl.get_disclosure() creates Statement from role URI."""

    def test_get_disclosure_valid_role(self, mock_xbrl):
        result = mock_xbrl.get_disclosure('http://company.com/role/DebtDisclosure')
        assert result is not None

    def test_get_disclosure_invalid_role_returns_none(self, mock_xbrl):
        result = mock_xbrl.get_disclosure('http://company.com/role/NonexistentRole')
        assert result is None

    def test_get_disclosure_creates_statement_with_role(self, mock_xbrl):
        with patch('edgar.xbrl.statements.Statement') as MockStatement:
            mock_xbrl.get_disclosure('http://company.com/role/DebtDisclosure')
            MockStatement.assert_called_once_with(mock_xbrl, 'http://company.com/role/DebtDisclosure')
