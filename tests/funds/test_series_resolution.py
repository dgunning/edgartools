"""
Tests for series resolution functionality (FEAT-417).
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from edgar.funds.series_resolution import SeriesInfo, TickerSeriesResolver


class TestSeriesInfo:
    """Test SeriesInfo dataclass"""

    @pytest.mark.fast
    def test_series_info_creation(self):
        """Test creating SeriesInfo with all fields"""
        series_info = SeriesInfo(
            series_id="S000001234",
            series_name="Test Fund Series",
            ticker="TESTX",
            class_id="C000005678",
            class_name="Test Class"
        )

        assert series_info.series_id == "S000001234"
        assert series_info.series_name == "Test Fund Series"
        assert series_info.ticker == "TESTX"
        assert series_info.class_id == "C000005678"
        assert series_info.class_name == "Test Class"

    @pytest.mark.fast
    def test_series_info_minimal_creation(self):
        """Test creating SeriesInfo with minimal fields"""
        series_info = SeriesInfo(
            series_id="S000001234",
            series_name=None,
            ticker="TESTX"
        )

        assert series_info.series_id == "S000001234"
        assert series_info.series_name is None
        assert series_info.ticker == "TESTX"
        assert series_info.class_id is None
        assert series_info.class_name is None


class TestTickerSeriesResolver:
    """Test TickerSeriesResolver functionality"""

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_resolve_ticker_single_series(self, mock_get_tickers):
        """Test resolving ticker to single series"""
        # Mock data with single match
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'TESTX'
            }
        ])
        mock_get_tickers.return_value = mock_df

        result = TickerSeriesResolver.resolve_ticker_to_series("TESTX")

        assert len(result) == 1
        assert result[0].series_id == "S000001234"
        assert result[0].ticker == "TESTX"
        assert result[0].class_id == "C000005678"

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_resolve_ticker_multiple_series(self, mock_get_tickers):
        """Test resolving ticker to multiple series"""
        # Clear cache to prevent contamination from other tests
        TickerSeriesResolver.resolve_ticker_to_series.cache_clear()

        # Mock data with multiple matches
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'GRID'
            },
            {
                'cik': 12345,
                'seriesId': 'S000002345',
                'classId': 'C000006789',
                'ticker': 'GRID'
            }
        ])
        mock_get_tickers.return_value = mock_df

        result = TickerSeriesResolver.resolve_ticker_to_series("GRID")

        assert len(result) == 2
        assert result[0].series_id == "S000001234"
        assert result[1].series_id == "S000002345"
        assert all(info.ticker == "GRID" for info in result)

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_resolve_ticker_no_match(self, mock_get_tickers):
        """Test resolving ticker with no matches"""
        # Mock data with no matches
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'OTHER'
            }
        ])
        mock_get_tickers.return_value = mock_df

        result = TickerSeriesResolver.resolve_ticker_to_series("NOTFOUND")

        assert len(result) == 0

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_resolve_ticker_case_insensitive(self, mock_get_tickers):
        """Test ticker resolution is case insensitive"""
        # Mock data
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'TESTX'
            }
        ])
        mock_get_tickers.return_value = mock_df

        # Test lowercase input
        result = TickerSeriesResolver.resolve_ticker_to_series("testx")

        assert len(result) == 1
        assert result[0].ticker == "TESTX"

    @pytest.mark.fast
    def test_resolve_ticker_empty_input(self):
        """Test handling of empty ticker input"""
        result = TickerSeriesResolver.resolve_ticker_to_series("")
        assert len(result) == 0

        result = TickerSeriesResolver.resolve_ticker_to_series(None)
        assert len(result) == 0

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_resolve_ticker_exception_handling(self, mock_get_tickers):
        """Test graceful handling of exceptions"""
        # Clear cache to ensure fresh test
        TickerSeriesResolver.resolve_ticker_to_series.cache_clear()

        mock_get_tickers.side_effect = Exception("API Error")

        with patch('edgar.funds.series_resolution.log') as mock_log:
            result = TickerSeriesResolver.resolve_ticker_to_series("UNIQUETEST")

            assert len(result) == 0
            mock_log.warning.assert_called_once()

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_get_primary_series_single_match(self, mock_resolve):
        """Test getting primary series with single match"""
        mock_resolve.return_value = [
            SeriesInfo(series_id="S000001234", series_name=None, ticker="TESTX")
        ]

        result = TickerSeriesResolver.get_primary_series("TESTX")

        assert result == "S000001234"

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_get_primary_series_multiple_matches(self, mock_resolve):
        """Test getting primary series with multiple matches"""
        mock_resolve.return_value = [
            SeriesInfo(series_id="S000001234", series_name=None, ticker="GRID"),
            SeriesInfo(series_id="S000002345", series_name=None, ticker="GRID")
        ]

        result = TickerSeriesResolver.get_primary_series("GRID")

        # Should return the first series
        assert result == "S000001234"

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_get_primary_series_no_match(self, mock_resolve):
        """Test getting primary series with no matches"""
        mock_resolve.return_value = []

        result = TickerSeriesResolver.get_primary_series("NOTFOUND")

        assert result is None

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_has_multiple_series_true(self, mock_resolve):
        """Test has_multiple_series returns True for multiple matches"""
        mock_resolve.return_value = [
            SeriesInfo(series_id="S000001234", series_name=None, ticker="GRID"),
            SeriesInfo(series_id="S000002345", series_name=None, ticker="GRID")
        ]

        result = TickerSeriesResolver.has_multiple_series("GRID")

        assert result is True

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_has_multiple_series_false(self, mock_resolve):
        """Test has_multiple_series returns False for single match"""
        mock_resolve.return_value = [
            SeriesInfo(series_id="S000001234", series_name=None, ticker="TESTX")
        ]

        result = TickerSeriesResolver.has_multiple_series("TESTX")

        assert result is False

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    def test_has_multiple_series_no_match(self, mock_resolve):
        """Test has_multiple_series returns False for no matches"""
        mock_resolve.return_value = []

        result = TickerSeriesResolver.has_multiple_series("NOTFOUND")

        assert result is False

    @pytest.mark.fast
    def test_caching_behavior(self):
        """Test that results are cached properly"""
        # Clear cache first
        TickerSeriesResolver.resolve_ticker_to_series.cache_clear()

        with patch('edgar.reference.tickers.get_mutual_fund_tickers') as mock_get_tickers:
            mock_df = pd.DataFrame([
                {
                    'cik': 12345,
                    'seriesId': 'S000001234',
                    'classId': 'C000005678',
                    'ticker': 'TESTX'
                }
            ])
            mock_get_tickers.return_value = mock_df

            # First call
            result1 = TickerSeriesResolver.resolve_ticker_to_series("TESTX")

            # Second call should use cache
            result2 = TickerSeriesResolver.resolve_ticker_to_series("TESTX")

            # Should only call the underlying function once due to caching
            assert mock_get_tickers.call_count == 1
            assert len(result1) == len(result2) == 1
            assert result1[0].series_id == result2[0].series_id