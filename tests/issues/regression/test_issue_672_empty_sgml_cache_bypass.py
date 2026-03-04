"""
Regression test for GitHub Issue #672: Empty SGML responses cached forever.

When the SEC returns an empty response for a filing's SGML content, the HTTP cache
stores it forever (cache-forever rule for Archive data). The fix detects empty/truncated
content immediately after fetch and retries with a direct HTTP request that bypasses
the cache entirely.
"""
from unittest.mock import patch, call

import pytest

from edgar.sgml.sgml_common import FilingSGML


VALID_SGML = (
    "<SUBMISSION>\n"
    "<ACCESSION-NUMBER>0001045810-21-000064\n"
    "<TYPE>10-K\n"
    "<DOCUMENT>\n"
    "<TYPE>10-K\n"
    "<SEQUENCE>1\n"
    "<FILENAME>nvda20210131-10k.htm\n"
    "<TEXT>\n<html><body>Filing content</body></html>\n"
    "</TEXT>\n"
    "</DOCUMENT>\n"
    "</SUBMISSION>\n"
)

SEC_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000104581021000064/0001045810-21-000064.txt"


class TestEmptySGMLCacheBypass:
    """Test that empty/truncated cached responses trigger a direct-fetch retry."""

    def test_from_source_retries_on_empty_cached_response(self):
        """If cached fetch returns empty content, retry with direct fetch."""
        with patch("edgar.sgml.sgml_common.read_content_as_string", return_value="") as mock_read, \
             patch("edgar.sgml.sgml_common._fetch_url_directly", return_value=VALID_SGML) as mock_direct:
            result = FilingSGML.from_source(SEC_URL)

        mock_read.assert_called_once()
        mock_direct.assert_called_once_with(SEC_URL)
        assert result.header is not None

    def test_from_source_retries_on_truncated_cached_response(self):
        """Short content (< 50 bytes stripped) also triggers retry."""
        with patch("edgar.sgml.sgml_common.read_content_as_string", return_value="short") as mock_read, \
             patch("edgar.sgml.sgml_common._fetch_url_directly", return_value=VALID_SGML) as mock_direct:
            result = FilingSGML.from_source(SEC_URL)

        mock_direct.assert_called_once_with(SEC_URL)
        assert result.header is not None

    def test_from_source_does_not_retry_for_valid_content(self):
        """Valid SGML content should not trigger a retry."""
        with patch("edgar.sgml.sgml_common.read_content_as_string", return_value=VALID_SGML), \
             patch("edgar.sgml.sgml_common._fetch_url_directly") as mock_direct:
            result = FilingSGML.from_source(SEC_URL)

        mock_direct.assert_not_called()
        assert result.header is not None

    def test_from_source_does_not_retry_for_local_files(self):
        """Cache bypass retry should only apply to URL sources, not local files."""
        with patch("edgar.sgml.sgml_common.read_content_as_string", return_value=""), \
             patch("edgar.sgml.sgml_common._fetch_url_directly") as mock_direct:
            with pytest.raises(ValueError, match="empty or truncated"):
                FilingSGML.from_source("/tmp/some_file.txt")

        mock_direct.assert_not_called()

    def test_direct_fetch_called_with_correct_url(self):
        """Verify _fetch_url_directly receives the original source URL."""
        test_url = "https://www.sec.gov/Archives/edgar/data/1045810/test.txt"
        with patch("edgar.sgml.sgml_common.read_content_as_string", return_value=""), \
             patch("edgar.sgml.sgml_common._fetch_url_directly", return_value=VALID_SGML) as mock_direct:
            FilingSGML.from_source(test_url)

        mock_direct.assert_called_once_with(test_url)
