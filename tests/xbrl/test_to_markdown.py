"""
Tests for to_markdown() methods on drill-down objects.

Covers:
- edgar.markdown: create_markdown_table, process_content
- RenderedStatement.to_markdown(): detail levels, Rich tag stripping, NBSP indentation
- Statement.to_markdown(): delegation
- StatementLineItem.to_markdown(): values + note reference
- Note.to_markdown(): tables, narrative, policies, details, detail levels
- Notes.to_markdown(): full document, focus filtering
- CompanyReport._focused_context(): text context generation
"""
import re
from unittest.mock import Mock, MagicMock, patch

import pytest

from edgar.markdown import create_markdown_table, process_content, clean_text, list_of_dicts_to_table
from edgar.xbrl.rendering import (
    RenderedStatement, StatementRow, StatementCell, StatementHeader,
)
from edgar.xbrl.notes import Note, Notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(value, formatted=None):
    """Create a StatementCell with a simple formatter."""
    fmt = formatted or str(value) if value is not None else ""
    return StatementCell(value=value, formatter=lambda v, f=fmt: f if v is not None else "")


def _row(label, values, level=0, is_abstract=False, is_dimension=False, concept=''):
    """Create a StatementRow with cells."""
    cells = [_cell(v) for v in values]
    return StatementRow(
        label=label,
        level=level,
        cells=cells,
        metadata={'concept': concept},
        is_abstract=is_abstract,
        is_dimension=is_dimension,
    )


def _rendered_statement(title='Income Statement', company='Apple Inc.', ticker='AAPL',
                        columns=None, rows=None, units_note=None, fiscal_period=None):
    """Build a RenderedStatement with sensible defaults."""
    columns = columns or ['2024-09-28', '2023-09-30']
    rows = rows or [
        _row('Net sales', [391035, 383285], level=0, is_abstract=True, concept='us-gaap_Revenue'),
        _row('Products', [224578, 220272], level=1, concept='us-gaap_ProductRevenue'),
        _row('Services', [166457, 163013], level=1, concept='us-gaap_ServiceRevenue'),
    ]
    header = StatementHeader(columns=columns)
    return RenderedStatement(
        title=title,
        header=header,
        rows=rows,
        metadata={'company_name': company, 'ticker': ticker},
        statement_type='IncomeStatement',
        fiscal_period_indicator=fiscal_period,
        units_note=units_note,
    )


def _make_note(number=1, title='Debt', short_name='Debt', role='http://co/role/Debt',
               tables=None, policies=None, details=None, xbrl=None, statement=None):
    """Build a Note with sensible defaults."""
    return Note(
        number=number, title=title, short_name=short_name, role=role,
        statement=statement, tables=tables or [], policies=policies or [],
        details=details or [], xbrl=xbrl,
    )


def _make_notes_collection(count=5):
    """Build a Notes object with N numbered notes."""
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
    notes = []
    for i in range(min(count, len(titles))):
        notes.append(_make_note(
            number=i + 1, title=titles[i], short_name=titles[i],
            role=f'http://co/role/Note{i + 1}',
        ))
    return Notes(notes, entity_name='Test Corp', form='10-K', period='2024-12-31')


# ===========================================================================
# edgar.markdown module
# ===========================================================================

class TestCreateMarkdownTable:

    @pytest.mark.fast
    def test_basic_table(self):
        md = create_markdown_table(['Item', 'Value'], [['Revenue', '$100M'], ['Net Income', '$25M']])
        assert '| Item | Value |' in md
        assert '| Revenue | $100M |' in md
        assert '| Net Income | $25M |' in md

    @pytest.mark.fast
    def test_right_alignment(self):
        md = create_markdown_table(['Label', 'Amount'], [['A', '100']], alignments=['left', 'right'])
        assert '---:' in md

    @pytest.mark.fast
    def test_empty_table(self):
        md = create_markdown_table(['A'], [])
        # Empty rows produces empty string (no table at all)
        assert md == ''

    @pytest.mark.fast
    def test_short_rows_padded(self):
        md = create_markdown_table(['A', 'B', 'C'], [['x']])
        # Row should be padded to 3 columns
        assert md.count('|') >= 4  # at least | x | | |


