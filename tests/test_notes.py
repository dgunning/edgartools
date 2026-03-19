"""
Tests for edgar.xbrl.notes — Note and Notes classes.

Covers:
- Note construction and properties
- Notes collection: indexing, search, iteration, bool
- Notes.from_xbrl with FilingSummary (hierarchy) and fallback (XBRL-only)
- Helper functions: _extract_short_name, _is_data_concept, _compute_expands
- to_context() at both Note and Notes level
- CompanyReport.notes integration (via TenK.to_context(focus=...))
"""
import weakref
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest

from edgar.xbrl.notes import (
    Note, Notes,
    _extract_short_name, _is_data_concept, _get_concept_label,
    _collect_note_concepts, _compute_expands, _compute_expands_with_statements,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_note(number=1, title='Debt', short_name='Debt', role='http://co/role/Debt',
               tables=None, policies=None, details=None, xbrl=None, statement=None):
    """Helper to build a Note with sensible defaults."""
    return Note(
        number=number,
        title=title,
        short_name=short_name,
        role=role,
        statement=statement,
        tables=tables or [],
        policies=policies or [],
        details=details or [],
        xbrl=xbrl,
    )


def _make_notes_collection(count=5):
    """Build a Notes object with N numbered notes."""
    notes = []
    titles = [
        'Organization and Summary of Significant Accounting Policies',
        'Revenue Recognition',
        'Debt',
        'Income Taxes',
        'Share-Based Compensation',
        'Goodwill and Intangible Assets',
        'Commitments and Contingencies',
        'Earnings Per Share',
    ]
    for i in range(min(count, len(titles))):
        notes.append(_make_note(
            number=i + 1,
            title=titles[i],
            short_name=titles[i],
            role=f'http://co/role/Note{i + 1}',
        ))
    return Notes(notes, entity_name='Test Corp', form='10-K', period='2024-12-31')


# ---------------------------------------------------------------------------
# Note class
# ---------------------------------------------------------------------------

class TestNote:

    @pytest.mark.fast
    def test_basic_properties(self):
        note = _make_note(number=3, title='Debt', short_name='Debt')
        assert note.number == 3
        assert note.title == 'Debt'
        assert note.short_name == 'Debt'
        assert note.table_count == 0
        assert note.has_tables is False
        assert note.children == []

    @pytest.mark.fast
    def test_tables_policies_details_counted(self):
        tables = [Mock(), Mock()]
        policies = [Mock()]
        details = [Mock(), Mock(), Mock()]
        note = _make_note(tables=tables, policies=policies, details=details)
        assert note.table_count == 2
        assert note.has_tables is True
        assert len(note.children) == 6  # 2 + 1 + 3

    @pytest.mark.fast
    def test_text_delegates_to_statement(self):
        stmt = Mock()
        stmt.text.return_value = 'Some narrative about debt.'
        note = _make_note(statement=stmt)
        assert note.text == 'Some narrative about debt.'
        stmt.text.assert_called_once()

    @pytest.mark.fast
    def test_text_returns_none_without_statement(self):
        note = _make_note(statement=None)
        assert note.text is None

    @pytest.mark.fast
    def test_html_delegates_to_statement(self):
        stmt = Mock()
        stmt.text.return_value = '<p>Debt disclosure</p>'
        note = _make_note(statement=stmt)
        assert note.html == '<p>Debt disclosure</p>'
        stmt.text.assert_called_with(raw_html=True)

    @pytest.mark.fast
    def test_html_returns_none_without_statement(self):
        note = _make_note(statement=None)
        assert note.html is None

    @pytest.mark.fast
    def test_strong_reference_to_xbrl(self):
        """XBRL reference is stored directly (pickle-safe)."""
        xbrl = Mock()
        note = _make_note(xbrl=xbrl)
        assert note._xbrl is xbrl

    @pytest.mark.fast
    def test_no_xbrl_ref_when_none(self):
        note = _make_note(xbrl=None)
        assert note._xbrl is None

    @pytest.mark.fast
    def test_str_representation(self):
        note = _make_note(number=5, short_name='Debt')
        assert "Note(5, 'Debt')" == str(note)

    @pytest.mark.fast
    def test_str_with_tables(self):
        note = _make_note(number=5, short_name='Debt', tables=[Mock(), Mock()])
        result = str(note)
        assert 'tables=2' in result

    @pytest.mark.fast
    def test_expands_empty_without_xbrl(self):
        note = _make_note(xbrl=None)
        assert note.expands == []
        assert note.expands_concepts == []

    @pytest.mark.fast
    def test_expands_statements_empty_without_xbrl(self):
        note = _make_note(xbrl=None)
        assert note.expands_statements == []


class TestNoteToContext:

    @pytest.mark.fast
    def test_minimal_detail(self):
        tables = [Mock()]
        tables[0].render.return_value = Mock(title='Debt Maturities')
        note = _make_note(number=3, title='Debt', short_name='Debt', tables=tables)
        ctx = note.to_context(detail='minimal')
        assert 'NOTE 3: Debt' in ctx
        # Minimal should mention tables
        assert 'Tables:' in ctx or 'Maturities' in ctx

    @pytest.mark.fast
    def test_standard_detail_includes_narrative(self):
        stmt = Mock()
        stmt.text.return_value = 'The company has outstanding debt of $5 billion.'
        note = _make_note(number=3, title='Debt', short_name='Debt', statement=stmt)
        ctx = note.to_context(detail='standard')
        assert 'NOTE 3: Debt' in ctx
        assert 'NARRATIVE:' in ctx
        assert '$5 billion' in ctx

    @pytest.mark.fast
    def test_full_detail_includes_policies_and_details(self):
        stmt = Mock()
        stmt.text.return_value = 'Short narrative.'
        policy = Mock()
        policy.text.return_value = 'Accounting policy for debt instruments.'
        detail = Mock()
        detail.render.return_value = Mock(title='Debt - Long-term Maturities')

        note = _make_note(
            number=3, title='Debt', short_name='Debt',
            statement=stmt, policies=[policy], details=[detail],
        )
        ctx = note.to_context(detail='full')
        assert 'POLICIES:' in ctx
        assert 'Accounting policy' in ctx
        assert 'DETAIL BREAKDOWNS: 1' in ctx

    @pytest.mark.fast
    def test_narrative_truncated_at_500_chars(self):
        stmt = Mock()
        stmt.text.return_value = 'A' * 800
        note = _make_note(statement=stmt)
        ctx = note.to_context(detail='standard')
        # Should truncate and add ellipsis
        assert '...' in ctx
        # The narrative portion should be ≤ 503 chars (500 + "...")
        for line in ctx.split('\n'):
            if line.strip().startswith('A'):
                assert len(line.strip()) <= 510  # with indent


# ---------------------------------------------------------------------------
# Notes collection
# ---------------------------------------------------------------------------

class TestNotesCollection:

    @pytest.mark.fast
    def test_len(self):
        notes = _make_notes_collection(5)
        assert len(notes) == 5

    @pytest.mark.fast
    def test_iter(self):
        notes = _make_notes_collection(3)
        items = list(notes)
        assert len(items) == 3
        assert all(isinstance(n, Note) for n in items)

    @pytest.mark.fast
    def test_bool_true_when_has_notes(self):
        notes = _make_notes_collection(1)
        assert bool(notes) is True

    @pytest.mark.fast
    def test_bool_false_when_empty(self):
        notes = Notes([], entity_name='Empty Corp')
        assert bool(notes) is False

    @pytest.mark.fast
    def test_getitem_by_number(self):
        notes = _make_notes_collection(5)
        note = notes[3]
        assert note is not None
        assert note.number == 3
        assert note.title == 'Debt'

    @pytest.mark.fast
    def test_getitem_by_number_out_of_range(self):
        notes = _make_notes_collection(3)
        assert notes[99] is None

    @pytest.mark.fast
    def test_getitem_by_title_exact(self):
        notes = _make_notes_collection(5)
        note = notes['Debt']
        assert note is not None
        assert note.title == 'Debt'

    @pytest.mark.fast
    def test_getitem_by_title_case_insensitive(self):
        notes = _make_notes_collection(5)
        note = notes['debt']
        assert note is not None
        assert note.title == 'Debt'

    @pytest.mark.fast
    def test_getitem_returns_none_for_unknown_title(self):
        notes = _make_notes_collection(3)
        assert notes['Nonexistent Note'] is None

    @pytest.mark.fast
    def test_getitem_returns_none_for_bad_type(self):
        notes = _make_notes_collection(3)
        assert notes[3.14] is None

    @pytest.mark.fast
    def test_contains_by_number(self):
        notes = _make_notes_collection(3)
        assert 1 in notes
        assert 99 not in notes

    @pytest.mark.fast
    def test_contains_by_title(self):
        notes = _make_notes_collection(5)
        assert 'Debt' in notes
        assert 'debt' in notes
        assert 'Nonexistent' not in notes

    @pytest.mark.fast
    def test_str(self):
        notes = _make_notes_collection(5)
        assert str(notes) == 'Notes(5 notes)'

    @pytest.mark.fast
    def test_with_tables(self):
        n1 = _make_note(number=1, title='A', short_name='A', tables=[Mock()])
        n2 = _make_note(number=2, title='B', short_name='B')
        n3 = _make_note(number=3, title='C', short_name='C', tables=[Mock(), Mock()])
        notes = Notes([n1, n2, n3])
        result = notes.with_tables
        assert len(result) == 2
        assert result[0].title == 'A'
        assert result[1].title == 'C'


class TestNotesSearch:

    @pytest.mark.fast
    def test_exact_title_match_ranks_first(self):
        notes = _make_notes_collection(8)
        results = notes.search('Debt')
        assert len(results) >= 1
        assert results[0].title == 'Debt'

    @pytest.mark.fast
    def test_word_match(self):
        notes = _make_notes_collection(8)
        results = notes.search('Income')
        assert any('Income' in n.title for n in results)

    @pytest.mark.fast
    def test_substring_match(self):
        notes = _make_notes_collection(8)
        results = notes.search('Compensation')
        assert any('Compensation' in n.title for n in results)

    @pytest.mark.fast
    def test_no_match_returns_empty(self):
        notes = _make_notes_collection(5)
        results = notes.search('Cryptocurrency')
        assert results == []

    @pytest.mark.fast
    def test_empty_keyword_returns_empty(self):
        notes = _make_notes_collection(5)
        assert notes.search('') == []
        assert notes.search('   ') == []

    @pytest.mark.fast
    def test_case_insensitive(self):
        notes = _make_notes_collection(5)
        results = notes.search('debt')
        assert len(results) >= 1
        assert results[0].title == 'Debt'

    @pytest.mark.fast
    def test_multi_word_search(self):
        notes = _make_notes_collection(8)
        results = notes.search('share based')
        assert any('Share-Based' in n.title for n in results)

    @pytest.mark.fast
    def test_ranking_exact_before_substring(self):
        """Exact title match should rank before substring match."""
        n1 = _make_note(number=1, title='Revenue', short_name='Revenue')
        n2 = _make_note(number=2, title='Revenue Recognition', short_name='Revenue Recognition')
        notes = Notes([n1, n2])
        results = notes.search('Revenue')
        assert results[0].title == 'Revenue'

    @pytest.mark.fast
    def test_ranking_starts_with_before_word_match(self):
        """Title-starts-with should rank before word match in the middle."""
        n1 = _make_note(number=1, title='Other Revenue Details', short_name='Other Revenue Details')
        n2 = _make_note(number=2, title='Revenue Recognition', short_name='Revenue Recognition')
        notes = Notes([n1, n2])
        results = notes.search('Revenue')
        # "Revenue Recognition" starts with it → rank 1; "Other Revenue" has word match → rank 2
        assert results[0].title == 'Revenue Recognition'


class TestNotesToContext:

    @pytest.mark.fast
    def test_header_includes_entity_and_form(self):
        notes = _make_notes_collection(3)
        ctx = notes.to_context(detail='minimal')
        assert 'Test Corp' in ctx
        assert '10-K' in ctx
        assert 'Total: 3 notes' in ctx

    @pytest.mark.fast
    def test_focus_filters_notes(self):
        notes = _make_notes_collection(5)
        ctx = notes.to_context(detail='minimal', focus=['Debt'])
        assert 'Debt' in ctx
        # Other notes should not appear
        assert 'Revenue' not in ctx
        assert 'Income Taxes' not in ctx

    @pytest.mark.fast
    def test_empty_notes_context(self):
        notes = Notes([], entity_name='Empty Corp')
        ctx = notes.to_context()
        assert 'Total: 0 notes' in ctx


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestExtractShortName:

    @pytest.mark.fast
    def test_number_category_prefix(self):
        assert _extract_short_name('9952165 - Disclosure - Balance Sheet Detail') == 'Balance Sheet Detail'

    @pytest.mark.fast
    def test_note_prefix(self):
        assert _extract_short_name('Note 5 - Balance Sheet Detail') == 'Balance Sheet Detail'

    @pytest.mark.fast
    def test_note_prefix_with_dash_variants(self):
        assert _extract_short_name('Note 12 – Revenue Recognition') == 'Revenue Recognition'
        assert _extract_short_name('Note 3 — Debt') == 'Debt'

    @pytest.mark.fast
    def test_camel_case_split(self):
        result = _extract_short_name('BalanceSheetDetail')
        assert result == 'Balance Sheet Detail'

    @pytest.mark.fast
    def test_plain_text_passthrough(self):
        assert _extract_short_name('Revenue Recognition') == 'Revenue Recognition'

    @pytest.mark.fast
    def test_whitespace_stripped(self):
        assert _extract_short_name('  Debt  ') == 'Debt'


class TestIsDataConcept:

    @pytest.mark.fast
    def test_data_concepts(self):
        assert _is_data_concept('us-gaap_Revenue') is True
        assert _is_data_concept('us-gaap_LongTermDebtNoncurrent') is True
        assert _is_data_concept('us-gaap_Assets') is True

    @pytest.mark.fast
    def test_structural_concepts_filtered(self):
        assert _is_data_concept('us-gaap_RevenueAbstract') is False
        assert _is_data_concept('us-gaap_DebtAxis') is False
        assert _is_data_concept('us-gaap_DebtDomain') is False
        assert _is_data_concept('us-gaap_DebtMember') is False
        assert _is_data_concept('us-gaap_DebtLineItems') is False
        assert _is_data_concept('us-gaap_DebtTable') is False
        assert _is_data_concept('us-gaap_DebtTextBlock') is False


class TestGetConceptLabel:

    @pytest.mark.fast
    def test_label_from_catalog(self):
        xbrl = Mock()
        catalog_entry = Mock()
        catalog_entry.labels = {
            'http://www.xbrl.org/2003/role/label': 'Long-term Debt'
        }
        xbrl.parser.element_catalog.get.return_value = catalog_entry
        assert _get_concept_label('us-gaap_LongTermDebt', xbrl) == 'Long-term Debt'

    @pytest.mark.fast
    def test_fallback_camel_case_split(self):
        xbrl = Mock()
        xbrl.parser.element_catalog.get.return_value = None
        result = _get_concept_label('us-gaap_LongTermDebtNoncurrent', xbrl)
        assert result == 'Long Term Debt Noncurrent'

    @pytest.mark.fast
    def test_no_underscore_in_concept(self):
        xbrl = Mock()
        xbrl.parser.element_catalog.get.return_value = None
        result = _get_concept_label('Assets', xbrl)
        assert result == 'Assets'


# ---------------------------------------------------------------------------
# Expands computation
# ---------------------------------------------------------------------------

def _mock_xbrl_with_trees():
    """Build a mock XBRL with presentation trees for expands testing."""
    xbrl = Mock()

    # Note tree: has Revenue and COGS concepts plus structural ones
    note_tree = Mock()
    note_tree.all_nodes = {
        'us-gaap_Revenue': Mock(),
        'us-gaap_CostOfGoodsSold': Mock(),
        'us-gaap_RevenueAbstract': Mock(),       # structural — should be filtered
        'us-gaap_RevenueTextBlock': Mock(),       # structural — should be filtered
    }

    # Income statement tree: has Revenue, COGS, and NetIncome
    income_tree = Mock()
    income_tree.all_nodes = {
        'us-gaap_Revenue': Mock(),
        'us-gaap_CostOfGoodsSold': Mock(),
        'us-gaap_NetIncomeLoss': Mock(),
    }

    # Balance sheet tree: has Assets only
    balance_tree = Mock()
    balance_tree.all_nodes = {
        'us-gaap_Assets': Mock(),
        'us-gaap_Liabilities': Mock(),
    }

    xbrl.presentation_trees = {
        'http://co/role/RevenueNote': note_tree,
        'http://co/role/IncomeStatement': income_tree,
        'http://co/role/BalanceSheet': balance_tree,
    }

    # get_all_statements returns statement metadata
    xbrl.get_all_statements.return_value = [
        {'role': 'http://co/role/IncomeStatement', 'type': 'IncomeStatement',
         'definition': 'Income Statement', 'category': 'statement'},
        {'role': 'http://co/role/BalanceSheet', 'type': 'BalanceSheet',
         'definition': 'Balance Sheet', 'category': 'statement'},
        {'role': 'http://co/role/RevenueNote', 'type': 'Notes',
         'definition': 'Revenue', 'category': 'note'},
    ]

    # No catalog labels → fallback to CamelCase split
    xbrl.parser.element_catalog.get.return_value = None

    # No cache yet
    xbrl._statement_concepts_cache = None

    return xbrl


class TestCollectNoteConcepts:

    @pytest.mark.fast
    def test_collects_data_concepts_only(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        concepts = _collect_note_concepts(note, xbrl)
        assert 'us-gaap_Revenue' in concepts
        assert 'us-gaap_CostOfGoodsSold' in concepts
        # Structural concepts should be excluded
        assert 'us-gaap_RevenueAbstract' not in concepts
        assert 'us-gaap_RevenueTextBlock' not in concepts

    @pytest.mark.fast
    def test_includes_children_roles(self):
        xbrl = _mock_xbrl_with_trees()
        # Child statement whose role_or_type maps to income_tree
        child_stmt = Mock()
        child_stmt.role_or_type = 'http://co/role/IncomeStatement'
        note = _make_note(role='http://co/role/RevenueNote', tables=[child_stmt], xbrl=xbrl)
        concepts = _collect_note_concepts(note, xbrl)
        # Should include concepts from both the note tree and the child tree
        assert 'us-gaap_NetIncomeLoss' in concepts


class TestComputeExpands:

    @pytest.mark.fast
    def test_finds_overlapping_concepts(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        result = _compute_expands(note, xbrl)
        concept_ids = [cid for cid, _ in result]
        # Revenue and COGS appear in both note tree and income statement tree
        assert 'us-gaap_Revenue' in concept_ids
        assert 'us-gaap_CostOfGoodsSold' in concept_ids
        # Assets is only on balance sheet, not in note
        assert 'us-gaap_Assets' not in concept_ids

    @pytest.mark.fast
    def test_returns_empty_without_xbrl(self):
        assert _compute_expands(_make_note(), None) == []

    @pytest.mark.fast
    def test_returns_labels(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        result = _compute_expands(note, xbrl)
        labels = [label for _, label in result]
        # Fallback labels from CamelCase split
        assert 'Revenue' in labels
        assert 'Cost Of Goods Sold' in labels

    @pytest.mark.fast
    def test_results_sorted_by_label(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        result = _compute_expands(note, xbrl)
        labels = [label for _, label in result]
        assert labels == sorted(labels)


class TestComputeExpandsWithStatements:

    @pytest.mark.fast
    def test_returns_statement_types(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        data, stmt_types = _compute_expands_with_statements(note, xbrl)
        assert 'IncomeStatement' in stmt_types
        # Balance sheet has no overlap with this note
        assert 'BalanceSheet' not in stmt_types

    @pytest.mark.fast
    def test_deduplicates_concepts(self):
        xbrl = _mock_xbrl_with_trees()
        note = _make_note(role='http://co/role/RevenueNote', xbrl=xbrl)
        data, _ = _compute_expands_with_statements(note, xbrl)
        concept_ids = [cid for cid, _ in data]
        # No duplicates
        assert len(concept_ids) == len(set(concept_ids))

    @pytest.mark.fast
    def test_empty_when_no_note_concepts(self):
        xbrl = Mock()
        xbrl.presentation_trees = {}  # No trees → no concepts
        note = _make_note(role='http://co/role/Empty', xbrl=xbrl)
        data, stmt_types = _compute_expands_with_statements(note, xbrl)
        assert data == []
        assert stmt_types == set()


# ---------------------------------------------------------------------------
# Notes.from_xbrl — FilingSummary path
# ---------------------------------------------------------------------------

class TestNotesFromFilingSummary:

    def _make_report(self, role, short_name, menu_category, parent_role=None, position='1'):
        report = Mock()
        report.role = role
        report.short_name = short_name
        report.menu_category = menu_category
        report.parent_role = parent_role
        report.position = position
        return report

    @pytest.mark.fast
    def test_builds_notes_from_filing_summary(self):
        xbrl = Mock()
        xbrl.entity_info = {
            'entity_name': 'Test Corp',
            'form_type': '10-K',
            'period_of_report': '2024-12-31',
        }

        # Presentation trees must exist for Statement creation
        roles = {
            'http://co/role/Debt': Mock(),
            'http://co/role/DebtTables': Mock(),
        }
        xbrl.presentation_trees = roles
        xbrl.get_all_statements.return_value = [
            {'role': 'http://co/role/Debt', 'type': 'Notes', 'definition': 'Debt'},
            {'role': 'http://co/role/DebtTables', 'type': 'NoteTable', 'definition': 'Debt Tables'},
        ]

        filing_summary = Mock()
        filing_summary.reports = [
            self._make_report('http://co/role/Debt', 'Debt', 'Notes', position='3'),
            self._make_report('http://co/role/DebtTables', 'Debt (Tables)', 'Tables',
                              parent_role='http://co/role/Debt', position='4'),
        ]

        with patch('edgar.xbrl.statements.Statement') as MockStmt:
            notes = Notes.from_xbrl(xbrl, filing_summary=filing_summary)

        assert len(notes) == 1
        assert notes[1].title == 'Debt'
        assert len(notes[1].tables) == 1

    @pytest.mark.fast
    def test_sorts_notes_by_position(self):
        xbrl = Mock()
        xbrl.entity_info = {'entity_name': '', 'form_type': '', 'period_of_report': ''}
        xbrl.presentation_trees = {
            'http://co/role/A': Mock(),
            'http://co/role/B': Mock(),
            'http://co/role/C': Mock(),
        }
        xbrl.get_all_statements.return_value = [
            {'role': r, 'type': 'Notes', 'definition': ''}
            for r in xbrl.presentation_trees
        ]

        filing_summary = Mock()
        filing_summary.reports = [
            self._make_report('http://co/role/C', 'Third', 'Notes', position='30'),
            self._make_report('http://co/role/A', 'First', 'Notes', position='10'),
            self._make_report('http://co/role/B', 'Second', 'Notes', position='20'),
        ]

        with patch('edgar.xbrl.statements.Statement'):
            notes = Notes.from_xbrl(xbrl, filing_summary=filing_summary)

        titles = [n.title for n in notes]
        assert titles == ['First', 'Second', 'Third']

    @pytest.mark.fast
    def test_policies_and_details_attached_to_parent(self):
        xbrl = Mock()
        xbrl.entity_info = {'entity_name': '', 'form_type': '', 'period_of_report': ''}
        xbrl.presentation_trees = {
            'http://co/role/Revenue': Mock(),
            'http://co/role/RevenuePolicies': Mock(),
            'http://co/role/RevenueDetails': Mock(),
        }
        xbrl.get_all_statements.return_value = [
            {'role': r, 'type': 'Notes', 'definition': ''}
            for r in xbrl.presentation_trees
        ]

        filing_summary = Mock()
        filing_summary.reports = [
            self._make_report('http://co/role/Revenue', 'Revenue', 'Notes', position='1'),
            self._make_report('http://co/role/RevenuePolicies', 'Revenue (Policies)', 'Policies',
                              parent_role='http://co/role/Revenue', position='2'),
            self._make_report('http://co/role/RevenueDetails', 'Revenue (Details)', 'Details',
                              parent_role='http://co/role/Revenue', position='3'),
        ]

        with patch('edgar.xbrl.statements.Statement'):
            notes = Notes.from_xbrl(xbrl, filing_summary=filing_summary)

        assert len(notes) == 1
        note = notes[1]
        assert len(note.policies) == 1
        assert len(note.details) == 1

    @pytest.mark.fast
    def test_orphan_details_matched_by_name_prefix(self):
        """Details without ParentRole are matched by name-prefix to parent note."""
        xbrl = Mock()
        xbrl.entity_info = {'entity_name': '', 'form_type': '', 'period_of_report': ''}
        xbrl.presentation_trees = {
            'http://co/role/Debt': Mock(),
            'http://co/role/DebtMaturities': Mock(),
        }
        xbrl.get_all_statements.return_value = [
            {'role': r, 'type': 'Notes', 'definition': ''}
            for r in xbrl.presentation_trees
        ]

        filing_summary = Mock()
        filing_summary.reports = [
            self._make_report('http://co/role/Debt', 'Debt', 'Notes', position='1'),
            # Orphan detail — no parent_role, but name starts with "Debt"
            self._make_report('http://co/role/DebtMaturities', 'Debt Maturities', 'Details',
                              parent_role=None, position='2'),
        ]

        with patch('edgar.xbrl.statements.Statement'):
            notes = Notes.from_xbrl(xbrl, filing_summary=filing_summary)

        assert len(notes) == 1
        assert len(notes[1].details) == 1


# ---------------------------------------------------------------------------
# Notes.from_xbrl — XBRL-only fallback path
# ---------------------------------------------------------------------------

class TestNotesFromXbrlOnly:

    @pytest.mark.fast
    def test_builds_flat_notes_from_classification(self):
        xbrl = Mock()
        xbrl.entity_info = {'entity_name': 'Fallback Corp', 'form_type': '10-Q', 'period_of_report': ''}
        xbrl.presentation_trees = {
            'http://co/role/RevenueNote': Mock(),
            'http://co/role/IncomeStatement': Mock(),
        }
        xbrl.get_all_statements.return_value = [
            {'role': 'http://co/role/RevenueNote', 'type': 'Notes',
             'definition': '9952165 - Disclosure - Revenue', 'category': 'note'},
            {'role': 'http://co/role/IncomeStatement', 'type': 'IncomeStatement',
             'definition': 'Income Statement', 'category': 'statement'},
        ]

        with patch('edgar.xbrl.statements.Statement'):
            notes = Notes.from_xbrl(xbrl, filing_summary=None)

        # Only Notes type, not IncomeStatement
        assert len(notes) == 1
        assert notes[1].title == 'Revenue'
        assert notes.entity_name == 'Fallback Corp'

    @pytest.mark.fast
    def test_fallback_has_no_children(self):
        """Without FilingSummary, notes have no tables/policies/details."""
        xbrl = Mock()
        xbrl.entity_info = {'entity_name': '', 'form_type': '', 'period_of_report': ''}
        xbrl.presentation_trees = {'http://co/role/Debt': Mock()}
        xbrl.get_all_statements.return_value = [
            {'role': 'http://co/role/Debt', 'type': 'Notes',
             'definition': 'Debt', 'category': 'note'},
        ]

        with patch('edgar.xbrl.statements.Statement'):
            notes = Notes.from_xbrl(xbrl, filing_summary=None)

        note = notes[1]
        assert note.tables == []
        assert note.policies == []
        assert note.details == []


# ---------------------------------------------------------------------------
# CompanyReport.notes integration
# ---------------------------------------------------------------------------

class TestCompanyReportNotes:

    @pytest.mark.fast
    def test_notes_returns_empty_without_financials(self):
        """When financials are None, notes returns empty Notes."""
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        report = CompanyReport(filing)

        # Override financials to return None
        with patch.object(type(report), 'financials', new_callable=PropertyMock, return_value=None):
            notes = report.notes
        assert isinstance(notes, Notes)
        assert len(notes) == 0

    @pytest.mark.fast
    def test_notes_returns_empty_without_xbrl(self):
        """When financials.xb is None, notes returns empty Notes."""
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        report = CompanyReport(filing)
        financials = Mock()
        financials.xb = None

        with patch.object(type(report), 'financials', new_callable=PropertyMock, return_value=financials):
            notes = report.notes
        assert isinstance(notes, Notes)
        assert len(notes) == 0


# ---------------------------------------------------------------------------
# TenK / TenQ to_context(focus=...)
# ---------------------------------------------------------------------------

class TestFocusedContext:

    @pytest.mark.fast
    def test_focused_context_calls_notes_search(self):
        """to_context(focus='debt') should delegate to _focused_context."""
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        filing.form = '10-K'
        report = CompanyReport(filing)

        # Mock notes with a matching note
        mock_note = _make_note(number=3, title='Debt', short_name='Debt')
        mock_notes = Mock(spec=Notes)
        mock_notes.search.return_value = [mock_note]
        mock_notes.__iter__ = Mock(return_value=iter([mock_note]))
        mock_notes.__bool__ = Mock(return_value=True)

        with patch.object(type(report), 'notes', new_callable=PropertyMock, return_value=mock_notes):
            with patch.object(type(report), 'period_of_report', new_callable=PropertyMock, return_value='2024-12-31'):
                result = report._focused_context('debt')

        assert '10-K' in result.upper() or 'Test Corp' in result
        mock_notes.search.assert_called_once_with('debt')

    @pytest.mark.fast
    def test_focused_context_no_match(self):
        """When no note matches, context says so."""
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        filing.form = '10-K'
        report = CompanyReport(filing)

        mock_notes = Mock(spec=Notes)
        mock_notes.search.return_value = []
        mock_notes.__iter__ = Mock(return_value=iter([]))
        mock_notes.__bool__ = Mock(return_value=True)

        with patch.object(type(report), 'notes', new_callable=PropertyMock, return_value=mock_notes):
            with patch.object(type(report), 'period_of_report', new_callable=PropertyMock, return_value='2024-12-31'):
                result = report._focused_context('cryptocurrency')

        assert 'No matching note found' in result

    @pytest.mark.fast
    def test_focused_context_multiple_topics(self):
        """_focused_context accepts a list of topics."""
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        filing.form = '10-Q'
        report = CompanyReport(filing)

        debt_note = _make_note(number=3, title='Debt', short_name='Debt')
        rev_note = _make_note(number=2, title='Revenue', short_name='Revenue')

        mock_notes = Mock(spec=Notes)
        mock_notes.search.side_effect = lambda k: [debt_note] if k == 'debt' else [rev_note]
        mock_notes.__iter__ = Mock(return_value=iter([debt_note, rev_note]))
        mock_notes.__bool__ = Mock(return_value=True)

        with patch.object(type(report), 'notes', new_callable=PropertyMock, return_value=mock_notes):
            with patch.object(type(report), 'period_of_report', new_callable=PropertyMock, return_value='2024-06-30'):
                result = report._focused_context(['debt', 'revenue'])

        assert 'Debt' in result
        assert 'Revenue' in result

    @pytest.mark.fast
    def test_focused_context_when_notes_empty(self):
        from edgar.company_reports._base import CompanyReport

        filing = Mock()
        filing.company = 'Test Corp'
        filing.form = '10-K'
        report = CompanyReport(filing)

        empty_notes = Notes([])

        with patch.object(type(report), 'notes', new_callable=PropertyMock, return_value=empty_notes):
            with patch.object(type(report), 'period_of_report', new_callable=PropertyMock, return_value='2024-12-31'):
                result = report._focused_context('debt')

        assert 'No notes available' in result


# ---------------------------------------------------------------------------
# Statement.html property
# ---------------------------------------------------------------------------

class TestStatementHtmlProperty:

    @pytest.mark.fast
    def test_html_property_calls_text_with_raw_html(self):
        """Statement.html should be a shortcut to .text(raw_html=True)."""
        from edgar.xbrl.statements import Statement

        mock_xbrl = Mock()
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Some Note'}],
            'http://test.com/role/SomeNote',
            'Disclosure'
        )
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_SomeTextBlock',
                'label': 'Some Note',
                'values': {'duration_2023': '<div><p>Hello</p></div>'},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/SomeNote')
        result = stmt.html
        assert result is not None
        assert '<div>' in result or '<p>' in result
