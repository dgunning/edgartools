"""Numeric and date parsing helpers for 424B prospectus extraction."""

from __future__ import annotations

from datetime import date
from typing import Optional


def _parse_filing_date(d) -> Optional[date]:
    """Parse a filing date string or date to a date object."""
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return date.fromisoformat(d)
        except (ValueError, TypeError):
            return None
    return None


def _plus_three_years(d: date) -> date:
    """The Rule 415(a)(5) expiry date: three years after ``d``."""
    try:
        return d.replace(year=d.year + 3)
    except ValueError:
        # Feb 29 -> Feb 28
        return d.replace(year=d.year + 3, day=d.day - 1)


def _parse_sec_number(val: Optional[str]) -> Optional[float]:
    """Parse SEC-style numeric strings into float.

    Handles: '$1,234,567', '1,234,567', '10.5 million', '(0.45)', '3.5%'
    Returns None on failure or empty input.
    """
    if not val or not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    # Skip non-numeric sentinel values
    lower = s.lower()
    if lower in ('-', 'n/a', 'none') or lower.startswith(('at', 'exchange', 'preliminary', 'market')):
        return None
    # Strip currency symbol and commas
    s = s.replace('$', '').replace(',', '').strip()
    # Handle parenthetical negatives: (123) → -123
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1].strip()
    # Strip trailing %
    s = s.rstrip('%').strip()
    if not s:
        return None
    # Handle multiplier words
    lower = s.lower()
    multipliers = {'million': 1_000_000, 'billion': 1_000_000_000}
    for word, mult in multipliers.items():
        if lower.endswith(word):
            num_part = lower[:len(lower) - len(word)].strip()
            try:
                return float(num_part) * mult
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_sec_int(val: Optional[str]) -> Optional[int]:
    """Parse SEC-style numeric string to int, rounding if needed."""
    f = _parse_sec_number(val)
    if f is None:
        return None
    return round(f)