class TestProcessContent:

    @pytest.mark.fast
    def test_html_table_to_markdown(self):
        html = '<table><tr><th>Metric</th><th>2024</th></tr><tr><td>Revenue</td><td>$100M</td></tr></table>'
        md = process_content(html)
        assert 'Revenue' in md
        assert '$100M' in md
        assert '|' in md  # pipe table

    @pytest.mark.fast
    def test_plain_text_passthrough(self):
        text = 'The Company issues unsecured promissory notes.'
        md = process_content(text)
        assert 'promissory notes' in md

    @pytest.mark.fast
    def test_heading_extraction(self):
        html = '<h3>Debt Summary</h3><p>Total debt was $50B.</p>'
        md = process_content(html)
        assert 'Debt Summary' in md
        assert '$50B' in md

    @pytest.mark.fast
    def test_noise_filtered(self):
        html = '<p>http://fasb.org/us-gaap/2024</p><p>Real content here.</p>'
        md = process_content(html)
        assert 'fasb.org' not in md
        assert 'Real content' in md

    @pytest.mark.fast
    def test_track_filtered_returns_tuple(self):
        html = '<table><tr><td>Data</td></tr></table>'
        result = process_content(html, track_filtered=True)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestCleanText:

    @pytest.mark.fast
    def test_nbsp_collapsed(self):
        assert clean_text('hello\xa0world') == 'hello world'

    @pytest.mark.fast
    def test_multiple_spaces(self):
        assert clean_text('a   b    c') == 'a b c'


class TestListOfDictsToTable:

    @pytest.mark.fast
    def test_basic_conversion(self):
        data = [
            {'label': 'Revenue', 'col_0': '$100M', 'col_1': '$90M'},
            {'label': 'Net Income', 'col_0': '$25M', 'col_1': '$20M'},
        ]
        md = list_of_dicts_to_table(data)
        assert 'Revenue' in md
        assert '$100M' in md
        assert '|' in md


# ===========================================================================
# RenderedStatement.to_markdown()
# ===========================================================================

class TestRenderedStatementToMarkdown:

    @pytest.mark.fast
    def test_standard_includes_company_header(self):
        rs = _rendered_statement()
        md = rs.to_markdown()
        assert '## Income Statement' in md
        assert 'Apple Inc.' in md
        assert 'AAPL' in md

    @pytest.mark.fast
    def test_minimal_no_header(self):
        rs = _rendered_statement()
        md = rs.to_markdown(detail='minimal')
        assert '## ' not in md
        assert 'Apple' not in md
        # But table is present
        assert '| ' in md
        assert 'Net sales' in md

    @pytest.mark.fast
    def test_full_includes_footer(self):
        rs = _rendered_statement(units_note='[italic]In millions[/italic]')
        md = rs.to_markdown(detail='full')
        assert 'Source: SEC XBRL' in md
        assert 'In millions' in md

    @pytest.mark.fast
    def test_rich_tags_stripped(self):
        rs = _rendered_statement(units_note='[italic]In millions[/italic], [dim]except per share[/dim]')
        md = rs.to_markdown()
        assert '[italic]' not in md
        assert '[/italic]' not in md
        assert '[dim]' not in md
        assert '[/dim]' not in md
        assert 'In millions' in md

    @pytest.mark.fast
    def test_right_aligned_separator(self):
        rs = _rendered_statement()
        md = rs.to_markdown()
        assert '---:' in md

    @pytest.mark.fast
    def test_nbsp_indentation(self):
        rs = _rendered_statement()
        md = rs.to_markdown()
        # Level-1 rows should use NBSP for indentation
        assert '\u00A0' in md

    @pytest.mark.fast
    def test_abstract_row_bold(self):
        rs = _rendered_statement()
        md = rs.to_markdown()
        assert '**' in md  # abstract row is bolded

    @pytest.mark.fast
    def test_optimize_for_llm_skips_empty_abstract(self):
        rows = [
            _row('ASSETS', [None, None], is_abstract=True),
            _row('Cash', [50000, 40000]),
        ]
        rs = _rendered_statement(rows=rows)
        md_normal = rs.to_markdown(optimize_for_llm=False)
        md_llm = rs.to_markdown()  # optimize_for_llm=True is now the default
        assert 'ASSETS' in md_normal
        assert 'ASSETS' not in md_llm
        assert 'Cash' in md_llm

    @pytest.mark.fast
    def test_backward_compatible_no_args(self):
        """Calling to_markdown() with no args should work like old behavior."""
        rs = _rendered_statement()
        md = rs.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 50


# ===========================================================================
# Statement.to_markdown()
# ===========================================================================

class TestStatementToMarkdown:

    @pytest.mark.fast
    def test_delegates_to_rendered(self):
        """Statement.to_markdown() should delegate to render().to_markdown()."""
        mock_rendered = Mock()
        mock_rendered.to_markdown.return_value = '## Test\n| A | B |'

        stmt = Mock()
        stmt.render.return_value = mock_rendered

        # Call the actual method implementation
        from edgar.xbrl.statements import Statement
        result = Statement.to_markdown(stmt, detail='full', optimize_for_llm=True)
        mock_rendered.to_markdown.assert_called_once_with(detail='full', optimize_for_llm=True)


