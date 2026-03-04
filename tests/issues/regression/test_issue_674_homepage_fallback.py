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
