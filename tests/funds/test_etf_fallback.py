"""
Tests for ETF company fallback functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from edgar.funds.series_resolution import SeriesInfo, TickerSeriesResolver
from edgar.funds.core import Fund


class TestETFFallback:
    """Test ETF company fallback in series resolution"""

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    @patch('edgar.reference.tickers.find_cik')
    @patch('edgar.reference.tickers.get_company_tickers')
    def test_etf_fallback_resolution(self, mock_get_company_tickers, mock_find_cik, mock_get_mf_tickers):
        """Test that ETF tickers fall back to company data when not found in mutual fund data"""
        # Mock mutual fund data (empty - no matches)
        mock_get_mf_tickers.return_value = pd.DataFrame([
            {'cik': 12345, 'seriesId': 'S000001234', 'classId': 'C000005678', 'ticker': 'OTHERFUND'}
        ])

        # Mock CIK lookup (found)
        mock_find_cik.return_value = 884394  # SPY's actual CIK

        # Mock company data (SPY found)
        mock_get_company_tickers.return_value = pd.DataFrame([
            {'cik': 884394, 'ticker': 'SPY', 'company': 'SPDR S&P 500 ETF TRUST'}
        ])

        # Test resolution
        result = TickerSeriesResolver.resolve_ticker_to_series("SPY")

        # Should find one ETF series
        assert len(result) == 1
        assert result[0].series_id == "ETF_884394"
        assert result[0].series_name == "SPDR S&P 500 ETF TRUST"
        assert result[0].ticker == "SPY"
        assert result[0].class_id == "ETF_CLASS_884394"

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    @patch('edgar.reference.tickers.find_cik')
    def test_mutual_fund_priority_over_etf_fallback(self, mock_find_cik, mock_get_mf_tickers):
        """Test that mutual fund data is prioritized over ETF fallback"""
        # Mock mutual fund data (has match)
        mock_get_mf_tickers.return_value = pd.DataFrame([
            {'cik': 12345, 'seriesId': 'S000001234', 'classId': 'C000005678', 'ticker': 'VFINX'}
        ])

        # Test resolution
        result = TickerSeriesResolver.resolve_ticker_to_series("VFINX")

        # Should find mutual fund series, not call CIK lookup
        assert len(result) == 1
        assert result[0].series_id == "S000001234"
        assert not result[0].series_id.startswith("ETF_")

        # CIK lookup should not be called since mutual fund data was found
        mock_find_cik.assert_not_called()

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    @patch('edgar.reference.tickers.find_cik')
    def test_no_fallback_when_cik_not_found(self, mock_find_cik, mock_get_mf_tickers):
        """Test that no fallback occurs when ticker not found anywhere"""
        # Mock mutual fund data (no matches)
        mock_get_mf_tickers.return_value = pd.DataFrame([
            {'cik': 12345, 'seriesId': 'S000001234', 'classId': 'C000005678', 'ticker': 'OTHERFUND'}
        ])

        # Mock CIK lookup (not found)
        mock_find_cik.return_value = None

        # Test resolution
        result = TickerSeriesResolver.resolve_ticker_to_series("NOTFOUND")

        # Should return empty list
        assert len(result) == 0

    @pytest.mark.fast
    def test_get_primary_series_with_etf(self):
        """Test get_primary_series works with ETF synthetic series IDs"""
        with patch.object(TickerSeriesResolver, 'resolve_ticker_to_series') as mock_resolve:
            mock_resolve.return_value = [
                SeriesInfo(series_id="ETF_884394", series_name="SPDR S&P 500 ETF TRUST", ticker="SPY")
            ]

            result = TickerSeriesResolver.get_primary_series("SPY")
            assert result == "ETF_884394"


class TestFundETFIntegration:
    """Test Fund class integration with ETF fallback"""

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    @patch('edgar.funds.core.find_fund')
    def test_fund_etf_series_creation(self, mock_find_fund, mock_resolve):
        """Test that Fund can create ETF series properly"""
        # Mock the resolution to return ETF series
        mock_resolve.return_value = [
            SeriesInfo(series_id="ETF_884394", series_name="SPDR S&P 500 ETF TRUST", ticker="SPY")
        ]

        # Mock find_fund to return a basic entity
        mock_entity = MagicMock()
        mock_find_fund.return_value = mock_entity

        # Create Fund
        fund = Fund("SPY")

        # Should have ETF target series ID
        assert fund._target_series_id == "ETF_884394"

        # Should be able to get ETF series
        series = fund.get_series()
        assert series is not None
        assert series.series_id == "ETF_884394"
        assert series.name == "SPDR S&P 500 ETF TRUST"

    @pytest.mark.fast
    @patch('edgar.funds.series_resolution.TickerSeriesResolver.resolve_ticker_to_series')
    @patch('edgar.funds.core.find_fund')
    def test_fund_resolution_diagnostics_etf(self, mock_find_fund, mock_resolve):
        """Test resolution diagnostics for ETF"""
        # Mock the resolution to return ETF series
        mock_resolve.return_value = [
            SeriesInfo(series_id="ETF_884394", series_name="SPDR S&P 500 ETF TRUST", ticker="SPY")
        ]

        # Mock find_fund
        mock_entity = MagicMock()
        mock_find_fund.return_value = mock_entity

        # Create Fund
        fund = Fund("SPY")

        # Test diagnostics
        diagnostics = fund.get_resolution_diagnostics()
        assert diagnostics['status'] == 'success'
        assert diagnostics['method'] == 'etf_company_fallback'
        assert diagnostics['series_id'] == 'ETF_884394'
        assert diagnostics['cik'] == 884394
        assert diagnostics['original_identifier'] == 'SPY'

    @pytest.mark.fast
    @patch('edgar.reference.tickers.find_cik')
    @patch('edgar.funds.core.find_fund')
    def test_fund_resolution_diagnostics_partial_success(self, mock_find_fund, mock_find_cik):
        """Test resolution diagnostics for partial success (CIK found but no series)"""
        # Mock CIK lookup (found)
        mock_find_cik.return_value = 884394

        # Mock find_fund
        mock_entity = MagicMock()
        mock_find_fund.return_value = mock_entity

        # Create Fund that doesn't resolve to series
        fund = Fund("UNRESOLVED")
        fund._target_series_id = None  # Simulate no series resolution

        # Test diagnostics
        diagnostics = fund.get_resolution_diagnostics()
        assert diagnostics['status'] == 'partial_success'
        assert diagnostics['method'] == 'company_lookup_unresolved'
        assert diagnostics['cik'] == 884394
        assert 'suggestion' in diagnostics

    @pytest.mark.fast
    @patch('edgar.reference.tickers.find_cik')
    @patch('edgar.funds.core.find_fund')
    def test_fund_resolution_diagnostics_failed(self, mock_find_fund, mock_find_cik):
        """Test resolution diagnostics for complete failure"""
        # Mock CIK lookup (not found)
        mock_find_cik.return_value = None

        # Mock find_fund
        mock_entity = MagicMock()
        mock_find_fund.return_value = mock_entity

        # Create Fund that doesn't resolve at all
        fund = Fund("NOTFOUND")
        fund._target_series_id = None

        # Test diagnostics
        diagnostics = fund.get_resolution_diagnostics()
        assert diagnostics['status'] == 'failed'
        assert diagnostics['method'] == 'no_resolution'
        assert 'suggestion' in diagnostics


class TestETFFallbackEdgeCases:
    """Test edge cases in ETF fallback"""

    @pytest.mark.fast
    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    @patch('edgar.reference.tickers.find_cik')
    @patch('edgar.reference.tickers.get_company_tickers')
    def test_etf_fallback_with_missing_company_data(self, mock_get_company_tickers, mock_find_cik, mock_get_mf_tickers):
        """Test ETF fallback when company data doesn't match CIK"""
        # Clear cache to prevent contamination from other tests
        TickerSeriesResolver.resolve_ticker_to_series.cache_clear()

        # Mock mutual fund data (empty with proper columns)
        mock_get_mf_tickers.return_value = pd.DataFrame(columns=['cik', 'seriesId', 'classId', 'ticker'])

        # Mock CIK lookup (found)
        mock_find_cik.return_value = 884394

        # Mock company data (empty - no matching records)
        mock_get_company_tickers.return_value = pd.DataFrame([
            {'cik': 999999, 'ticker': 'OTHER', 'company': 'Other Company'}
        ])

        # Test resolution
        result = TickerSeriesResolver.resolve_ticker_to_series("SPY")

        # Should return empty since company data doesn't match
        assert len(result) == 0

    @pytest.mark.fast
    def test_etf_fallback_caching(self):
        """Test that ETF fallback results are cached properly"""
        # Clear cache
        TickerSeriesResolver.resolve_ticker_to_series.cache_clear()

        with patch('edgar.reference.tickers.get_mutual_fund_tickers') as mock_mf, \
             patch('edgar.reference.tickers.find_cik') as mock_cik, \
             patch('edgar.reference.tickers.get_company_tickers') as mock_company:

            # Setup mocks - empty DataFrame with proper columns
            mock_mf.return_value = pd.DataFrame(columns=['cik', 'seriesId', 'classId', 'ticker'])
            mock_cik.return_value = 884394
            mock_company.return_value = pd.DataFrame([
                {'cik': 884394, 'ticker': 'SPY', 'company': 'SPDR S&P 500 ETF TRUST'}
            ])

            # First call
            result1 = TickerSeriesResolver.resolve_ticker_to_series("SPY")

            # Second call should use cache
            result2 = TickerSeriesResolver.resolve_ticker_to_series("SPY")

            # Should only call mocks once due to caching
            assert mock_mf.call_count == 1
            assert mock_cik.call_count == 1
            assert mock_company.call_count == 1

            # Results should be identical
            assert len(result1) == len(result2) == 1
            assert result1[0].series_id == result2[0].series_id