# ===========================================================================
# StatementLineItem.to_markdown()
# ===========================================================================

class TestStatementLineItemToMarkdown:

    @pytest.mark.fast
    def test_with_values(self):
        from edgar.xbrl.statements import StatementLineItem
        cells = [
            StatementCell(value=67886000000, formatter=lambda v: '67,886' if v else ''),
            StatementCell(value=65413000000, formatter=lambda v: '65,413' if v else ''),
        ]
        row = StatementRow(label='Goodwill', level=0, cells=cells,
                           metadata={'concept': 'us-gaap_Goodwill'})
        columns = ['2024-09-28', '2023-09-30']
        item = StatementLineItem(row, xbrl=None, columns=columns)
        md = item.to_markdown(include_note=False)
        assert '**Goodwill**' in md
        assert '67,886 (2024-09-28)' in md
        assert '65,413 (2023-09-30)' in md

    @pytest.mark.fast
    def test_with_note_reference(self):
        from edgar.xbrl.statements import StatementLineItem
        cells = [StatementCell(value=67886000000, formatter=lambda v: '67,886' if v else '')]
        row = StatementRow(label='Goodwill', level=0, cells=cells,
                           metadata={'concept': 'us-gaap_Goodwill'})
        mock_note = _make_note(number=7, title='Goodwill and Intangible Assets')

        item = StatementLineItem(row, xbrl=None, columns=['2024-09-28'])

        with patch.object(StatementLineItem, 'note', new_callable=lambda: property(lambda self: mock_note)):
            md = item.to_markdown(include_note=True)
            assert 'Note 7' in md
            assert 'Goodwill and Intangible Assets' in md
            assert '>' in md  # blockquote

    @pytest.mark.fast
    def test_no_note_no_blockquote(self):
        from edgar.xbrl.statements import StatementLineItem
        cells = [StatementCell(value=50000, formatter=lambda v: '50,000' if v else '')]
        row = StatementRow(label='Cash', level=0, cells=cells,
                           metadata={'concept': 'us-gaap_Cash'})
        item = StatementLineItem(row, xbrl=None)
        md = item.to_markdown(include_note=True)
        # No note found (xbrl=None), so no blockquote
        assert '>' not in md
        assert '**Cash**' in md

    @pytest.mark.fast
    def test_no_values(self):
        from edgar.xbrl.statements import StatementLineItem
        cells = [
            StatementCell(value=None, formatter=lambda v: ''),
            StatementCell(value=None, formatter=lambda v: ''),
        ]
        row = StatementRow(label='Abstract Header', level=0, cells=cells,
                           metadata={'concept': ''}, is_abstract=True)
        item = StatementLineItem(row, xbrl=None)
        md = item.to_markdown(include_note=False)
        assert '**Abstract Header**' in md


# ===========================================================================
# Note.to_markdown()
# ===========================================================================

