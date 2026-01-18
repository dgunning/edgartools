"""Tests for the CurrencyConverter utility."""

import pytest
from edgar.xbrl.currency import CurrencyConverter, ExchangeRate, _extract_year


class TestExtractYear:
    """Tests for the _extract_year helper function."""

    def test_extract_year_from_string(self):
        assert _extract_year("2024-12-31") == 2024
        assert _extract_year("2023-01-01") == 2023

    def test_extract_year_from_none(self):
        assert _extract_year(None) is None

    def test_extract_year_from_invalid_string(self):
        assert _extract_year("invalid") is None
        assert _extract_year("") is None

    def test_extract_year_from_date_object(self):
        from datetime import date
        assert _extract_year(date(2024, 12, 31)) == 2024


class TestExchangeRate:
    """Tests for the ExchangeRate dataclass."""

    def test_exchange_rate_creation(self):
        rate = ExchangeRate(year=2024, average=689.0, closing=714.0)
        assert rate.year == 2024
        assert rate.average == 689.0
        assert rate.closing == 714.0

    def test_exchange_rate_repr(self):
        rate = ExchangeRate(year=2024, average=689.0, closing=714.0)
        assert "2024" in repr(rate)
        assert "avg=689.0" in repr(rate)
        assert "close=714.0" in repr(rate)

    def test_exchange_rate_partial(self):
        rate = ExchangeRate(year=2024, average=1.08)
        assert rate.year == 2024
        assert rate.average == 1.08
        assert rate.closing is None


class TestCurrencyConverterUnit:
    """Unit tests for CurrencyConverter (no network)."""

    def test_to_usd_conversion_per_100_format(self):
        """Test conversion with 'per 100 USD' format (like NVO DKK rates)."""
        # Mock a converter with known rates
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "DKK"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0, closing=714.0),
            2023: ExchangeRate(year=2023, average=689.0, closing=674.0),
        }

        # Test average rate conversion
        # 689 DKK per 100 USD means 1 USD = 6.89 DKK
        # So 1000 DKK = 1000 / 6.89 = ~145.14 USD
        result = converter.to_usd(1000, 2024, rate_type='average')
        assert result is not None
        assert abs(result - 145.14) < 0.1

        # Test closing rate conversion
        result = converter.to_usd(1000, 2024, rate_type='closing')
        assert result is not None
        assert abs(result - 140.06) < 0.1

    def test_to_usd_conversion_direct_format(self):
        """Test conversion with direct rate format (like BNTX EUR rates)."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "EUR"
        converter.target_currency = "USD"
        converter._rate_scale = 1.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=1.0824, closing=1.0389),
        }

        # 1.0824 EUR per USD means 1 USD = 1.0824 EUR
        # So 1000 EUR = 1000 / 1.0824 = ~923.85 USD
        result = converter.to_usd(1000, 2024, rate_type='average')
        assert result is not None
        assert abs(result - 923.85) < 0.1

    def test_to_usd_missing_year(self):
        """Test conversion returns None for missing year."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "DKK"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0),
        }

        result = converter.to_usd(1000, 2020, rate_type='average')
        assert result is None

    def test_to_usd_invalid_rate_type(self):
        """Test conversion raises for invalid rate_type."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "DKK"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0),
        }

        with pytest.raises(ValueError, match="rate_type must be"):
            converter.to_usd(1000, 2024, rate_type='invalid')

    def test_from_usd_conversion(self):
        """Test reverse conversion from USD."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "DKK"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0),
        }

        # 100 USD at 689 DKK per 100 USD = 689 DKK
        result = converter.from_usd(100, 2024, rate_type='average')
        assert result is not None
        assert abs(result - 689.0) < 0.01

    def test_available_years(self):
        """Test available_years returns sorted years."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024),
            2022: ExchangeRate(year=2022),
            2023: ExchangeRate(year=2023),
        }

        assert converter.available_years == [2024, 2023, 2022]

    def test_has_rates(self):
        """Test has_rates property."""
        converter = CurrencyConverter.__new__(CurrencyConverter)

        converter.exchange_rates = {}
        assert converter.has_rates is False

        converter.exchange_rates = {2024: ExchangeRate(year=2024)}
        assert converter.has_rates is True

    def test_is_foreign_filer(self):
        """Test is_foreign_filer property."""
        converter = CurrencyConverter.__new__(CurrencyConverter)

        converter.home_currency = "USD"
        assert converter.is_foreign_filer is False

        converter.home_currency = "EUR"
        assert converter.is_foreign_filer is True

    def test_get_rate(self):
        """Test get_rate method."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0, closing=714.0),
        }

        assert converter.get_rate(2024, 'average') == 689.0
        assert converter.get_rate(2024, 'closing') == 714.0
        assert converter.get_rate(2020, 'average') is None

    def test_repr_with_rates(self):
        """Test __repr__ includes rates."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "DKK"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, average=689.0, closing=714.0),
        }

        repr_str = repr(converter)
        assert "DKK" in repr_str
        assert "USD" in repr_str
        assert "2024" in repr_str
        assert "689" in repr_str

    def test_repr_no_rates(self):
        """Test __repr__ when no rates found."""
        converter = CurrencyConverter.__new__(CurrencyConverter)
        converter.home_currency = "EUR"
        converter.target_currency = "USD"
        converter.exchange_rates = {}

        repr_str = repr(converter)
        assert "no rates found" in repr_str


@pytest.mark.network
class TestCurrencyConverterIntegration:
    """Integration tests for CurrencyConverter (requires network)."""

    def test_nvo_converter(self):
        """Test CurrencyConverter with NVO (DKK reporting)."""
        from edgar import Company

        nvo = Company('NVO')
        filings = nvo.get_filings(form='20-F')
        if len(filings) == 0:
            pytest.skip("No 20-F filings found for NVO")

        filing = filings[0]
        xbrl = filing.xbrl()
        converter = CurrencyConverter(xbrl)

        assert converter.home_currency == "DKK"
        assert converter.is_foreign_filer is True
        assert converter.has_rates is True
        assert len(converter.available_years) >= 1

        # Test conversion (approximate NVO 2024 revenue)
        dkk_revenue = 290_400_000_000
        usd_revenue = converter.to_usd(dkk_revenue, 2024, rate_type='average')
        if usd_revenue:
            # Should be approximately $42B
            assert 40e9 < usd_revenue < 50e9

    def test_us_company_no_conversion_needed(self):
        """Test that US companies report in USD (no conversion needed)."""
        from edgar import Company

        aapl = Company('AAPL')
        filings = aapl.get_filings(form='10-K')
        if len(filings) == 0:
            pytest.skip("No 10-K filings found for AAPL")

        filing = filings[0]
        xbrl = filing.xbrl()
        converter = CurrencyConverter(xbrl)

        assert converter.home_currency == "USD"
        assert converter.is_foreign_filer is False
        # US companies don't have IFRS exchange rate facts
        assert converter.has_rates is False
