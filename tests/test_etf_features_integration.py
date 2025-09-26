"""
Integration tests for ETF features (FEAT-417 and FEAT-418).
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from decimal import Decimal

from edgar.funds.core import Fund
from edgar.funds.reports import FundReport, GeneralInfo, FundInfo, Header, FilerInfo, IssuerCredentials, InvestmentOrSecurity, Identifiers
from edgar.funds.ticker_resolution import TickerResolutionResult


class TestETFFeaturesIntegration:
    """Integration tests for both ETF series search and ticker resolution"""

    @patch('edgar.funds.series_resolution.get_mutual_fund_tickers')
    @patch('edgar.funds.core.find_fund')
    def test_fund_with_ticker_resolves_to_series(self, mock_find_fund, mock_get_tickers):
        """Test FEAT-417: Fund created with ticker resolves to correct series"""
        # Mock ticker to series resolution
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'GRID'
            }
        ])
        mock_get_tickers.return_value = mock_df

        # Mock fund entity
        mock_entity = MagicMock()
        mock_find_fund.return_value = mock_entity

        fund = Fund("GRID")

        assert fund._original_identifier == "GRID"
        assert fund._target_series_id == "S000001234"

    @patch('edgar.funds.series_resolution.get_mutual_fund_tickers')
    def test_fund_get_series_method(self, mock_get_tickers):
        """Test Fund.get_series() method"""
        # Mock ticker to series resolution
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'GRID'
            }
        ])
        mock_get_tickers.return_value = mock_df

        with patch('edgar.funds.core.find_fund') as mock_find_fund, \
             patch('edgar.funds.core.get_fund_series') as mock_get_fund_series:

            mock_entity = MagicMock()
            mock_find_fund.return_value = mock_entity

            mock_series = MagicMock()
            mock_get_fund_series.return_value = mock_series

            fund = Fund("GRID")
            series = fund.get_series()

            assert series == mock_series
            mock_get_fund_series.assert_called_once_with("S000001234")

    def test_fund_get_filings_with_series_only_parameter(self):
        """Test Fund.get_filings() with series_only parameter"""
        with patch('edgar.funds.core.find_fund') as mock_find_fund:
            mock_entity = MagicMock()
            mock_filings = MagicMock()
            mock_entity.get_filings.return_value = mock_filings
            mock_find_fund.return_value = mock_entity

            fund = Fund("GRID")
            fund._target_series_id = "S000001234"

            filings = fund.get_filings(series_only=True, form="NPORT-P")

            # Should still return filings (filtering not yet implemented)
            assert filings == mock_filings
            mock_entity.get_filings.assert_called_once_with(series_only=True, form="NPORT-P")


class TestFundReportTickerResolution:
    """Test FundReport integration with ticker resolution"""

    def create_mock_investment(self, name="Test Investment", cusip="123456789",
                               direct_ticker=None, resolved_ticker="AAPL"):
        """Helper to create mock investment with ticker resolution"""
        identifiers = Identifiers(ticker=direct_ticker, isin=None, other={})

        investment = InvestmentOrSecurity(
            name=name,
            lei="",
            title="Test Title",
            cusip=cusip,
            identifiers=identifiers,
            balance=Decimal('100'),
            units="Shares",
            desc_other_units=None,
            currency_code="USD",
            currency_conditional_code=None,
            exchange_rate=None,
            value_usd=Decimal('1000'),
            pct_value=Decimal('0.05'),
            payoff_profile=None,
            asset_category="Equity",
            issuer_category=None,
            investment_country="US",
            is_restricted_security=False,
            fair_value_level="1",
            debt_security=None,
            security_lending=None,
            derivative_info=None
        )

        # Mock the ticker resolution
        with patch.object(investment, 'ticker_resolution_info') as mock_resolution:
            mock_resolution.return_value = TickerResolutionResult(
                ticker=resolved_ticker,
                method="cusip" if not direct_ticker else "direct",
                confidence=0.85 if not direct_ticker else 1.0
            )
            yield investment

    @patch('edgar.reference.tickers.get_mutual_fund_tickers')
    def test_fund_report_get_ticker_for_series(self, mock_get_tickers):
        """Test FundReport.get_ticker_for_series() method"""
        # Mock mutual fund tickers data
        mock_df = pd.DataFrame([
            {
                'cik': 12345,
                'seriesId': 'S000001234',
                'classId': 'C000005678',
                'ticker': 'GRID'
            }
        ])
        mock_get_tickers.return_value = mock_df

        # Create mock fund report
        general_info = GeneralInfo(
            name="Test Fund",
            cik="0000012345",
            file_number="811-12345",
            reg_lei=None,
            street1="123 Main St",
            street2=None,
            city="New York",
            state="NY",
            country="US",
            zip_or_postal_code="10001",
            phone=None,
            series_name="Test Series",
            series_lei=None,
            series_id="S000001234",
            fiscal_year_end="12-31",
            rep_period_date="2024-03-31",
            is_final_filing=True
        )

        fund_report = FundReport(
            header=MagicMock(),
            general_info=general_info,
            fund_info=MagicMock(),
            investments=[]
        )

        ticker = fund_report.get_ticker_for_series()
        assert ticker == "GRID"

    def test_fund_report_matches_ticker(self):
        """Test FundReport.matches_ticker() method"""
        fund_report = MagicMock()
        fund_report.get_ticker_for_series.return_value = "GRID"

        # Import and test the method
        from edgar.funds.reports import FundReport
        result = FundReport.matches_ticker(fund_report, "GRID")
        assert result is True

        result = FundReport.matches_ticker(fund_report, "grid")  # Case insensitive
        assert result is True

        result = FundReport.matches_ticker(fund_report, "OTHER")
        assert result is False

    def test_investment_data_with_ticker_metadata(self):
        """Test investment_data() with ticker resolution metadata"""
        # Create mock investments
        with self.create_mock_investment(
            name="Apple Inc",
            cusip="037833100",
            direct_ticker=None,
            resolved_ticker="AAPL"
        ) as investment:

            fund_report = FundReport(
                header=MagicMock(),
                general_info=MagicMock(),
                fund_info=MagicMock(),
                investments=[investment]
            )

            # Test without metadata
            df = fund_report.investment_data(include_ticker_metadata=False)
            assert "ticker" in df.columns
            assert "ticker_resolution_method" not in df.columns
            assert "ticker_resolution_confidence" not in df.columns

            # Test with metadata
            df_with_meta = fund_report.investment_data(include_ticker_metadata=True)
            assert "ticker" in df_with_meta.columns
            assert "ticker_resolution_method" in df_with_meta.columns
            assert "ticker_resolution_confidence" in df_with_meta.columns

    def test_investment_ticker_property_uses_resolution(self):
        """Test that InvestmentOrSecurity.ticker uses resolution service"""
        with self.create_mock_investment(
            name="Microsoft Corp",
            cusip="594918104",
            direct_ticker=None,
            resolved_ticker="MSFT"
        ) as investment:

            # The ticker property should return the resolved ticker
            assert investment.ticker == "MSFT"

    def test_investment_ticker_resolution_info(self):
        """Test InvestmentOrSecurity.ticker_resolution_info property"""
        with self.create_mock_investment(
            name="Tesla Inc",
            cusip="88160R101",
            direct_ticker=None,
            resolved_ticker="TSLA"
        ) as investment:

            resolution_info = investment.ticker_resolution_info
            assert resolution_info.ticker == "TSLA"
            assert resolution_info.method == "cusip"
            assert resolution_info.confidence == 0.85


class TestBackwardCompatibility:
    """Test that new features don't break existing functionality"""

    def test_fund_creation_backward_compatible(self):
        """Test that Fund creation still works for existing patterns"""
        with patch('edgar.funds.core.find_fund') as mock_find_fund:
            mock_entity = MagicMock()
            mock_find_fund.return_value = mock_entity

            # Test various identifier types
            fund_cik = Fund("0000012345")
            fund_series = Fund("S000001234")
            fund_class = Fund("C000005678")

            assert all(f._entity == mock_entity for f in [fund_cik, fund_series, fund_class])

    def test_investment_data_backward_compatible(self):
        """Test that investment_data() maintains backward compatibility"""
        fund_report = FundReport(
            header=MagicMock(),
            general_info=MagicMock(),
            fund_info=MagicMock(),
            investments=[]
        )

        # Should work without new parameters
        df = fund_report.investment_data()
        assert isinstance(df, pd.DataFrame)

        # Should work with old parameters
        df = fund_report.investment_data(include_derivatives=False)
        assert isinstance(df, pd.DataFrame)

    def test_fund_report_methods_backward_compatible(self):
        """Test that existing FundReport methods still work"""
        general_info = GeneralInfo(
            name="Test Fund",
            cik="0000012345",
            file_number="811-12345",
            reg_lei=None,
            street1="123 Main St",
            street2=None,
            city="New York",
            state="NY",
            country="US",
            zip_or_postal_code="10001",
            phone=None,
            series_name="Test Series",
            series_lei=None,
            series_id="S000001234",
            fiscal_year_end="12-31",
            rep_period_date="2024-03-31",
            is_final_filing=True
        )

        fund_report = FundReport(
            header=MagicMock(),
            general_info=general_info,
            fund_info=MagicMock(),
            investments=[]
        )

        # Existing methods should still work
        assert fund_report.name == "Test Fund - Test Series"
        assert fund_report.reporting_period == "2024-03-31"
        series = fund_report.get_fund_series()
        assert series.series_id == "S000001234"