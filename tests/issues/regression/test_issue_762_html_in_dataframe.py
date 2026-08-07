"""
Regression test for Issue #762: to_dataframe() exposes raw HTML in disclosure/notes statements.

XBRL TextBlock concepts (e.g., segment disclosure tables) contain HTML-encoded fact values.
The to_dataframe() path must sanitize these to plain text so DataFrame cells are usable.

Uses the MSFT 10-K fixture which has disclosure tables with TextBlock concepts.
"""

import re

import pytest

from edgar.xbrl.rendering import _is_html, html_to_text


HTML_TAG_PATTERN = re.compile(r'<[a-zA-Z][^>]*>')


class TestHtmlSanitization:
    """Verify _is_html and html_to_text work correctly for TextBlock content."""

    def test_is_html_detects_table_markup(self):
        assert _is_html('<table><tr><td>Revenue</td><td>100</td></tr></table>')

    def test_is_html_detects_paragraph_markup(self):
        assert _is_html('<p style="font-size:10pt">Some disclosure text</p>')

    def test_is_html_rejects_plain_text(self):
        assert not _is_html('Revenue from contracts with customers')

    def test_is_html_rejects_numeric_string(self):
        assert not _is_html('1234567890')

    def test_html_to_text_strips_tags(self):
        html = '<p>Revenue was <span style="font-weight:bold">$100 million</span> for the period.</p>'
        text = html_to_text(html)
        assert '<' not in text
        assert '100 million' in text

    def test_html_to_text_handles_table(self):
        html = '<table><tr><td>Segment</td><td>Revenue</td></tr><tr><td>Cloud</td><td>50,000</td></tr></table>'
        text = html_to_text(html)
        assert '<' not in text
        assert 'Cloud' in text


class TestDataFrameNoHtml:
    """Verify to_dataframe() output contains no HTML for disclosure statements."""

    @pytest.fixture(scope="class")
    def msft_xbrl(self):
        from pathlib import Path
        from edgar.xbrl.xbrl import XBRL
        fixture_dir = Path("tests/fixtures/xbrl/msft/10k_2024")
        if not fixture_dir.exists() or not any(fixture_dir.iterdir()):
            pytest.skip("MSFT 10-K fixture not available")
        return XBRL.from_directory(fixture_dir)

    def test_segment_disclosure_dataframe_has_no_html(self, msft_xbrl):
        """The segment disclosure table DataFrame must not contain HTML."""
        stmt = msft_xbrl.statements.get('Role_DisclosureSEGMENTINFORMATIONANDGEOGRAPHICDATATables')
        if stmt is None:
            pytest.skip("Segment disclosure statement not found")

        df = stmt.to_dataframe()
        assert not df.empty

        for col in df.columns:
            for idx, val in df[col].items():
                if isinstance(val, str) and HTML_TAG_PATTERN.search(val):
                    pytest.fail(f"HTML in row {idx}, column '{col}': {val[:120]}...")

    def test_segment_disclosure_has_readable_text(self, msft_xbrl):
        """Sanitized TextBlock values should contain readable financial content."""
        stmt = msft_xbrl.statements.get('Role_DisclosureSEGMENTINFORMATIONANDGEOGRAPHICDATATables')
        if stmt is None:
            pytest.skip("Segment disclosure statement not found")

        df = stmt.to_dataframe()
        text_cells = []
        for col in df.columns:
            for val in df[col].dropna():
                if isinstance(val, str) and len(val) > 100:
                    text_cells.append(val)

        assert len(text_cells) > 0, "Expected TextBlock content in segment disclosure"
        combined = " ".join(text_cells).lower()
        assert any(kw in combined for kw in ["revenue", "segment", "geographic"]), (
            "Sanitized text should contain financial content"
        )
