"""Reporting-unit evidence for 13F values, before normalization to dollars."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

ValueUnit = Literal['dollars', 'thousands']

# Kept as a fallback for filings without usable schema metadata.
_13F_VALUE_IN_THOUSANDS_CUTOFF = datetime(2022, 9, 30)
_13F_IMPLIED_PRICE_THOUSANDS_THRESHOLD = 1.0
_13F_FRAC_THOUSANDS = 0.5
_13F_DOLLARS_SCHEMA_VERSION = 'X0202'


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

    A majority of sub-dollar implied prices remains evidence for thousands.
    Otherwise metadata decides: raw prices alone cannot distinguish ordinary
    dollar holdings from thousands-denominated holdings of expensive securities.
    In particular, old filings can already contain dollars (Kahn Brothers,
    0001039565-22-000009). No upper price cap can safely resolve that ambiguity.
    """
    import pandas as pd

    if override not in (None, 'dollars', 'thousands'):
        raise ValueError("value_unit must be None, 'dollars', or 'thousands'")

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
    elif fraction is not None and fraction >= _13F_FRAC_THOUSANDS:
        unit, source, ambiguous = 'thousands', 'implied_prices', False
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
