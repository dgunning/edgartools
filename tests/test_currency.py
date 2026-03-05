"""
Tests for currency conversion utilities (edgar.xbrl.currency).

Tests the pure logic of ExchangeRate, _extract_year, and CurrencyConverter
conversion math without needing XBRL data or network calls.
"""

from datetime import date, datetime

import pytest

from edgar.xbrl.currency import ExchangeRate, CurrencyConverter, _extract_year


# ── _extract_year ────────────────────────────────────────────────────────────

class TestExtractYear:

    def test_string_date(self):
        assert _extract_year("2024-12-31") == 2024

    def test_date_object(self):
        assert _extract_year(date(2023, 6, 15)) == 2023

    def test_datetime_object(self):
        assert _extract_year(datetime(2022, 1, 1)) == 2022

    def test_none(self):
        assert _extract_year(None) is None

    def test_invalid_string(self):
        assert _extract_year("not-a-date") is None

    def test_empty_string(self):
        assert _extract_year("") is None


# ── ExchangeRate ─────────────────────────────────────────────────────────────

class TestExchangeRate:

    def test_creation(self):
        rate = ExchangeRate(year=2024, average=689.0, closing=714.0)
        assert rate.year == 2024
        assert rate.average == 689.0
        assert rate.closing == 714.0

    def test_repr_both_rates(self):
        rate = ExchangeRate(year=2024, average=689.0, closing=714.0)
        r = repr(rate)
        assert "2024" in r
        assert "avg=689.0" in r
        assert "close=714.0" in r

    def test_repr_average_only(self):
        rate = ExchangeRate(year=2024, average=689.0)
        r = repr(rate)
        assert "avg=689.0" in r
        assert "close" not in r

    def test_defaults_to_none(self):
        rate = ExchangeRate(year=2024)
        assert rate.average is None
        assert rate.closing is None


# ── CurrencyConverter math (bypass __post_init__) ────────────────────────────

@pytest.fixture
def dkk_converter():
    """DKK converter with pre-set rates (no XBRL needed)."""
    # Bypass __post_init__ by creating and manually setting fields
    converter = object.__new__(CurrencyConverter)
    converter.home_currency = "DKK"
    converter.target_currency = "USD"
    converter._rate_scale = 100.0  # DKK per 100 USD
    converter.exchange_rates = {
        2024: ExchangeRate(year=2024, average=689.0, closing=714.0),
        2023: ExchangeRate(year=2023, average=685.0, closing=690.0),
    }
    return converter


@pytest.fixture
def eur_converter():
    """EUR converter with direct rate scale."""
    converter = object.__new__(CurrencyConverter)
    converter.home_currency = "EUR"
    converter.target_currency = "USD"
    converter._rate_scale = 1.0  # Direct rate
    converter.exchange_rates = {
        2024: ExchangeRate(year=2024, average=1.08, closing=1.10),
    }
    return converter


class TestCurrencyConverterMath:

    def test_to_usd_average(self, dkk_converter):
        # 689 DKK per 100 USD → 1 DKK = 100/689 USD
        result = dkk_converter.to_usd(689_000, 2024, rate_type='average')
        assert abs(result - 100_000) < 1  # 689K DKK ≈ 100K USD

    def test_to_usd_closing(self, dkk_converter):
        result = dkk_converter.to_usd(714_000, 2024, rate_type='closing')
        assert abs(result - 100_000) < 1

    def test_from_usd(self, dkk_converter):
        result = dkk_converter.from_usd(100_000, 2024, rate_type='average')
        assert abs(result - 689_000) < 1

    def test_missing_year_returns_none(self, dkk_converter):
        assert dkk_converter.to_usd(100, 2020) is None
        assert dkk_converter.from_usd(100, 2020) is None

    def test_invalid_rate_type_raises(self, dkk_converter):
        with pytest.raises(ValueError, match="rate_type"):
            dkk_converter.to_usd(100, 2024, rate_type='spot')
        with pytest.raises(ValueError, match="rate_type"):
            dkk_converter.from_usd(100, 2024, rate_type='spot')

    def test_direct_rate_scale(self, eur_converter):
        # 1.08 EUR per USD → 108 EUR = 100 USD
        result = eur_converter.to_usd(108, 2024, rate_type='average')
        assert abs(result - 100) < 0.1

    def test_get_rate(self, dkk_converter):
        assert dkk_converter.get_rate(2024, 'average') == 689.0
        assert dkk_converter.get_rate(2024, 'closing') == 714.0
        assert dkk_converter.get_rate(2020) is None

    def test_available_years(self, dkk_converter):
        assert dkk_converter.available_years == [2024, 2023]

    def test_has_rates(self, dkk_converter):
        assert dkk_converter.has_rates is True

    def test_is_foreign_filer(self, dkk_converter):
        assert dkk_converter.is_foreign_filer is True

    def test_repr_with_rates(self, dkk_converter):
        r = repr(dkk_converter)
        assert "DKK" in r
        assert "USD" in r
        assert "2024" in r

    def test_repr_no_rates(self):
        converter = object.__new__(CurrencyConverter)
        converter.home_currency = "JPY"
        converter.target_currency = "USD"
        converter._rate_scale = 100.0
        converter.exchange_rates = {}
        assert "no rates found" in repr(converter)

    def test_rate_with_none_average(self):
        """Converter handles rate with only closing, no average."""
        converter = object.__new__(CurrencyConverter)
        converter.home_currency = "GBP"
        converter.target_currency = "USD"
        converter._rate_scale = 1.0
        converter.exchange_rates = {
            2024: ExchangeRate(year=2024, closing=0.79),
        }
        assert converter.to_usd(100, 2024, rate_type='average') is None
        assert converter.to_usd(79, 2024, rate_type='closing') == pytest.approx(100, abs=0.1)
