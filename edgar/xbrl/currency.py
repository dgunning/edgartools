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

import pandas as pd

from edgar.core import log
from edgar.xbrl.core import unit_currency

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


def _first_date(row, *columns):
    """The first of ``columns`` that holds a value in ``row``.

    An empty cell in a facts frame is NaN, not None, and NaN is truthy, so
    ``row.get('period_end') or row.get('period_instant')`` returns NaN for an
    instant fact and never reaches its date (GH #1652).
    """
    for column in columns:
        value = row.get(column)
        if value is not None and not pd.isna(value):
            return value
    return None


def _local_name(qname: str) -> str:
    """``'currency:USD'`` -> ``'USD'``."""
    return qname.rsplit(':', 1)[-1]


# (ExchangeRate field, concept, date columns in order of preference)
_RATE_CONCEPTS = (
    ('average', 'ifrs-full:AverageForeignExchangeRate', ('period_end',)),
    # A closing rate is an instant fact: its date is period_instant, and
    # period_end is an empty (NaN) cell.
    ('closing', 'ifrs-full:ClosingForeignExchangeRate', ('period_end', 'period_instant')),
)

# Marks a warning that is a failure to read the facts (edgartools-35jj).
_FAILED = 'could not be extracted'

# The axis whose member names the currency a rate is quoted for.
_CURRENCY_AXIS = 'srt:CurrencyAxis'

