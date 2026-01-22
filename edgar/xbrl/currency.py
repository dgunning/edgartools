"""
Currency conversion utilities for foreign filers (IFRS).

Foreign filers (like NVO, BNTX) report financials in their home currency
(DKK, EUR, etc.) rather than USD. IFRS filings typically include exchange
rate data that can be extracted for conversion.

Example usage:
    from edgar import Company
    from edgar.xbrl.currency import CurrencyConverter

    nvo = Company("NVO")
    filing = nvo.get_filings(form="20-F").latest()
    xbrl = filing.xbrl()

    converter = CurrencyConverter(xbrl)
    print(converter)
    # CurrencyConverter(home=DKK, target=USD)
    #   Rates (DKK per 100 USD):
    #     2024: avg=689.0, close=714.0

    # Convert values
    dkk_revenue = 290_400_000_000
    usd_revenue = converter.to_usd(dkk_revenue, 2024, rate_type='average')
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Union

if TYPE_CHECKING:
    from edgar.xbrl import XBRL


def _extract_year(value) -> Optional[int]:
    """Extract year from a date value (handles strings, dates, timestamps)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            # Parse YYYY-MM-DD format
            return int(value.split('-')[0])
        except (ValueError, IndexError):
            return None
    if hasattr(value, 'year'):
        return value.year
    return None

__all__ = ['CurrencyConverter', 'ExchangeRate']


@dataclass
class ExchangeRate:
    """Exchange rate for a specific year."""
    year: int
    average: Optional[float] = None  # For income statement / cash flow
    closing: Optional[float] = None  # For balance sheet

    def __repr__(self) -> str:
        parts = []
        if self.average is not None:
            parts.append(f"avg={self.average}")
        if self.closing is not None:
            parts.append(f"close={self.closing}")
        return f"ExchangeRate({self.year}: {', '.join(parts)})"


