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

import math
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


def _precision(decimals) -> float:
    """A fact's ``decimals`` as a number: 'INF' or unknown is exact (inf)."""
    try:
        return float(decimals)
    except (TypeError, ValueError):
        return math.inf


def _agreed_value(values) -> Optional[float]:
    """One rate from ``(value, decimals)`` pairs that agree to their stated precision.

    1.31 (decimals 2) and 1.3077 (decimals 4) are one rate, rounded; the most
    precise is kept. Values that differ by more than half a unit in the last
    stated place give None (GH #1650 review).
    """
    pairs = []
    for value, decimals in values:
        precision = _precision(decimals)
        pairs.append((value, math.inf if math.isnan(precision) else precision))
    pairs.sort(key=lambda pair: pair[1], reverse=True)
    best, _ = pairs[0]
    for value, precision in pairs[1:]:
        tolerance = 0.0 if math.isinf(precision) else 0.5 * 10 ** -precision
        if abs(value - best) > tolerance + 1e-12:
            return None
    return best


def _days(start, end) -> float:
    """Length of a duration fact in days, or 0 when it has no start."""
    try:
        days = float((pd.Timestamp(end) - pd.Timestamp(start)).days)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(days) else days


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

# Which way a unit says a rate is quoted: Novo's dkkPerUSD is home per target,
# SAP's USD/EUR is target per home. A pure-number unit says nothing.
_HOME_PER_TARGET = 'home_per_target'
_TARGET_PER_HOME = 'target_per_home'
_PURE = 'pure'

# The ways a filed rate can read, each as a function giving target per 1 home
# unit: GSK's 1.31 is USD per GBP, Sun Life's 1.33 is CAD per USD, Novo's 662
# is DKK per 100 USD. ("USD" stands for the target currency.)
_USD_PER_HOME = 'usd_per_home'
_HOME_PER_USD = 'home_per_usd'
_HOME_PER_100_USD = 'home_per_100_usd'
_READINGS = {
    _USD_PER_HOME: lambda value: value,
    _HOME_PER_USD: lambda value: 1 / value,
    _HOME_PER_100_USD: lambda value: 100 / value,
}

# USD per 1 unit of each currency: a band around everything it traded at from
# 2000 to 2026, padded. A rate is read the way that lands it in its band; the
# bands are far narrower than 100x, so "per 1" and "per 100" never both fit.
# Near-parity currencies (EUR, CHF, CAD, AUD) can fit both "USD per home" and
# "home per USD"; such a rate is used only if the filing itself says which.
# Volatile currencies (ARS, TRY, VES, NGN, EGP, ...) are left out on purpose:
# no band would be narrow enough to tell the readings apart.
_USD_PER_UNIT = {
    'EUR': (0.75, 1.75),
    'GBP': (0.95, 2.30),
    'CHF': (0.50, 1.50),
    'JPY': (0.0055, 0.0145),
    'CAD': (0.58, 1.15),
    'AUD': (0.45, 1.15),
    'NZD': (0.36, 0.95),
    'DKK': (0.10, 0.235),
    'SEK': (0.075, 0.18),
    'NOK': (0.075, 0.21),
    'CNY': (0.11, 0.175),
    'HKD': (0.125, 0.131),
    'SGD': (0.50, 0.85),
    'KRW': (0.0006, 0.00125),
    'TWD': (0.027, 0.038),
    'INR': (0.0105, 0.0275),
    'IDR': (0.000055, 0.00013),
    'ILS': (0.19, 0.34),
    'ZAR': (0.045, 0.18),
    'BRL': (0.15, 0.70),
    'MXN': (0.038, 0.12),
    'CLP': (0.00095, 0.0025),
    'COP': (0.00018, 0.0006),
    'PEN': (0.24, 0.40),
    'RUB': (0.008, 0.045),
}


