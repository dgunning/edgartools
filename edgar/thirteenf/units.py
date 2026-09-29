"""Reporting-unit evidence for 13F values, before normalization to dollars."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from edgar.exceptions import ValidationError

ValueUnit = Literal['dollars', 'thousands']

# Kept as a fallback for filings without usable schema metadata.
_13F_VALUE_IN_THOUSANDS_CUTOFF = datetime(2022, 9, 30)
_13F_IMPLIED_PRICE_THOUSANDS_THRESHOLD = 1.0
_13F_FRAC_THOUSANDS = 0.5
_13F_DOLLARS_SCHEMA_VERSION = 'X0202'
# A sub-dollar fraction inside this band is a coin flip, not evidence: two
# priceable rows with one warrant land on exactly 0.5 (GH #1336). Metadata decides.
_13F_FRAC_DEAD_BAND = (0.35, 0.65)
# Fewer priceable rows than this still decide by price, but are flagged ambiguous
# so a 1000x conversion warns. Measured over the SEC 13F data sets for Dec 2025 -
# Aug 2026: of 151 small filings with a sub-dollar fraction >= 0.35, 99 genuinely
# report thousands and 52 dollars, so letting metadata decide them (it says
# dollars under X0202) would silently mis-scale the 99.
_13F_MIN_PRICEABLE_ROWS = 10


class Ambiguous13FValueUnitWarning(UserWarning):
    """A thousands-to-dollars conversion relies on ambiguous filing metadata."""


@dataclass(frozen=True)
class ValueUnitResolution:
    """The unit selected for raw values, and the evidence supporting that choice.

    ``ambiguous`` means the share-price evidence did not distinguish the two
    units. A schema/date fallback is a convention, not independent verification.
    An explicit override records the caller's decision, not library validation.
    """

    unit: ValueUnit
    source: Literal['override', 'implied_prices', 'schema', 'report_period', 'default']
    ambiguous: bool
    priceable_rows: int
    fraction_sub_dollar: Optional[float]
    schema_version: Optional[str]
    report_period: Optional[datetime]

    @property
    def multiplier(self) -> int:
        """Multiplier applied to raw values to produce dollars."""
        return 1000 if self.unit == 'thousands' else 1


def _schema_implies_dollars(schema_version: Optional[str]) -> Optional[bool]:
    if not schema_version:
        return None
    return schema_version.strip().upper() >= _13F_DOLLARS_SCHEMA_VERSION


def _resolve_unit_fallback(schema_version: Optional[str],
                           report_period_dt: Optional[datetime]) -> bool:
    dollars = _schema_implies_dollars(schema_version)
    if dollars is not None:
        return not dollars
    return report_period_dt is not None and report_period_dt <= _13F_VALUE_IN_THOUSANDS_CUTOFF


def resolve_value_unit(df, schema_version: Optional[str] = None,
                       report_period_dt: Optional[datetime] = None,
                       *, override: Optional[ValueUnit] = None) -> ValueUnitResolution:
    """Retain the existing unit heuristic while exposing its limitations.

    A majority of sub-dollar implied prices remains evidence for thousands, unless
    the fraction falls in ``_13F_FRAC_DEAD_BAND``; from fewer than
    ``_13F_MIN_PRICEABLE_ROWS`` rows it is flagged ambiguous (GH #1336).
    Otherwise metadata decides: raw prices alone cannot distinguish ordinary
    dollar holdings from thousands-denominated holdings of expensive securities.
    In particular, old filings can already contain dollars (Kahn Brothers,
    0001039565-22-000009). No upper price cap can safely resolve that ambiguity.
    """
    import pandas as pd

    if override not in (None, 'dollars', 'thousands'):
        raise ValidationError(
            "override must be None, 'dollars', or 'thousands'",
            parameter='override', invalid_value=override,
            suggestions=["Use None, 'dollars', or 'thousands'."],
        )

    count = 0
    fraction = None
    if df is not None:
        try:
            shares = pd.to_numeric(df['SharesPrnAmount'], errors='coerce')
            values = pd.to_numeric(df['Value'], errors='coerce')
            mask = (df['Type'] == 'Shares') & (shares > 0) & (values > 0)
            if 'PutCall' in df.columns:
                mask &= df['PutCall'].fillna('') == ''
            # Ignore missing, non-finite and non-positive observations. They do
            # not establish the unit of a priceable equity holding.
            mask &= shares < float('inf')
            mask &= values < float('inf')
            implied = (values[mask] / shares[mask]).dropna()
            implied = implied[(implied > 0) & (implied < float('inf'))]
            count = len(implied)
            if count:
                fraction = float((implied < _13F_IMPLIED_PRICE_THOUSANDS_THRESHOLD).mean())
        except (KeyError, TypeError, ValueError):
            pass

    if override is not None:
        unit, source, ambiguous = override, 'override', False
    elif (fraction is not None and fraction >= _13F_FRAC_THOUSANDS
          and not _13F_FRAC_DEAD_BAND[0] < fraction < _13F_FRAC_DEAD_BAND[1]):
        unit, source = 'thousands', 'implied_prices'
        ambiguous = count < _13F_MIN_PRICEABLE_ROWS
    else:
        unit = 'thousands' if _resolve_unit_fallback(schema_version, report_period_dt) else 'dollars'
        source = ('schema' if _schema_implies_dollars(schema_version) is not None else
                  'report_period' if report_period_dt is not None else 'default')
        ambiguous = True

    return ValueUnitResolution(unit, source, ambiguous, count, fraction,
                               schema_version, report_period_dt)


def _detect_value_in_thousands(df, schema_version: Optional[str] = None,
                               report_period_dt: Optional[datetime] = None) -> bool:
    """Compatibility wrapper for the original private unit detector."""
    return resolve_value_unit(df, schema_version, report_period_dt).unit == 'thousands'