class TestNoteToMarkdown:

    @pytest.mark.fast
    def test_minimal_title_only(self):
        note = _make_note(number=3, title='Debt')
        md = note.to_markdown(detail='minimal')
        assert '## Note 3: Debt' in md
        # No narrative or tables
        assert '### Narrative' not in md

    @pytest.mark.fast
    def test_minimal_with_table_names(self):
        table_stmt = Mock()
        table_stmt.render.return_value = Mock(title='Schedule of Debt Maturities')
        note = _make_note(number=3, title='Debt', tables=[table_stmt])
        md = note.to_markdown(detail='minimal')
        assert '## Note 3: Debt' in md
        assert '**Tables:**' in md

    @pytest.mark.fast
    def test_standard_with_tables_and_narrative(self):
        # Table stmt that returns HTML
        table_stmt = Mock()
        table_stmt.render.return_value = Mock(title='Debt Maturities')
        table_stmt.text.side_effect = lambda raw_html=False: (
            '<table><tr><td>2025</td><td>$10B</td></tr></table>' if raw_html
            else '2025: $10B'
        )
        # Main statement with narrative
        main_stmt = Mock()
        main_stmt.text.return_value = 'The Company issues short-term promissory notes.'

        note = _make_note(number=9, title='Debt', tables=[table_stmt], statement=main_stmt)
        md = note.to_markdown(detail='standard')

        assert '## Note 9: Debt' in md
        # _extract_table_name strips parent prefix "Debt" → "Maturities"
        assert 'Maturities' in md
        assert '### Narrative' in md
        assert 'promissory notes' in md

    @pytest.mark.fast
    def test_full_includes_policies_and_details(self):
        policy_stmt = Mock()
        policy_stmt.render.return_value = Mock(title='Debt - Accounting Policy')
        policy_stmt.text.return_value = 'The Company records debt at amortized cost.'

        detail_stmt = Mock()
        detail_stmt.render.return_value = Mock(title='Long-term Debt Components')
        detail_stmt.text.side_effect = lambda raw_html=False: (
            '<table><tr><td>Term Debt</td><td>$50B</td></tr></table>' if raw_html
            else 'Term Debt: $50B'
        )

        main_stmt = Mock()
        main_stmt.text.return_value = 'Narrative text here.'

        note = _make_note(
            number=9, title='Debt',
            tables=[], policies=[policy_stmt], details=[detail_stmt],
            statement=main_stmt,
        )
        md = note.to_markdown(detail='full')

        assert '### Policy:' in md
        assert 'amortized cost' in md
        assert 'Long-term Debt' in md

    @pytest.mark.fast
    def test_optimize_for_llm_false_uses_plain_text(self):
        table_stmt = Mock()
        table_stmt.render.return_value = Mock(title='Summary')
        table_stmt.text.side_effect = lambda raw_html=False: (
            '<table><tr><td>A</td></tr></table>' if raw_html
            else 'Plain text fallback'
        )

        note = _make_note(number=1, title='Test', tables=[table_stmt])
        md = note.to_markdown(detail='standard', optimize_for_llm=False)
        assert 'Plain text fallback' in md

    @pytest.mark.fast
    def test_expands_metadata(self):
        note = _make_note(number=5, title='Revenue')
        # Patch expands properties
        with patch.object(type(note), 'expands', new_callable=lambda: property(
            lambda self: ['Net sales', 'Product revenue'])):
            with patch.object(type(note), 'expands_statements', new_callable=lambda: property(
                lambda self: ['IncomeStatement'])):
                md = note.to_markdown(detail='minimal')
                assert '**Expands:**' in md
                assert 'Net sales' in md
                assert '**From:**' in md
                assert 'IncomeStatement' in md


# ===========================================================================
# Notes.to_markdown()
# ===========================================================================

class TestNotesToMarkdown:

    @pytest.mark.fast
    def test_full_document_header(self):
        notes = _make_notes_collection(3)
        md = notes.to_markdown(detail='minimal')
        assert '# Notes to Financial Statements' in md
        assert 'Test Corp' in md
        assert '10-K' in md
        assert '2024-12-31' in md

    @pytest.mark.fast
    def test_all_notes_included(self):
        notes = _make_notes_collection(3)
        md = notes.to_markdown(detail='minimal')
        assert 'Note 1' in md
        assert 'Note 2' in md
        assert 'Note 3' in md

    @pytest.mark.fast
    def test_focus_filters_notes(self):
        notes = _make_notes_collection(5)
        md = notes.to_markdown(detail='minimal', focus='Debt')
        assert 'Note 3: Debt' in md
        # Other notes should NOT be present
        assert 'Revenue Recognition' not in md
        assert 'Income Taxes' not in md

    @pytest.mark.fast
    def test_focus_list(self):
        notes = _make_notes_collection(5)
        md = notes.to_markdown(detail='minimal', focus=['Debt', 'Revenue'])
        assert 'Debt' in md
        assert 'Revenue' in md
        # Non-matching notes excluded
        assert 'Income Taxes' not in md

    @pytest.mark.fast
    def test_separator_between_notes(self):
        notes = _make_notes_collection(3)
        md = notes.to_markdown(detail='minimal')
        assert '---' in md

    @pytest.mark.fast
    def test_empty_notes(self):
        notes = Notes([], entity_name='Empty Corp')
        md = notes.to_markdown()
        assert '# Notes to Financial Statements' in md
        assert 'Note 1' not in md


# ===========================================================================
# _focused_context integration
# ===========================================================================

class TestFocusedContext:

    @pytest.mark.fast
    def test_focused_context_returns_text(self):
        """_focused_context should return plain text context."""
        from edgar.company_reports._base import CompanyReport
        report = Mock(spec=CompanyReport)
        report.form = '10-K'
        report.company = 'Test Corp'
        report.notes = _make_notes_collection(5)
        report.period_of_report = '2024-12-31'

        result = CompanyReport._focused_context(report, focus='Debt', detail='minimal')
        assert '10-K: Test Corp' in result
        assert '## Debt' in result
