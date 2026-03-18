"""
Tests for statement-to-note drill-down feature.

Verifies that Statement.__getitem__ returns StatementLineItem objects
with .note/.notes properties that resolve via the concept→notes reverse index.
"""
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from edgar.xbrl.notes import (
    Note, Notes,
    _build_concept_to_notes_index,
    _get_concept_to_notes_index,
    get_notes_for_concept,
)
from edgar.xbrl.rendering import RenderedStatement, StatementHeader, StatementRow, StatementCell
from edgar.xbrl.statements import StatementLineItem


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_xbrl():
    """XBRL instance with presentation trees for two roles."""
    from edgar.xbrl.xbrl import XBRL
    xbrl = XBRL()

    # Stub presentation trees with concept IDs
    debt_tree = MagicMock()
    debt_tree.all_nodes = {
        'us-gaap_LongTermDebtNoncurrent': MagicMock(),
        'us-gaap_DebtDisclosureAbstract': MagicMock(),  # structural, should be filtered
        'us-gaap_ShortTermBorrowings': MagicMock(),
    }

    revenue_tree = MagicMock()
    revenue_tree.all_nodes = {
        'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax': MagicMock(),
        'us-gaap_RevenueRecognitionAbstract': MagicMock(),  # structural
    }

    bs_tree = MagicMock()
    bs_tree.all_nodes = {
        'us-gaap_LongTermDebtNoncurrent': MagicMock(),
        'us-gaap_Assets': MagicMock(),
        'us-gaap_Goodwill': MagicMock(),
    }

    xbrl.parser.presentation_trees = {
        'http://company.com/role/DebtDisclosure': debt_tree,
        'http://company.com/role/RevenueRecognition': revenue_tree,
        'http://company.com/role/BalanceSheet': bs_tree,
    }

    # Element catalog for labels
    label_entry = MagicMock()
    label_entry.labels = {'http://www.xbrl.org/2003/role/label': 'Long-term Debt'}
    xbrl.parser.element_catalog = {
        'us-gaap_LongTermDebtNoncurrent': label_entry,
    }

    return xbrl


@pytest.fixture
def debt_note(mock_xbrl):
    """A Note covering the Debt role."""
    return Note(
        number=5,
        title='Debt',
        short_name='Debt',
        role='http://company.com/role/DebtDisclosure',
        statement=None,
        tables=[],
        policies=[],
        details=[],
        menu_category='Notes',
        xbrl=mock_xbrl,
    )


@pytest.fixture
def revenue_note(mock_xbrl):
    """A Note covering the Revenue role."""
    return Note(
        number=3,
        title='Revenue Recognition',
        short_name='Revenue Recognition',
        role='http://company.com/role/RevenueRecognition',
        statement=None,
        tables=[],
        policies=[],
        details=[],
        menu_category='Notes',
        xbrl=mock_xbrl,
    )


@pytest.fixture
def notes_collection(debt_note, revenue_note):
    return Notes([revenue_note, debt_note])


# ── Reverse index tests ──────────────────────────────────────────────────────

class TestReverseIndex:

    def test_build_index_maps_concepts_to_notes(self, notes_collection, mock_xbrl):
        index = _build_concept_to_notes_index(notes_collection, mock_xbrl)
        # LongTermDebtNoncurrent should map to debt_note
        assert 'us-gaap_LongTermDebtNoncurrent' in index
        assert any(n.short_name == 'Debt' for n in index['us-gaap_LongTermDebtNoncurrent'])

    def test_structural_concepts_excluded(self, notes_collection, mock_xbrl):
        index = _build_concept_to_notes_index(notes_collection, mock_xbrl)
        # Abstract concepts should not appear
        assert 'us-gaap_DebtDisclosureAbstract' not in index
        assert 'us-gaap_RevenueRecognitionAbstract' not in index

    def test_index_cached_on_xbrl(self, notes_collection, mock_xbrl):
        mock_xbrl._notes_cache = notes_collection
        idx1 = _get_concept_to_notes_index(mock_xbrl)
        idx2 = _get_concept_to_notes_index(mock_xbrl)
        assert idx1 is idx2  # Same object, cached

    def test_get_notes_for_concept_returns_list(self, notes_collection, mock_xbrl):
        mock_xbrl._notes_cache = notes_collection
        notes = get_notes_for_concept('us-gaap_LongTermDebtNoncurrent', mock_xbrl)
        assert isinstance(notes, list)
        assert len(notes) >= 1

    def test_get_notes_for_unknown_concept(self, notes_collection, mock_xbrl):
        mock_xbrl._notes_cache = notes_collection
        notes = get_notes_for_concept('us-gaap_NonexistentConcept', mock_xbrl)
        assert notes == []


# ── StatementLineItem tests ──────────────────────────────────────────────────

