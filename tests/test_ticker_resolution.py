"""
Tests for ticker resolution functionality (FEAT-418).
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from edgar.funds.ticker_resolution import TickerResolutionResult, TickerResolutionService


class TestTickerResolutionResult:
    """Test TickerResolutionResult model"""

    def test_success_property_with_valid_ticker(self):
        """Test success property returns True for valid result"""
        result = TickerResolutionResult(
            ticker="AAPL",
            method="direct",
            confidence=1.0
        )
        assert result.success is True

    def test_success_property_with_no_ticker(self):
        """Test success property returns False when ticker is None"""
        result = TickerResolutionResult(
            ticker=None,
            method="failed",
            confidence=0.0
        )
        assert result.success is False

    def test_success_property_with_zero_confidence(self):
        """Test success property returns False with zero confidence"""
        result = TickerResolutionResult(
            ticker="AAPL",
            method="direct",
            confidence=0.0
        )
        assert result.success is False


class TestTickerResolutionService:
    """Test TickerResolutionService functionality"""

    def test_direct_ticker_resolution(self):
        """Test direct ticker resolution with highest confidence"""
        result = TickerResolutionService.resolve_ticker(ticker="AAPL")

        assert result.success is True
        assert result.ticker == "AAPL"
        assert result.method == "direct"
        assert result.confidence == 1.0

    def test_direct_ticker_normalization(self):
        """Test direct ticker is normalized to uppercase"""
        result = TickerResolutionService.resolve_ticker(ticker="  aapl  ")

        assert result.success is True
        assert result.ticker == "AAPL"
        assert result.method == "direct"

    def test_empty_ticker_fallback_to_cusip(self):
        """Test fallback to CUSIP when ticker is empty"""
        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.return_value = "MSFT"

            result = TickerResolutionService.resolve_ticker(
                ticker=None,
                cusip="594918104"
            )

            assert result.success is True
            assert result.ticker == "MSFT"
            assert result.method == "cusip"
            assert result.confidence == 0.85

    def test_cusip_resolution_failure(self):
        """Test CUSIP resolution returns failed when no match"""
        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.return_value = None

            result = TickerResolutionService.resolve_ticker(
                ticker=None,
                cusip="INVALID123"
            )

            assert result.success is False
            assert result.method == "failed"
            assert result.confidence == 0.0

    def test_invalid_cusip_handling(self):
        """Test handling of invalid CUSIP format"""
        result = TickerResolutionService.resolve_ticker(
            ticker=None,
            cusip="123"  # Too short
        )

        assert result.success is False
        assert result.method == "failed"

    def test_cusip_resolution_exception_handling(self):
        """Test graceful handling of CUSIP lookup exceptions"""
        # Clear cache to ensure fresh test
        TickerResolutionService.resolve_ticker.cache_clear()

        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.side_effect = Exception("API Error")

            result = TickerResolutionService.resolve_ticker(
                ticker=None,
                cusip="999999999"  # Use unique CUSIP to avoid cache collision
            )

            assert result.success is False
            assert result.method == "failed"

    def test_no_resolution_methods_available(self):
        """Test when no resolution methods succeed"""
        result = TickerResolutionService.resolve_ticker()

        assert result.success is False
        assert result.method == "failed"
        assert result.confidence == 0.0
        assert result.error_message == "No resolution methods succeeded"

    def test_caching_behavior(self):
        """Test that results are cached properly"""
        # Clear cache first
        TickerResolutionService.resolve_ticker.cache_clear()

        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.return_value = "MSFT"

            # First call
            result1 = TickerResolutionService.resolve_ticker(ticker=None, cusip="594918104")

            # Second call should use cache
            result2 = TickerResolutionService.resolve_ticker(ticker=None, cusip="594918104")

            # Should only call the underlying function once due to caching
            assert mock_cusip.call_count == 1
            assert result1.ticker == result2.ticker


class TestPrivateResolutionMethods:
    """Test private resolution methods"""

    def test_resolve_via_cusip_valid(self):
        """Test CUSIP resolution with valid CUSIP"""
        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.return_value = "GOOGL"

            result = TickerResolutionService._resolve_via_cusip("38259P508")

            assert result == "GOOGL"
            mock_cusip.assert_called_once_with("38259P508")

    def test_resolve_via_cusip_invalid(self):
        """Test CUSIP resolution with invalid CUSIP"""
        result = TickerResolutionService._resolve_via_cusip("")
        assert result is None

        result = TickerResolutionService._resolve_via_cusip("123")  # Too short
        assert result is None

    def test_resolve_via_cusip_normalization(self):
        """Test CUSIP normalization to uppercase"""
        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.return_value = "TSLA"

            result = TickerResolutionService._resolve_via_cusip("  88160r101  ")

            assert result == "TSLA"
            mock_cusip.assert_called_once_with("88160R101")

    def test_resolve_via_cusip_exception_handling(self):
        """Test exception handling in CUSIP resolution"""
        with patch('edgar.funds.ticker_resolution.get_ticker_from_cusip') as mock_cusip:
            mock_cusip.side_effect = Exception("Test exception")

            with patch('edgar.funds.ticker_resolution.log') as mock_log:
                result = TickerResolutionService._resolve_via_cusip("594918104")

                assert result is None
                mock_log.warning.assert_called_once()