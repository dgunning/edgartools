"""
Regression test for Issue #519: HTTP 304 Not Modified breaking Company(ticker) lookup

Issue: https://github.com/dgunning/edgartools/issues/519
Beads: edgartools-4e1

Problem:
When SEC returns HTTP 304 "Not Modified" responses, the inspect_response() function
treated it as an error, causing Company(ticker) to fail with "Both data sources are unavailable".

Root Cause:
inspect_response() at httprequests.py:771 only accepted status code 200,
rejecting 304 which is a valid caching response.

Fix:
Updated inspect_response() to accept both 200 and 304 as successful responses.
"""
import pytest
from unittest.mock import Mock, patch
from httpx import Response

from edgar.httprequests import inspect_response, download_file, download_json


class TestIssue519Http304Handling:
    """Test that HTTP 304 Not Modified responses are handled correctly."""

    def test_inspect_response_accepts_200(self):
        """Verify inspect_response accepts HTTP 200 OK."""
        response = Mock(spec=Response)
        response.status_code = 200

        # Should not raise
        inspect_response(response)

    def test_inspect_response_accepts_304(self):
        """Verify inspect_response accepts HTTP 304 Not Modified."""
        response = Mock(spec=Response)
        response.status_code = 304

        # Should not raise - this was the bug
        inspect_response(response)

    def test_inspect_response_rejects_404(self):
        """Verify inspect_response rejects HTTP 404 Not Found."""
        response = Mock(spec=Response)
        response.status_code = 404
        response.raise_for_status = Mock(side_effect=Exception("404 Not Found"))

        # Should raise
        with pytest.raises(Exception, match="404 Not Found"):
            inspect_response(response)

    def test_inspect_response_rejects_500(self):
        """Verify inspect_response rejects HTTP 500 Server Error."""
        response = Mock(spec=Response)
        response.status_code = 500
        response.raise_for_status = Mock(side_effect=Exception("500 Server Error"))

        # Should raise
        with pytest.raises(Exception, match="500 Server Error"):
            inspect_response(response)

    @patch('edgar.httprequests.http_client')
    def test_download_file_handles_304(self, mock_http_client):
        """Test that download_file handles HTTP 304 responses correctly."""
        # Mock a 304 response with empty body (standard for 304)
        mock_response = Mock(spec=Response)
        mock_response.status_code = 304
        mock_response.text = ""  # 304 typically has no body
        mock_response.content = b""

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_http_client.return_value.__enter__.return_value = mock_client

        # Should not raise - download_file calls inspect_response
        result = download_file("https://example.com/test.txt", as_text=True)

        # 304 means "use your cached copy", so we get empty response
        assert result == ""

    @patch('edgar.httprequests.http_client')
    def test_download_json_handles_304(self, mock_http_client):
        """Test that download_json handles HTTP 304 responses correctly."""
        # Mock a 304 response
        mock_response = Mock(spec=Response)
        mock_response.status_code = 304
        mock_response.text = "{}"  # Minimal valid JSON

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_http_client.return_value.__enter__.return_value = mock_client

        # Should not raise - download_json calls inspect_response
        result = download_json("https://example.com/data.json")

        assert result == {}


class TestIssue519CompanyLookup:
    """Integration tests for Company ticker lookup with HTTP 304."""

    def test_company_ticker_lookup_with_304_response(self):
        """
        Test that inspect_response handles HTTP 304 correctly.

        This is the core fix: inspect_response() should accept 304 status codes
        instead of treating them as errors. The original bug caused Company("MSFT")
        to fail with "Both data sources are unavailable" when getting 304 responses.

        Note: We test the fix behavior directly here (304 acceptance) rather than
        mocking the full download chain, as the module-level caching makes mocking
        unreliable for the higher-level functions.
        """
        # Test that inspect_response accepts 304
        from edgar.httprequests import inspect_response

        mock_response = Mock(spec=Response)
        mock_response.status_code = 304

        # This should NOT raise - this is the core fix
        # Before the fix, this would call raise_for_status()
        try:
            inspect_response(mock_response)
        except Exception as e:
            pytest.fail(f"inspect_response should accept 304 status code, but raised: {e}")