class TestStatementLineItem:

    def test_label_and_concept(self):
        row = StatementRow(
            label='Long-term debt',
            level=1,
            cells=[],
            metadata={'concept': 'us-gaap_LongTermDebtNoncurrent'},
        )
        xbrl = MagicMock()
        item = StatementLineItem(row, xbrl)
        assert item.label == 'Long-term debt'
        assert item.concept == 'us-gaap_LongTermDebtNoncurrent'

    def test_values_from_cells(self):
        row = StatementRow(
            label='Revenue',
            level=0,
            cells=[
                StatementCell(value=394328000000),
                StatementCell(value=365817000000),
            ],
            metadata={'concept': 'us-gaap_Revenue'},
        )
        item = StatementLineItem(row, MagicMock())
        vals = item.values
        assert vals == [394328000000, 365817000000]

    def test_note_returns_none_without_xbrl(self):
        row = StatementRow(label='X', level=0, metadata={'concept': 'foo'})
        item = StatementLineItem(row, None)
        assert item.note is None
        assert item.notes == []

    def test_repr(self):
        row = StatementRow(
            label='Goodwill',
            level=0,
            metadata={'concept': 'us-gaap_Goodwill'},
        )
        item = StatementLineItem(row, MagicMock())
        assert 'Goodwill' in repr(item)
        assert 'us-gaap_Goodwill' in repr(item)

    def test_note_drilldown(self, notes_collection, mock_xbrl):
        """End-to-end: line item → note lookup via reverse index."""
        mock_xbrl._notes_cache = notes_collection
        row = StatementRow(
            label='Long-term debt',
            level=1,
            metadata={'concept': 'us-gaap_LongTermDebtNoncurrent'},
        )
        item = StatementLineItem(row, mock_xbrl)
        note = item.note
        assert note is not None
        assert note.short_name == 'Debt'

    def test_notes_returns_all_matches(self, notes_collection, mock_xbrl):
        mock_xbrl._notes_cache = notes_collection
        row = StatementRow(
            label='Long-term debt',
            level=1,
            metadata={'concept': 'us-gaap_LongTermDebtNoncurrent'},
        )
        item = StatementLineItem(row, mock_xbrl)
        all_notes = item.notes
        assert isinstance(all_notes, list)
        assert len(all_notes) >= 1

    def test_uses_weakref(self, mock_xbrl):
        """StatementLineItem uses weakref to avoid preventing XBRL GC."""
        row = StatementRow(label='X', level=0, metadata={'concept': 'foo'})
        item = StatementLineItem(row, mock_xbrl)
        assert item._xbrl is mock_xbrl
        # weakref slot is set
        assert item._xbrl_ref is not None


# ── RenderedStatement.__getitem__ tests ───────────────────────────────────────

class TestRenderedStatementGetItem:

    def _make_rendered(self, rows):
        return RenderedStatement(
            title='Balance Sheet',
            header=StatementHeader(),
            rows=rows,
        )

    def test_exact_match(self):
        rows = [
            StatementRow(label='Total Assets', level=0),
            StatementRow(label='Total Liabilities', level=0),
        ]
        rs = self._make_rendered(rows)
        assert rs['Total Assets'] is rows[0]

    def test_case_insensitive(self):
        rows = [StatementRow(label='Long-term Debt', level=1)]
        rs = self._make_rendered(rows)
        assert rs['long-term debt'] is rows[0]

    def test_substring_fallback(self):
        rows = [StatementRow(label='Long-term debt, net of unamortized discount', level=1)]
        rs = self._make_rendered(rows)
        assert rs['Long-term debt'] is rows[0]

    def test_not_found_returns_none(self):
        rows = [StatementRow(label='Cash', level=0)]
        rs = self._make_rendered(rows)
        assert rs['Nonexistent'] is None

    def test_empty_rows(self):
        rs = self._make_rendered([])
        assert rs['Anything'] is None


# ── Notes.from_xbrl caching ──────────────────────────────────────────────────

class TestNotesCaching:

    def test_from_xbrl_sets_cache(self, mock_xbrl):
        """Notes.from_xbrl should populate xbrl._notes_cache."""
        assert mock_xbrl._notes_cache is None
        notes = Notes.from_xbrl(mock_xbrl)
        assert mock_xbrl._notes_cache is notes


# ── Statement.report property ─────────────────────────────────────────────────

class TestStatementReport:

    def test_report_defaults_to_none(self):
        """Statement.report is None when not built from FilingSummary."""
        from edgar.xbrl.xbrl import XBRL
        xbrl = XBRL()
        from edgar.xbrl.statements import Statement
        stmt = Statement(xbrl, 'http://example.com/role/BalanceSheet')
        assert stmt.report is None

    def test_report_set_by_notes_builder(self):
        """Statement._report is set when built from FilingSummary."""
        from unittest.mock import MagicMock
        from edgar.xbrl.statements import Statement
        from edgar.xbrl.xbrl import XBRL
        xbrl = XBRL()
        stmt = Statement(xbrl, 'http://example.com/role/DebtTables')
        mock_report = MagicMock()
        stmt._report = mock_report
        assert stmt.report is mock_report
