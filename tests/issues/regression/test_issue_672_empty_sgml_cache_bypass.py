"""
Regression test for GitHub Issue #672: Empty SGML responses cached forever.

When the SEC returns an empty response for a filing's SGML content, the HTTP cache
stores it forever (cache-forever rule for Archive data). The fix retries once using
a direct HTTP fetch (bypassing the cache entirely) when the SGML parser detects an
empty/truncated/error response.
"""
from unittest.mock import patch

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


class TestEmptySGMLCacheBypass:
    """Test that empty/truncated SGML responses trigger a direct-fetch retry."""

    def test_from_source_retries_on_empty_cached_response(self):
        """If cached fetch returns empty content, retry with direct fetch."""
        call_count = 0

        def mock_read_content(source, bypass_cache=False):
            nonlocal call_count
            call_count += 1
            return ""  # Simulate cached empty response

        def mock_direct_fetch(url):
            return VALID_SGML

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content), \
             patch("edgar.sgml.sgml_common._fetch_url_directly", side_effect=mock_direct_fetch):
            result = FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/1045810/000104581021000064/0001045810-21-000064.txt")

        assert call_count == 1, "Should have called read_content_as_string once"
        assert result.header is not None

    def test_from_source_retries_on_error_page_response(self):
        """If cached fetch returns SEC error page, retry with direct fetch."""
        def mock_read_content(source, bypass_cache=False):
            return "<html>SEC Error</html>"

        def mock_direct_fetch(url):
            return VALID_SGML

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content), \
             patch("edgar.sgml.sgml_common._fetch_url_directly", side_effect=mock_direct_fetch):
            result = FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/test.txt")

        assert result.header is not None

    def test_from_source_does_not_retry_for_local_files(self):
        """Cache bypass retry should only apply to URL sources, not local files."""
        def mock_read_content(source, bypass_cache=False):
            return ""

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            with pytest.raises(ValueError, match="empty or truncated"):
                FilingSGML.from_source("/tmp/some_file.txt")

    def test_from_source_does_not_retry_on_genuine_parse_error(self):
        """Non-transient errors (e.g., genuinely malformed SGML) should not trigger retry."""
        def mock_read_content(source, bypass_cache=False):
            return "x" * 200

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            with pytest.raises(ValueError, match="Unknown SGML format"):
                FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/test.txt")

    def test_direct_fetch_called_with_correct_url(self):
        """Verify _fetch_url_directly receives the original source URL."""
        captured_url = None

        def mock_read_content(source, bypass_cache=False):
            return ""

        def mock_direct_fetch(url):
            nonlocal captured_url
            captured_url = url
            return VALID_SGML

        test_url = "https://www.sec.gov/Archives/edgar/data/1045810/test.txt"
        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content), \
             patch("edgar.sgml.sgml_common._fetch_url_directly", side_effect=mock_direct_fetch):
            FilingSGML.from_source(test_url)

        assert captured_url == test_url
