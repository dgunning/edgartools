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

    @patch('edgar.httprequests.http_client')
    def test_company_ticker_lookup_with_304_response(self, mock_http_client):
        """
        Test that Company(ticker) works when SEC returns HTTP 304.

        This is the actual user-facing bug: Company("MSFT") failed with
        "Both data sources are unavailable" when getting 304 responses.
        """
        # Mock 304 response for ticker.txt
        mock_response_txt = Mock(spec=Response)
        mock_response_txt.status_code = 304
        mock_response_txt.text = "msft\t789019\n"

        # Mock 304 response for company_tickers.json
        mock_response_json = Mock(spec=Response)
        mock_response_json.status_code = 304
        mock_response_json.text = '{"0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"}}'

        mock_client = Mock()
        # First call returns txt response, second returns json response
        mock_client.get.side_effect = [mock_response_txt, mock_response_json]
        mock_http_client.return_value.__enter__.return_value = mock_client

        # This should not raise - before the fix, this would fail with
        # "Both data sources are unavailable"
        from edgar.reference.tickers import get_cik_tickers_from_ticker_txt, get_company_tickers

        # Test ticker.txt download
        ticker_data = get_cik_tickers_from_ticker_txt()
        assert ticker_data is not None

        # Test company_tickers.json download
        company_data = get_company_tickers()
        assert company_data is not None
