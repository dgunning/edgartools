"""
Tests for XBRL notes extraction fix.

Verifies that TextBlock concepts are correctly classified (not abstract),
that Statement objects support text extraction, and that notes() returns
Statement objects.
"""

import pytest
from unittest.mock import Mock

from edgar.xbrl.abstract_detection import is_abstract_concept, is_textblock_concept


class TestTextBlockClassification:
    """Verify TextBlock concepts are not misclassified as abstract."""

    @pytest.mark.fast
    def test_textblock_not_classified_as_abstract(self):
        """TextBlock concepts are content-bearing, not abstract."""
        assert not is_abstract_concept('us-gaap_RevenueTextBlock')
        assert not is_abstract_concept('us-gaap_EarningsPerShareTextBlock')
        assert not is_abstract_concept('us-gaap_SignificantAccountingPoliciesTextBlock')
        assert not is_abstract_concept('us-gaap_InventoryDisclosureTextBlock')

    @pytest.mark.fast
    def test_textblock_abstract_still_abstract(self):
        """TextBlockAbstract concepts should still be abstract (covered by *Abstract pattern)."""
        assert is_abstract_concept('us-gaap_DisclosureTextBlockAbstract')
        assert is_abstract_concept('us-gaap_SomeOtherTextBlockAbstract')

    @pytest.mark.fast
    def test_is_textblock_concept_helper(self):
        """Test the is_textblock_concept helper function."""
        # True for TextBlock concepts
        assert is_textblock_concept('us-gaap_RevenueTextBlock')
        assert is_textblock_concept('us-gaap:EarningsPerShareTextBlock')
        assert is_textblock_concept('us-gaap_SignificantAccountingPoliciesTextBlock')

        # False for TextBlockAbstract
        assert not is_textblock_concept('us-gaap_DisclosureTextBlockAbstract')
        assert not is_textblock_concept('us-gaap:SomeTextBlockAbstract')

        # False for plain concepts
        assert not is_textblock_concept('us-gaap_Revenue')
        assert not is_textblock_concept('us-gaap_Assets')

    @pytest.mark.fast
    def test_other_abstract_patterns_unchanged(self):
        """Other abstract patterns still work correctly."""
        assert is_abstract_concept('us-gaap_SomethingAbstract')
        assert is_abstract_concept('us-gaap_SomethingRollForward')
        assert is_abstract_concept('us-gaap_SomethingTable')
        assert is_abstract_concept('us-gaap_SomethingAxis')
        assert is_abstract_concept('us-gaap_SomethingDomain')
        assert is_abstract_concept('us-gaap_SomethingLineItems')


class TestStatementTextExtraction:
    """Test text() method and is_note property on Statement objects."""

    @pytest.mark.fast
    def test_statement_text_returns_none_for_financial(self):
        """Financial statements (no TextBlock concepts) return None from text()."""
        from edgar.xbrl.statements import Statement

        mock_xbrl = Mock()
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Income Statement'}],
            'http://test.com/role/IncomeStatement',
            'IncomeStatement'
        )
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_Revenue',
                'label': 'Revenue',
                'values': {'duration_2023': 1000000},
                'level': 0,
                'is_abstract': False,
            },
            {
                'concept': 'us-gaap_NetIncomeLoss',
                'label': 'Net Income',
                'values': {'duration_2023': 500000},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/IncomeStatement')
        assert stmt.text() is None

    @pytest.mark.fast
    def test_statement_is_note_false_for_financial(self):
        """Financial statements return is_note=False."""
        from edgar.xbrl.statements import Statement

        mock_xbrl = Mock()
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Income Statement'}],
            'http://test.com/role/IncomeStatement',
            'IncomeStatement'
        )
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_Revenue',
                'label': 'Revenue',
                'values': {'duration_2023': 1000000},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/IncomeStatement')
        assert stmt.is_note is False

    @pytest.mark.fast
    def test_statement_is_note_true_for_notes(self):
        """Statements with TextBlock concepts return is_note=True."""
        from edgar.xbrl.statements import Statement

        mock_xbrl = Mock()
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Revenue Disclosure'}],
            'http://test.com/role/RevenueDisclosure',
            'Disclosure'
        )
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_RevenueFromContractWithCustomerTextBlock',
                'label': 'Revenue Disclosure',
                'values': {'duration_2023': '<p>Revenue recognition policy...</p>'},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/RevenueDisclosure')
        assert stmt.is_note is True

    @pytest.mark.fast
    def test_statement_text_extracts_plain_text(self):
        """text() extracts plain text content from TextBlock values."""
        from edgar.xbrl.statements import Statement

        mock_xbrl = Mock()
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Inventory Disclosure'}],
            'http://test.com/role/InventoryDisclosure',
            'Disclosure'
        )
        mock_xbrl.get_statement.return_value = [
            {
                'concept': 'us-gaap_InventoryDisclosureTextBlock',
                'label': 'Inventory Disclosure',
                'values': {'duration_2023': 'Inventory consists of raw materials and finished goods.'},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/InventoryDisclosure')
        result = stmt.text()
        assert result is not None
        assert 'Inventory' in result

    @pytest.mark.fast
    def test_statement_text_raw_html(self):
        """text(raw_html=True) returns the raw HTML content."""
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
                'values': {'duration_2023': '<p>Hello <b>World</b></p>'},
                'level': 0,
                'is_abstract': False,
            }
        ]
        mock_xbrl.render_statement.return_value = Mock()

        stmt = Statement(mock_xbrl, 'http://test.com/role/SomeNote')
        result = stmt.text(raw_html=True)
        assert result is not None
        assert '<p>' in result
        assert '<b>World</b>' in result


class TestNotesReturnsStatements:
    """Test that CurrentPeriodView.notes() returns Statement objects."""

    @pytest.mark.fast
    def test_notes_returns_statement_objects(self):
        """notes() should return a list of Statement objects, not dicts."""
        from edgar.xbrl.current_period import CurrentPeriodView
        from edgar.xbrl.statements import Statement
        from edgar.xbrl.rendering import RenderedStatement

        mock_xbrl = Mock()
        mock_xbrl.reporting_periods = [
            {'key': 'duration_2023-01-01_2023-12-31', 'label': 'FY 2023'},
            {'key': 'instant_2023-12-31', 'label': 'Dec 31, 2023'},
        ]
        mock_xbrl.period_of_report = '2023-12-31'
        mock_xbrl.entity_name = 'Test Corp'
        mock_xbrl.document_type = '10-K'
        mock_xbrl.get_all_statements.return_value = [
            {
                'type': 'Notes',
                'definition': 'Revenue Disclosure',
                'role': 'http://example.com/role/revenue',
                'element_count': 5
            },
            {
                'type': 'Statement',
                'definition': 'Income Statement',
                'role': 'http://example.com/role/income',
                'element_count': 20
            }
        ]
        mock_xbrl.find_statement.return_value = (
            [{'definition': 'Revenue Disclosure'}],
            'http://example.com/role/revenue',
            'Notes'
        )
        mock_xbrl.render_statement.return_value = Mock(spec=RenderedStatement)

        cpv = CurrentPeriodView(mock_xbrl)
        notes = cpv.notes()

        assert isinstance(notes, list)
        assert len(notes) == 1  # Only Notes, not Statement type
        assert isinstance(notes[0], Statement)
