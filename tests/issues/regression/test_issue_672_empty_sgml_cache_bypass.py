"""
Regression test for GitHub Issue #672: Empty SGML responses cached forever.

When the SEC returns an empty response for a filing's SGML content, the HTTP cache
stores it forever (cache-forever rule for Archive data). The fix retries once with
cache bypass when the SGML parser detects an empty/truncated/error response.
"""
from collections import defaultdict
from unittest.mock import patch

import pytest

from edgar.sgml.sgml_common import FilingSGML, read_content_as_string
from edgar.sgml.sgml_parser import SECHTMLResponseError


class TestEmptySGMLCacheBypass:
    """Test that empty/truncated SGML responses trigger a cache-bypass retry."""

    def test_from_source_retries_on_empty_cached_response(self):
        """If first fetch returns empty content, retry with bypass_cache=True."""
        valid_sgml = (
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

        call_count = 0

        def mock_read_content(source, bypass_cache=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and not bypass_cache:
                # First call: simulate cached empty response
                return ""
            # Second call (with bypass_cache=True) or non-cached: return valid SGML
            return valid_sgml

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            result = FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/1045810/000104581021000064/0001045810-21-000064.txt")

        assert call_count == 2, "Should have retried once with cache bypass"
        assert result.header is not None

    def test_from_source_retries_on_error_page_response(self):
        """If first fetch returns SEC error page, retry with bypass_cache=True."""
        valid_sgml = (
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

        call_count = 0

        def mock_read_content(source, bypass_cache=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and not bypass_cache:
                # Simulate a short SEC error page
                return "<html>SEC Error</html>"
            return valid_sgml

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            result = FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/test.txt")

        assert call_count == 2, "Should have retried once with cache bypass"

    def test_from_source_does_not_retry_for_local_files(self):
        """Cache bypass retry should only apply to URL sources, not local files."""

        def mock_read_content(source, bypass_cache=False):
            return ""  # Empty content from local file

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            with pytest.raises(ValueError, match="empty or truncated"):
                FilingSGML.from_source("/tmp/some_file.txt")

    def test_from_source_does_not_retry_on_genuine_parse_error(self):
        """Non-transient errors (e.g., genuinely malformed SGML) should not trigger retry."""

        def mock_read_content(source, bypass_cache=False):
            # Return content that's long enough to not be "empty" but not valid SGML
            return "x" * 200

        with patch("edgar.sgml.sgml_common.read_content_as_string", side_effect=mock_read_content):
            with pytest.raises(ValueError, match="Unknown SGML format"):
                FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/test.txt")

    def test_read_content_as_string_passes_bypass_cache(self):
        """Verify bypass_cache parameter flows through to stream_with_retry."""
        with patch("edgar.sgml.sgml_common.stream_with_retry") as mock_stream:
            mock_stream.return_value = iter([])  # Empty iterator
            read_content_as_string("https://example.com/test.txt", bypass_cache=True)
            mock_stream.assert_called_once_with("https://example.com/test.txt", bypass_cache=True)