# Which way a rate is quoted. Novo's dkkPerUSD unit states home currency per
# target (662 DKK per 100 USD); GSK's note 5 states target per home (US$/£ 1.31).
_HOME_PER_TARGET = 'home_per_target'
_TARGET_PER_HOME = 'target_per_home'
# A pure-number unit: the direction has to come from somewhere else.
_PURE = 'pure'

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
    # How the stored rates are quoted. get_rate() returns the rate as filed, and
    # to_usd()/from_usd() read this to divide or multiply (GH #1651).
    _quote: str = field(default=_HOME_PER_TARGET, init=False)
    # Populated when rate extraction RAISED, as opposed to finding nothing.
    # Without it both outcomes present as "no rates found" (edgartools-35jj).
    _extraction_warnings: List[str] = field(default_factory=list, init=False)

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
                # Counts per-share facts as well: a 'divide' unit denominates
                # its value in the numerator's currency, and before
                # edgartools-uetp those units were misparsed as simple, so this
                # only ever saw the numerator by accident.
                currency = unit_currency(self.xbrl.units[unit_ref])
                if currency:
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
        1. Divide units of the home and target currency, either way round:
           Novo's DKK/USD ('dkkPerUSD', 662 per 100 USD) or SAP's USD/EUR
           (1.1293 USD per EUR)
        2. Pure ratio units ('number', 'pure') with direct exchange rates. These
           do not state a direction; one on the target currency's
           ``srt:CurrencyAxis`` member is read as target per 1 home unit, and a
           warning says so (GH #1651). One with no currency member is not used.

        A filing publishes one rate per currency, and often hedge-instrument
        rates too, under the same concept. Only facts for the target currency
        (``srt:CurrencyAxis``) that are not on a hedge axis are used; when the
        remaining facts for a year disagree, no rate is kept for that year and
        the disagreement is reported in ``extraction_warnings`` (GH #1650).

        Returns:
            Dict mapping year to ExchangeRate objects
        """
        rates: Dict[int, ExchangeRate] = {}
        self._extraction_warnings = []

        home = self.home_currency.upper()
        target = self.target_currency.upper()

        # Fallback for a unit_ref with no parsed unit: the id itself,
        # e.g. 'dkkPerUSD', 'eurPerUSD'
        home_lower = self.home_currency.lower()
        expected_unit_patterns = [
            f"{home_lower}Per{target}",
            f"{home_lower}_{target}",
            f"{home_lower}{target}",
        ]

        # Also accept pure ratio units (some filers use 'number' or 'pure')
        pure_unit_patterns = ['number', 'pure', 'ratio']
        units = self.xbrl.units

        def unit_quote(unit_ref: str) -> Optional[str]:
            """How a rate in this unit is quoted: a quote constant, _PURE, or None.

            Read from the unit's resolved measures, not its opaque id: SAP's
            USD per EUR unit is 'Unit_Divide_USD_EUR_yMgaKio6_...', which no id
            pattern matched (GH #1653). The measure's local name is compared,
            since some filers use an extension measure (Vodafone's 'vod:EUR').
            """
            unit = units.get(unit_ref)
            if unit is None:
                if any(pattern in unit_ref for pattern in expected_unit_patterns):
                    return _HOME_PER_TARGET
                if unit_ref.lower() in pure_unit_patterns:
                    return _PURE
                return None
            if unit.get('type') == 'divide':
                numerator = [_local_name(m).upper() for m in unit.get('numerator', [])]
                denominator = [_local_name(m).upper() for m in unit.get('denominator', [])]
                if numerator == [home] and denominator == [target]:
                    return _HOME_PER_TARGET
                if numerator == [target] and denominator == [home]:
                    return _TARGET_PER_HOME
                return None  # another currency pair, e.g. SAP's AUD per EUR
            if _local_name(unit.get('measure') or '').lower() == 'pure':
                return _PURE
            return None

        selected: List[tuple] = []
        for kind, concept, date_columns in _RATE_CONCEPTS:
            try:
                df = self.xbrl.facts.query().by_concept(concept, exact=True).to_dataframe()
                selected.extend(self._select_rates(df, kind, date_columns, unit_quote))
            except Exception as e:
                # Not "no rates found": that is what an empty frame means. This
                # is the extraction itself failing, which is indistinguishable
                # from a filing that genuinely publishes no rate unless it is
                # recorded (bead edgartools-35jj).
                self._extraction_warnings.append(
                    f"{kind} exchange rates {_FAILED}: {type(e).__name__}: {e}"
                )
                log.warning(
                    "Could not extract %s foreign-exchange rates from the filing (%s). "
                    "to_usd() will return None for periods that depend on them rather "
                    "than converting with a wrong rate.", kind, e,
                )

        if not selected:
            return rates

        # A pure number does not say which way it is quoted. GSK (US$/£ 1.31)
        # and BioNTech (1.0824 for 2024, which is SAP's USD per EUR rate) both
        # tag the USD member with USD per 1 home unit, so that is how it is read.
        assumed = any(quote == _PURE for *_, quote in selected)
        selected = [(year, kind, value, _TARGET_PER_HOME if quote == _PURE else quote)
                    for year, kind, value, quote in selected]

        # One direction per converter. A filing quotes its rates one way; if the
        # selected facts disagree, keep the majority and say what was dropped.
        quotes = Counter(quote for _, _, _, quote in selected)
        self._quote = quotes.most_common(1)[0][0]
        for year, kind, value, quote in selected:
            if quote != self._quote:
                self._extraction_warnings.append(
                    f"the {kind} rate for {year} ({value}) is quoted the other way "
                    f"from the filing's other rates and was not used"
                )
                continue
            rates.setdefault(year, ExchangeRate(year=year))
            setattr(rates[year], kind, value)
        if assumed and self._quote == _TARGET_PER_HOME:
            # An assumption, not a reading of the filing, so it is stated.
            self._extraction_warnings.append(
                f"the rates use a pure-number unit, which does not state their direction; "
                f"read as {self.target_currency} per 1 {self.home_currency}"
            )

        # Auto-detect rate scale by checking if rates look like "per 100" or direct
        # Rates > 10 are likely "per 100 USD" format, rates < 10 are direct rates
        if self._quote == _TARGET_PER_HOME:
            # Target per 1 home unit.
            self._rate_scale = 1.0
        elif rates:
            sample_rate = next(iter(rates.values()))
            rate_value = sample_rate.average or sample_rate.closing
            if rate_value and rate_value < 10:
                # Direct rate format (e.g., 1.08 EUR per USD)
                self._rate_scale = 1.0
            else:
                # Per 100 format (e.g., 689 DKK per 100 USD)
                self._rate_scale = 100.0

        return rates

    def _fact_dimensions(self, row) -> Dict[str, str]:
        """The dimensions of a fact's context, e.g. ``{'srt:CurrencyAxis': 'currency:USD'}``."""
        context = self.xbrl.contexts.get(row.get('context_ref'))
        return dict(context.dimensions) if context is not None else {}

    def _select_rates(self, df, kind: str, date_columns, unit_quote) -> List[tuple]:
        """Pick one ``kind`` rate per year from the facts of one rate concept.

        Returns ``(year, kind, value, quote)`` tuples.
        """
        if df.empty:
            return []
        target = self.target_currency.upper()
        # year -> [(number of dimensions besides the currency axis, value, quote)]
        candidates: Dict[int, List[tuple]] = {}
        hedge_rows: Counter = Counter()
        # Rate facts of an accepted unit whose period gave no year. Skipping one
        # silently left a filing's closing rates missing with no warning (GH #1652).
        undated = 0
        # Pure-number rates with no currency member: neither the currency nor
        # the direction is stated, so they cannot be used safely (GH #1651).
        unnamed = 0

        for _, row in df.iterrows():
            quote = unit_quote(row.get('unit_ref', ''))
            if quote is None:
                continue
            dimensions = self._fact_dimensions(row)
            member = dimensions.get(_CURRENCY_AXIS)
            if member is not None and _local_name(member).upper() != target:
                continue  # the rate of another currency, e.g. JPY for GSK
            if quote == _PURE and member is None:
                unnamed += 1
                continue
            year = _extract_year(_first_date(row, *date_columns))
            if not year:
                undated += 1
                continue
            if any('hedg' in _local_name(axis).lower() for axis in dimensions):
                # A hedging instrument's contracted rate, not a translation rate.
                hedge_rows[year] += 1
                continue
            value = row.get('numeric_value')
            if value is None or pd.isna(value):
                continue
            extra = len(dimensions) - (1 if member is not None else 0)
            candidates.setdefault(year, []).append((extra, value, quote))

        selected = []
        for year, facts in candidates.items():
            fewest = min(extra for extra, _, _ in facts)
            best = sorted({(value, quote) for extra, value, quote in facts if extra == fewest})
            values = [value for value, _ in best]
            if len(best) == 1:
                selected.append((year, kind) + best[0])
            else:
                self._extraction_warnings.append(
                    f"{len(values)} different {kind} {target} rates for {year} "
                    f"({', '.join(str(v) for v in values)}); none was used"
                )
        for year, count in sorted(hedge_rows.items()):
            if year not in candidates:
                self._extraction_warnings.append(
                    f"the only {kind} {target} rates for {year} are {count} "
                    f"hedging-instrument rate(s), which were not used"
                )
        if undated:
            self._extraction_warnings.append(
                f"{undated} {kind} exchange rate fact(s) had no period date and were not used"
            )
        if unnamed:
            self._extraction_warnings.append(
                f"{unnamed} {kind} exchange rate fact(s) with a pure-number unit name no "
                f"currency ({_CURRENCY_AXIS}) and were not used"
            )
        return selected

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

        if self._quote_direction() == _TARGET_PER_HOME:
            # Rate is USD per home unit: USD = home_value * rate
            return value * (rate / self._rate_scale)
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

        if self._quote_direction() == _TARGET_PER_HOME:
            # Rate is USD per home unit: home = USD / rate
            return value / (rate / self._rate_scale)
        # Rate is "home currency per 100 USD"
        # To convert: home = USD * (rate / 100)
        return value * (rate / self._rate_scale)

    def _quote_direction(self) -> str:
        # getattr: instances built with __new__ (the unit tests) skip the
        # dataclass defaults; they predate quote detection and hold home per USD.
        return getattr(self, '_quote', _HOME_PER_TARGET)

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
            The exchange rate as the filing states it, or None if not available.
            It is home currency per 100 USD (Novo: 662 DKK) or per 1 USD, or,
            when the filing quotes it the other way, USD per 1 home unit (GSK:
            1.31 US$/£). ``repr()`` of the converter names the direction.
        """
        if year not in self.exchange_rates:
            return None

        rate_obj = self.exchange_rates[year]
        if rate_type == 'average':
            return rate_obj.average
        elif rate_type == 'closing':
            return rate_obj.closing
        return None

    @property
    def extraction_warnings(self) -> List[str]:
        """Failures hit while reading exchange rates from the filing.

        Empty means the rates on this object are everything the filing published.
        Non-empty means extraction failed, or that rate facts were found but not
        used, so the rates may be incomplete, which is not the same thing as a
        filer publishing no rate at all.
        """
        # getattr, not attribute access: instances built with __new__ (as the
        # unit tests and any pickling path do) never run the dataclass defaults,
        # and a __repr__ that raises AttributeError would be a worse version of
        # the failure this whole change is about.
        return list(getattr(self, "_extraction_warnings", []))

    @property
    def has_warnings(self) -> bool:
        return bool(getattr(self, "_extraction_warnings", []))

    def _extraction_failed(self) -> bool:
        """True when a warning is a failure to read the facts, not a rate set aside."""
        return any(_FAILED in w for w in self.extraction_warnings)

    def __repr__(self) -> str:
        if not self.has_rates:
            if self.has_warnings:
                # "no rates found" would be a claim about the filing; this was a
                # failure on our side, or rates found and set aside (GH #1650),
                # and must not read as the filer's silence.
                status = ("rate extraction failed" if self._extraction_failed()
                          else "no usable rates")
                return (f"CurrencyConverter(home={self.home_currency}, "
                        f"target={self.target_currency}, {status}: "
                        f"{self.extraction_warnings[0]})")
            return f"CurrencyConverter(home={self.home_currency}, target={self.target_currency}, no rates found)"

        lines = [f"CurrencyConverter(home={self.home_currency}, target={self.target_currency})"]

        # Format rate description based on direction and scale
        if self._quote_direction() == _TARGET_PER_HOME:
            rate_desc = f"{self.target_currency} per {self.home_currency}"
        elif self._rate_scale == 100.0:
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

        if self.has_warnings:
            warnings_ = self.extraction_warnings
            lines.append(f"  Warnings ({len(warnings_)}): {warnings_[0]}")

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

        if self.has_warnings:
            # An empty table and a table missing rows look identical; say which.
            status = "Rate extraction failed" if self._extraction_failed() else "Warnings"
            table.caption = (f"[red]{status} "
                             f"({len(self.extraction_warnings)}): "
                             f"{self.extraction_warnings[0]}[/red]")

        return table
