"""
Regression test for GitHub Issue #248: Tables in 10K text partially truncated

Problem: When extracting text from SEC filings using the new parser with
fast table rendering, long cell content was truncated with "..." due to
max_col_width=60 in FastTableRenderer.simple() style.

Solution: Increased max_col_width from 60 to 200 in the simple() style to
avoid truncating typical SEC filing text while still providing a reasonable limit.

GitHub Issue: https://github.com/dgunning/edgartools/issues/248
"""
import pytest
from edgar import Company
from edgar.documents.parser import HTMLParser
from edgar.documents.renderers.fast_table import TableStyle


@pytest.mark.network
class TestIssue248TableTruncation:
    """Tests for table truncation fix in Issue #248."""

    def test_fast_table_renderer_does_not_truncate_long_descriptions(self):
        """
        Original issue: Long financial descriptions were truncated with "...".

        Example: "(Decrease) increase to the long-term Supplemental compensation accrual"
        was truncated to "(Decrease) increase to the long-term Supplemental com..."
        """
        # Get the filing mentioned in the issue - CIK 783412 (Daily Journal Corp)
        filing = Company(783412).get_filings(form='10-K')[0]
        html = filing.html()

        # Parse with new parser (fast_table_rendering is enabled by default)
        parser = HTMLParser()
        doc = parser.parse(html)
        text = doc.text()

        # Check that long descriptions are NOT truncated
        # The specific row that was truncated before the fix
        truncation_indicators = [
            'Supplemental com...',
            'collateralized by r...',
            'marketable secur...',
        ]

        for indicator in truncation_indicators:
            assert indicator not in text, f"Text still truncated: found '{indicator}'"

    def test_simple_style_max_col_width_is_adequate(self):
        """Verify the simple() style has adequate max_col_width."""
        style = TableStyle.simple()

        # max_col_width should be high enough to avoid truncating SEC filing text
        assert style.max_col_width >= 100, (
            f"max_col_width={style.max_col_width} is too low, "
            "should be >= 100 to avoid truncating SEC filing text"
        )

    def test_financial_table_content_preserved(self):
        """
        Ensure financial tables preserve their full content.

        This tests that the "Overall Financial Results" table from the
        10-K filing has all its content without truncation.
        """
        filing = Company(783412).get_filings(form='10-K')[0]
        html = filing.html()

        parser = HTMLParser()
        doc = parser.parse(html)

        # Find a table with financial data
        tables = doc.tables
        financial_table = None
        for table in tables:
            table_text = table.text()
            if 'Advertising' in table_text and 'Revenues' in table_text:
                financial_table = table
                break

        assert financial_table is not None, "Could not find financial table"

        table_text = financial_table.text()

        # Verify no truncation indicators
        assert '...' not in table_text or table_text.count('...') == 0 or \
               all(not line.endswith('...') for line in table_text.split('\n') if '...' in line), \
               "Table text contains truncation indicators"

        # Verify key financial terms are present (not truncated)
        expected_terms = ['Advertising', 'Circulation', 'Revenues', 'Total']
        for term in expected_terms:
            assert term in table_text, f"Expected term '{term}' not found in table"