@dataclass
class CurrencyConverter:
    """
    Currency converter for foreign filers using exchange rates from XBRL filings.

    This class extracts exchange rates from IFRS filings and provides methods
    to convert monetary values from the home currency to USD.

    Attributes:
        xbrl: The XBRL instance to extract rates from
        home_currency: The detected home currency (e.g., 'DKK', 'EUR')
        target_currency: The target currency for conversion (default: 'USD')
        exchange_rates: Dict mapping year to ExchangeRate objects

    Example:
        >>> converter = CurrencyConverter(xbrl)
        >>> converter.home_currency
        'DKK'
        >>> converter.to_usd(1_000_000, 2024, rate_type='average')
        1451.38
    """
    xbrl: 'XBRL'
    home_currency: str = field(default="", init=False)
    target_currency: str = "USD"
    exchange_rates: Dict[int, ExchangeRate] = field(default_factory=dict, init=False)
    _rate_scale: float = field(default=100.0, init=False)  # Rates are per 100 USD

    def __post_init__(self):
        """Initialize by detecting currency and extracting rates."""
        self.home_currency = self._detect_home_currency()
        self.exchange_rates = self._extract_exchange_rates()

    def _detect_home_currency(self) -> str:
        """
        Detect the home (reporting) currency from the most common currency in facts.

        Returns:
            ISO 4217 currency code (e.g., 'DKK', 'EUR', 'GBP')
        """
        facts_df = self.xbrl.facts.to_dataframe()
        currency_counts: Counter = Counter()

        for _, row in facts_df.iterrows():
            unit_ref = row.get('unit_ref')
            if unit_ref and unit_ref in self.xbrl.units:
                unit_info = self.xbrl.units[unit_ref]
                if unit_info.get('type') == 'simple':
                    measure = unit_info.get('measure', '')
                    if measure.startswith('iso4217:'):
                        currency = measure.replace('iso4217:', '')
                        currency_counts[currency] += 1

        if not currency_counts:
            return "USD"  # Default if no currency facts found

        # Return most common currency
        return currency_counts.most_common(1)[0][0]

    def _extract_exchange_rates(self) -> Dict[int, ExchangeRate]:
        """
        Extract exchange rates from IFRS concepts in the filing.

        Looks for:
        - ifrs-full:AverageForeignExchangeRate (for income statement)
        - ifrs-full:ClosingForeignExchangeRate (for balance sheet)

        Handles two common patterns:
        1. Currency-specific units like 'dkkPerUSD' with rates per 100 USD
        2. Pure ratio units ('number', 'pure') with direct exchange rates

        Returns:
            Dict mapping year to ExchangeRate objects
        """
        rates: Dict[int, ExchangeRate] = {}

        # Build the expected unit_ref pattern for home currency to USD
        # e.g., 'dkkPerUSD', 'eurPerUSD'
        home_lower = self.home_currency.lower()
        target_upper = self.target_currency.upper()
        expected_unit_patterns = [
            f"{home_lower}Per{target_upper}",
            f"{home_lower}_{target_upper}",
            f"{home_lower}{target_upper}",
        ]

        # Also accept pure ratio units (some filers use 'number' or 'pure')
        pure_unit_patterns = ['number', 'pure', 'ratio']

        def is_valid_rate_unit(unit_ref: str) -> bool:
            """Check if unit_ref indicates a valid exchange rate."""
            if any(pattern in unit_ref for pattern in expected_unit_patterns):
                return True
            if unit_ref.lower() in pure_unit_patterns:
                return True
            return False

        # Extract average rates (for income statement / duration periods)
        try:
            avg_df = self.xbrl.facts.query().by_concept(
                'ifrs-full:AverageForeignExchangeRate', exact=True
            ).to_dataframe()

            if not avg_df.empty:
                for _, row in avg_df.iterrows():
                    unit_ref = row.get('unit_ref', '')
                    if is_valid_rate_unit(unit_ref):
                        period_end = row.get('period_end')
                        year = _extract_year(period_end)
                        if year:
                            value = row.get('numeric_value')
                            if year not in rates:
                                rates[year] = ExchangeRate(year=year)
                            rates[year].average = value
        except Exception:
            pass  # No average rates found

        # Extract closing rates (for balance sheet / instant periods)
        try:
            close_df = self.xbrl.facts.query().by_concept(
                'ifrs-full:ClosingForeignExchangeRate', exact=True
            ).to_dataframe()

            if not close_df.empty:
                for _, row in close_df.iterrows():
                    unit_ref = row.get('unit_ref', '')
                    if is_valid_rate_unit(unit_ref):
                        # For instant periods, check period_end first (closing rate date)
                        period_date = row.get('period_end') or row.get('period_instant')
                        year = _extract_year(period_date)
                        if year:
                            value = row.get('numeric_value')
                            if year not in rates:
                                rates[year] = ExchangeRate(year=year)
                            rates[year].closing = value
        except Exception:
            pass  # No closing rates found

        # Auto-detect rate scale by checking if rates look like "per 100" or direct
        # Rates > 10 are likely "per 100 USD" format, rates < 10 are direct rates
        if rates:
            sample_rate = next(iter(rates.values()))
            rate_value = sample_rate.average or sample_rate.closing
            if rate_value and rate_value < 10:
                # Direct rate format (e.g., 1.08 EUR per USD)
                self._rate_scale = 1.0
            else:
                # Per 100 format (e.g., 689 DKK per 100 USD)
                self._rate_scale = 100.0

        return rates

    def to_usd(
        self,
        value: Union[int, float],
        year: int,
        rate_type: str = 'average'
    ) -> Optional[float]:
        """
        Convert a value from home currency to USD.

        Args:
            value: The value in home currency to convert
            year: The fiscal year for the exchange rate
            rate_type: 'average' for income statement items (default),
                      'closing' for balance sheet items

        Returns:
            The value converted to USD, or None if rate not available

        Example:
            >>> converter.to_usd(290_400_000_000, 2024, rate_type='average')
            42147026122.27
        """
        if year not in self.exchange_rates:
            return None

        rate_obj = self.exchange_rates[year]

        if rate_type == 'average':
            rate = rate_obj.average
        elif rate_type == 'closing':
            rate = rate_obj.closing
        else:
            raise ValueError(f"rate_type must be 'average' or 'closing', got '{rate_type}'")

        if rate is None:
            return None

        # Rate is "home currency per 100 USD"
        # To convert: USD = home_value / (rate / 100)
        return value / (rate / self._rate_scale)

    def from_usd(
        self,
        value: Union[int, float],
        year: int,
        rate_type: str = 'average'
    ) -> Optional[float]:
        """
        Convert a value from USD to home currency.

        Args:
            value: The value in USD to convert
            year: The fiscal year for the exchange rate
            rate_type: 'average' for income statement items (default),
                      'closing' for balance sheet items

        Returns:
            The value converted to home currency, or None if rate not available
        """
        if year not in self.exchange_rates:
            return None

        rate_obj = self.exchange_rates[year]

        if rate_type == 'average':
            rate = rate_obj.average
        elif rate_type == 'closing':
            rate = rate_obj.closing
        else:
            raise ValueError(f"rate_type must be 'average' or 'closing', got '{rate_type}'")

        if rate is None:
            return None

        # Rate is "home currency per 100 USD"
        # To convert: home = USD * (rate / 100)
        return value * (rate / self._rate_scale)

    @property
    def available_years(self) -> List[int]:
        """Get list of years with exchange rate data."""
        return sorted(self.exchange_rates.keys(), reverse=True)

    @property
    def has_rates(self) -> bool:
        """Check if any exchange rates were found."""
        return len(self.exchange_rates) > 0

    @property
    def is_foreign_filer(self) -> bool:
        """Check if this appears to be a foreign filer (non-USD reporting)."""
        return self.home_currency != "USD"

    def get_rate(self, year: int, rate_type: str = 'average') -> Optional[float]:
        """
        Get the exchange rate for a specific year.

        Args:
            year: The fiscal year
            rate_type: 'average' or 'closing'

        Returns:
            The exchange rate (home currency per 100 USD), or None if not available
        """
        if year not in self.exchange_rates:
            return None

        rate_obj = self.exchange_rates[year]
        if rate_type == 'average':
            return rate_obj.average
        elif rate_type == 'closing':
            return rate_obj.closing
        return None

    def __repr__(self) -> str:
        if not self.has_rates:
            return f"CurrencyConverter(home={self.home_currency}, target={self.target_currency}, no rates found)"

        lines = [f"CurrencyConverter(home={self.home_currency}, target={self.target_currency})"]

        # Format rate description based on scale
        if self._rate_scale == 100.0:
            rate_desc = f"{self.home_currency} per 100 {self.target_currency}"
        else:
            rate_desc = f"{self.home_currency} per {self.target_currency}"
        lines.append(f"  Rates ({rate_desc}):")

        for year in self.available_years:
            rate = self.exchange_rates[year]
            parts = []
            if rate.average is not None:
                parts.append(f"avg={rate.average:.4f}" if rate.average < 10 else f"avg={rate.average:.1f}")
            if rate.closing is not None:
                parts.append(f"close={rate.closing:.4f}" if rate.closing < 10 else f"close={rate.closing:.1f}")
            lines.append(f"    {year}: {', '.join(parts)}")

        return "\n".join(lines)

    def __rich__(self):
        """Rich display for the converter."""
        from rich.table import Table
        from rich import box

        table = Table(
            title=f"Currency Converter ({self.home_currency} → {self.target_currency})",
            box=box.SIMPLE
        )
        table.add_column("Year", style="bold")
        table.add_column("Average Rate", justify="right")
        table.add_column("Closing Rate", justify="right")

        for year in self.available_years:
            rate = self.exchange_rates[year]
            avg_str = f"{rate.average:.2f}" if rate.average is not None else "N/A"
            close_str = f"{rate.closing:.2f}" if rate.closing is not None else "N/A"
            table.add_row(str(year), avg_str, close_str)

        return table