def _plausible_range(home: str, target: str) -> Optional[tuple]:
    """(low, high) of target currency per 1 home unit, or None if unknown."""
    home_band = _USD_PER_UNIT.get(home.upper())
    target_band = (1.0, 1.0) if target.upper() == 'USD' else _USD_PER_UNIT.get(target.upper())
    if home_band is None or target_band is None:
        return None
    return home_band[0] / target_band[1], home_band[1] / target_band[0]


def _overlaps(low: float, high: float, band: tuple) -> bool:
    return low <= band[1] and high >= band[0]


def _sibling_readings(home: str, siblings) -> Optional[set]:
    """The reading other currencies' rates in the same table point to, or None.

    GSK's yen rate is 198: as JPY per GBP that implies 1.09-2.87 USD per GBP,
    inside the GBP band; as GBP per JPY it implies nothing plausible. So GSK
    quotes foreign currency per pound, and its USD rate is USD per GBP. Only a
    sibling that fits exactly one convention votes, and the votes must agree.
    """
    home_band = _USD_PER_UNIT.get(home.upper())
    if home_band is None:
        return None
    votes = set()
    for code, value in siblings:
        band = _USD_PER_UNIT.get(code)
        if band is None or code == home.upper():
            continue
        low, high = band
        fits = [reading for reading, (lo, hi) in (
            (_USD_PER_HOME, (value * low, value * high)),           # foreign per home
            (_HOME_PER_USD, (low / value, high / value)),           # home per foreign
            (_HOME_PER_100_USD, (100 * low / value, 100 * high / value)),
        ) if _overlaps(lo, hi, home_band)]
        if len(fits) == 1:
            votes.add(fits[0])
    return votes if len(votes) == 1 else None

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
    # Only for a converter built by hand without a filing: its rates are home
    # currency per this many target units. Extracted rates use _factors.
    _rate_scale: float = field(default=100.0, init=False)
    # (year, kind) -> target per 1 home unit, and how that reading was decided.
    # get_rate() returns the rate as filed; to_usd()/from_usd() use these.
    _factors: Dict[tuple, float] = field(default_factory=dict, init=False)
    _basis: Dict[tuple, tuple] = field(default_factory=dict, init=False)
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
        2. Pure ratio units ('number', 'pure'), which do not state a direction.

        Each rate is read whichever way (target per home, home per target, home
        per 100 target) puts it in the plausible band for the pair; when more
        than one does, the unit or the other currencies' rates in the table must
        decide, or the rate is not used (GH #1651). ``rate_basis`` says which.

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
        siblings: Dict[tuple, List[tuple]] = {}
        for kind, concept, date_columns in _RATE_CONCEPTS:
            try:
                df = self.xbrl.facts.query().by_concept(concept, exact=True).to_dataframe()
                selected.extend(self._select_rates(df, kind, date_columns, unit_quote, siblings))
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

        if not selected or home == target:
            return rates  # home == target: nothing to convert (Rio Tinto reports in USD)

        # How each rate reads is decided per rate, by which reading puts it in
        # the plausible range for the pair (GH #1651 review). A fixed rule
        # cannot work: pure-number rates follow each filer's convention, and
        # most quote home per USD (Sun Life 1.33 CAD, Tata 69.155 INR) while
        # GSK and National Grid quote USD per GBP. The old "> 10 means per
        # 100 USD" rule made MXN, ZAR, RUB and INR divide-unit rates 100x off.
        self._factors = {}
        self._basis = {}
        for year, kind, value, quote, named in selected:
            reading, how = self._read_rate(year, kind, value, quote, named,
                                           siblings.get((kind, year), []))
            if reading is None:
                continue
            rates.setdefault(year, ExchangeRate(year=year))
            setattr(rates[year], kind, value)
            self._factors[(year, kind)] = _READINGS[reading](value)
            self._basis[(year, kind)] = (self._reading_label(reading), how)
        return rates

    def _reading_label(self, reading: str) -> str:
        home, target = self.home_currency, self.target_currency
        return {
            _USD_PER_HOME: f"{target} per {home}",
            _HOME_PER_USD: f"{home} per {target}",
            _HOME_PER_100_USD: f"{home} per 100 {target}",
        }[reading]

    def _read_rate(self, year, kind, value, quote, named, siblings):
        """Decide how one rate reads. Returns ``(reading, how)``, or ``(None, None)``
        with the reason in extraction_warnings: this never guesses."""
        where = f"the {kind} rate for {year} ({value})"
        bounds = _plausible_range(self.home_currency, self.target_currency)
        if bounds is None:
            self._extraction_warnings.append(
                f"{where} was not used: no plausible range is known for "
                f"{self.target_currency} per {self.home_currency}, so its direction "
                f"cannot be checked"
            )
            return None, None
        low, high = bounds
        fits = [r for r, factor in _READINGS.items() if low <= factor(value) <= high]
        labels = ' or '.join(self._reading_label(r) for r in fits)

        # In-filing signals: the unit's numerator and denominator, then the
        # other currencies' rates in the same table.
        if quote == _TARGET_PER_HOME:
            hint, hint_source = {_USD_PER_HOME}, "its unit"
        elif quote == _HOME_PER_TARGET:
            hint, hint_source = {_HOME_PER_USD, _HOME_PER_100_USD}, "its unit"
        else:
            hint = _sibling_readings(self.home_currency, siblings)
            hint_source = "the other currencies' rates in the filing"

        if not fits:
            self._extraction_warnings.append(
                f"{where} was not used: no reading of it is a plausible "
                f"{self.target_currency} rate for {self.home_currency}"
            )
            return None, None
        if len(fits) == 1:
            reading = fits[0]
            if hint is not None and reading not in hint:
                self._extraction_warnings.append(
                    f"{where} was not used: it is plausible only as "
                    f"{self._reading_label(reading)}, which {hint_source} contradicts"
                )
                return None, None
            how = "only plausible reading"
        else:
            narrowed = [r for r in fits if hint is not None and r in hint]
            if len(narrowed) != 1:
                self._extraction_warnings.append(
                    f"{where} was not used: it is plausible as {labels}, and nothing "
                    f"in the filing says which"
                )
                return None, None
            reading = narrowed[0]
            how = f"plausible either way, settled by {hint_source}"
        if not named:
            how += "; names no currency, read as " + self.target_currency
            self._extraction_warnings.append(
                f"{where} names no currency ({_CURRENCY_AXIS}); it was read as a "
                f"{self.target_currency} rate because that is its only plausible reading"
            )
        return reading, how

    def _fact_dimensions(self, row) -> Dict[str, str]:
        """The dimensions of a fact's context, e.g. ``{'srt:CurrencyAxis': 'currency:USD'}``."""
        context = self.xbrl.contexts.get(row.get('context_ref'))
        return dict(context.dimensions) if context is not None else {}

    def _select_rates(self, df, kind: str, date_columns, unit_quote,
                      siblings: Dict[tuple, List[tuple]]) -> List[tuple]:
        """Pick one ``kind`` rate per year from the facts of one rate concept.

        Returns ``(year, kind, value, quote, named)`` tuples, ``named`` saying the
        fact carries a currency member. Pure-number rates of other currencies are
        added to ``siblings[(kind, year)]`` as ``(currency, value)``: they show
        which way the filing quotes its rates.
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
        # Empty, zero or non-finite values: a zero rate passed an `is None`
        # check and to_usd() then divided by it.
        unusable = 0

        for _, row in df.iterrows():
            quote = unit_quote(row.get('unit_ref', ''))
            if quote is None:
                continue
            dimensions = self._fact_dimensions(row)
            member = dimensions.get(_CURRENCY_AXIS)
            hedged = any('hedg' in _local_name(axis).lower() for axis in dimensions)
            if member is not None and _local_name(member).upper() != target:
                # The rate of another currency, e.g. JPY for GSK. Not used, but
                # a pure one shows the filing's convention (198 JPY per GBP).
                value = row.get('numeric_value')
                year = _extract_year(_first_date(row, *date_columns))
                if (quote == _PURE and not hedged and year and value is not None
                        and math.isfinite(value) and value > 0):
                    siblings.setdefault((kind, year), []).append(
                        (_local_name(member).upper(), value))
                continue
            period_date = _first_date(row, *date_columns)
            year = _extract_year(period_date)
            if not year:
                undated += 1
                continue
            if hedged:
                # A hedging instrument's contracted rate, not a translation rate.
                hedge_rows[year] += 1
                continue
            value = row.get('numeric_value')
            if value is None or pd.isna(value) or not math.isfinite(value) or value == 0:
                unusable += 1
                continue
            extra = len(dimensions) - (1 if member is not None else 0)
            candidates.setdefault(year, []).append({
                'extra': extra, 'value': value, 'quote': quote,
                # A divide unit names the pair itself; a pure number needs the member.
                'named': member is not None or quote != _PURE,
                'decimals': row.get('decimals'), 'date': str(period_date)[:10],
                'days': _days(row.get('period_start'), period_date),
            })

        selected = []
        for year, facts in candidates.items():
            # The translation rate has the fewest other dimensions; of those, the
            # one at the year end (not an interim or IFRS transition date), and for
            # an average the full-year period rather than a half year.
            # A fact naming the currency beats one that does not.
            if any(f['named'] for f in facts):
                facts = [f for f in facts if f['named']]
            fewest = min(f['extra'] for f in facts)
            facts = [f for f in facts if f['extra'] == fewest]
            latest = max(f['date'] for f in facts)
            facts = [f for f in facts if f['date'] == latest]
            longest = max(f['days'] for f in facts)
            facts = [f for f in facts if f['days'] == longest]
            quotes = {f['quote'] for f in facts}
            value = _agreed_value([(f['value'], f['decimals']) for f in facts])
            values = sorted({f['value'] for f in facts})
            if len(quotes) == 1 and value is not None:
                selected.append((year, kind, value, quotes.pop(), facts[0]['named']))
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
        if unusable:
            self._extraction_warnings.append(
                f"{unusable} {kind} exchange rate fact(s) had no usable value "
                f"(empty, zero or not finite) and were not used"
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

        return value * self._target_per_home(year, rate_type, rate)

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

        return value / self._target_per_home(year, rate_type, rate)

    def _target_per_home(self, year: int, rate_type: str, rate: float) -> float:
        factors = getattr(self, '_factors', None) or {}
        if (year, rate_type) in factors:
            return factors[(year, rate_type)]
        # A converter built by hand (getattr: __new__ skips the dataclass
        # defaults) holds home currency per _rate_scale target units.
        return getattr(self, '_rate_scale', 100.0) / rate

    @property
    def rate_basis(self) -> Dict[tuple, str]:
        """How each rate's direction was decided, keyed by ``(year, rate_type)``.

        e.g. ``{(2025, 'average'): 'USD per GBP (only plausible reading)'}``.
        to_usd() returns a plain number; this says what it rests on.
        """
        basis = getattr(self, '_basis', None) or {}
        return {key: f"{label} ({how})" for key, (label, how) in basis.items()}

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
            The exchange rate as the filing states it, or None if not available:
            home currency per 100 USD (Novo: 662 DKK), home currency per USD
            (Sun Life: 1.33 CAD) or USD per home unit (GSK: 1.31 US$/£).
            ``rate_basis`` and ``repr()`` say which, and how it was decided.
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

        basis = getattr(self, '_basis', None) or {}
        labels = sorted({label for label, _ in basis.values()})
        if len(labels) == 1:
            rate_desc = labels[0]
        elif labels:
            rate_desc = "as filed"
        elif getattr(self, '_rate_scale', 100.0) == 100.0:
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

        for line in sorted({f"{label}: {how}" for label, how in basis.values()}):
            lines.append(f"  Read as {line}")

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
