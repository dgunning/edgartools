"""
Regression test for GitHub Issue #674: Fallback to FilingHomepage when SGML unavailable.

When the SEC returns empty content for a filing's .txt file and the direct-fetch retry
also fails, Filing.sgml() should fall back to constructing a minimal FilingSGML from
the filing's homepage index page rather than raising an exception.
"""
from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest

from edgar._filings import Filing
from edgar.attachments import Attachment, Attachments
from edgar.sgml.sgml_common import FilingSGML
from edgar.sgml.sgml_parser import SECIdentityError, SECFilingNotFoundError


class TestHomepageFallback:
    """Test that Filing.sgml() falls back to homepage on transient SGML errors."""

    def _make_filing(self):
        return Filing(form='10-K', company='TEST CORP', cik=12345,
                      filing_date='2024-01-15', accession_no='0000012345-24-000001')

    def test_sgml_falls_back_to_homepage_on_empty_response(self):
        """When SGML fetch raises ValueError, fall back to homepage."""
        filing = self._make_filing()

        mock_attachment = MagicMock(spec=Attachment)
        mock_attachment.document = "test-10k.htm"
        mock_attachments = MagicMock(spec=Attachments)
        mock_attachments.primary_html_document = mock_attachment

        mock_homepage = MagicMock()
        mock_homepage.attachments = mock_attachments

        with patch.object(FilingSGML, 'from_filing', side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")), \
             patch.object(type(filing), 'homepage', new_callable=lambda: property(lambda self: mock_homepage)):
            result = filing.sgml()

        assert result is not None
        assert result.attachments is mock_attachments

    def test_sgml_does_not_fallback_on_identity_error(self):
        """SECIdentityError should propagate, not fall back."""
        filing = self._make_filing()

        with patch.object(FilingSGML, 'from_filing', side_effect=SECIdentityError("identity not set")):
            with pytest.raises(SECIdentityError):
                filing.sgml()

    def test_sgml_does_not_fallback_on_filing_not_found(self):
        """SECFilingNotFoundError should propagate, not fall back."""
        filing = self._make_filing()

        with patch.object(FilingSGML, 'from_filing', side_effect=SECFilingNotFoundError("not found")):
            with pytest.raises(SECFilingNotFoundError):
                filing.sgml()

    def test_from_homepage_creates_minimal_filing_sgml(self):
        """FilingSGML.from_homepage() creates instance with homepage attachments."""
        mock_attachments = MagicMock(spec=Attachments)
        mock_homepage = MagicMock()
        mock_homepage.attachments = mock_attachments

        result = FilingSGML.from_homepage(mock_homepage)

        assert result is not None
        assert result.header.is_empty()
        assert result.attachments is mock_attachments

    def test_from_homepage_has_empty_documents(self):
        """FilingSGML from homepage has no in-memory documents."""
        mock_homepage = MagicMock()
        mock_homepage.attachments = MagicMock(spec=Attachments)

        result = FilingSGML.from_homepage(mock_homepage)

        assert result.get_document_count() == 0
        assert result.get_content("anything.htm") is None


class TestFallbackAPIs:
    """Test that APIs degrade gracefully when using homepage fallback."""

    def _make_filing_with_homepage_fallback(self):
        """Create a filing that will use homepage fallback for SGML."""
        filing = Filing(form='10-K', company='TEST CORP', cik=12345,
                        filing_date='2024-01-15', accession_no='0000012345-24-000001')
        return filing

    def test_xml_falls_back_to_homepage_attachment(self):
        """filing.xml() should download from homepage attachment when SGML has no in-memory docs."""
        filing = self._make_filing_with_homepage_fallback()

        # Create a mock XML attachment
        mock_xml_doc = MagicMock(spec=Attachment)
        mock_xml_doc.is_binary.return_value = False
        mock_xml_doc.empty = False
        mock_xml_doc.content = "<XML>test data</XML>"

        mock_homepage = MagicMock()
        mock_homepage.primary_xml_document = mock_xml_doc
        mock_homepage.attachments = MagicMock(spec=Attachments)

        # SGML returns None for xml (no in-memory docs), so Filing.xml() should fallback
        with patch.object(FilingSGML, 'from_filing', side_effect=ValueError("empty")), \
             patch.object(type(filing), 'homepage', new_callable=lambda: property(lambda self: mock_homepage)):
            result = filing.xml()

        assert result == "<XML>test data</XML>"

    def test_period_of_report_falls_back_to_homepage(self):
        """filing.period_of_report should use homepage when SGML header is empty."""
        filing = self._make_filing_with_homepage_fallback()

        mock_homepage = MagicMock()
        mock_homepage.period_of_report = "2024-01-15"
        mock_homepage.attachments = MagicMock(spec=Attachments)

        with patch.object(FilingSGML, 'from_filing', side_effect=ValueError("empty")), \
             patch.object(type(filing), 'homepage', new_callable=lambda: property(lambda self: mock_homepage)):
            result = filing.period_of_report

        assert result == "2024-01-15"

    def test_html_falls_back_to_homepage_download(self):
        """filing.html() already has homepage fallback - verify it works under SGML failure."""
        filing = self._make_filing_with_homepage_fallback()

        mock_html_doc = MagicMock(spec=Attachment)
        mock_html_doc.empty = False
        mock_html_doc.is_binary.return_value = False
        mock_html_doc.download.return_value = "<html><body>Test</body></html>"

        mock_homepage = MagicMock()
        mock_homepage.primary_html_document = mock_html_doc
        mock_homepage.attachments = MagicMock(spec=Attachments)
        # primary_html_document on attachments returns None so sgml.html() returns None
        mock_homepage.attachments.primary_html_document = None

        with patch.object(FilingSGML, 'from_filing', side_effect=ValueError("empty")), \
             patch.object(type(filing), 'homepage', new_callable=lambda: property(lambda self: mock_homepage)):
            result = filing.html()

        assert result == "<html><body>Test</body></html>"
