"""Regression test for #981 — `_parse_date` ISO fast path.

GitHub Issue: https://github.com/dgunning/edgartools/issues/981

`EntityFactsParser._parse_date` used to try `datetime.strptime` before
`datetime.fromisoformat`. SEC facts dates are ISO-8601, so the first format in the
loop always matched and the `fromisoformat` fallback was never reached — costing
~3.6us per date instead of ~0.10us (a locale lock per call), across 364,523 date
parses for six companies.

Reordering is only safe if behaviour is byte-identical, so this file pins the
equivalence rather than the speed: every input shape the old implementation
handled must still map to the same result, including the non-ISO `%m/%d/%Y` form
that only the fallback can parse.
"""

from datetime import date, datetime

import pytest

from edgar.entity import parser as parser_module
from edgar.entity.parser import EntityFactsParser


def _pre_981(date_str):
    """The implementation as it stood before #981, kept as the oracle."""
    if not date_str:
        return None
    try:
        for fmt in ["%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return datetime.fromisoformat(date_str).date()
    except Exception:
        return None


# Every shape the parser can be handed: the ISO forms SEC actually emits, the
# legacy formats, and the malformed inputs that must stay None.
CASES = [
    "2024-03-31",  # SEC facts: end / start / filed
    "20240331",  # compact ISO
    "03/31/2024",  # non-ISO — only the strptime fallback parses this
    "2024-03-31T00:00:00",  # ISO datetime
    "2024-03-31T12:34:56+00:00",  # ISO datetime with offset
    "1999-01-01",
    "2024-2-3",  # single-digit month/day
    "",
    None,
    "garbage",
    "2024-13-45",  # well-shaped but not a real date
    "  2024-03-31  ",  # padded — was rejected before, must stay rejected
    "2024/03/31",
    12345,  # not a string at all
]


@pytest.mark.parametrize("value", CASES)
def test_parse_date_matches_pre_981_behaviour(value):
    """The fast path must not change a single result."""
    assert EntityFactsParser._parse_date(value) == _pre_981(value)


def test_iso_dates_parse():
    """The SEC form, asserted directly rather than only against the oracle."""
    assert EntityFactsParser._parse_date("2024-03-31") == date(2024, 3, 31)


def test_non_iso_format_still_reaches_the_fallback():
    """The regression that reordering could plausibly cause: `%m/%d/%Y` is not
    ISO, so it is only reachable through the strptime loop. If someone later
    drops that loop as 'dead code', this fails."""
    assert EntityFactsParser._parse_date("03/31/2024") == date(2024, 3, 31)


def test_unparseable_returns_none_not_raises():
    """`_parse_date` is called per fact during parsing; raising would abort the
    whole company. Non-string input is included because the old `except
    Exception` swallowed the TypeError that `fromisoformat` raises."""
    assert EntityFactsParser._parse_date("garbage") is None
    assert EntityFactsParser._parse_date(12345) is None  # type: ignore[arg-type]


class _CountingDatetime(datetime):
    """A datetime whose strptime records that it was called."""

    calls = 0

    @classmethod
    def strptime(cls, date_string, fmt):  # type: ignore[override]
        _CountingDatetime.calls += 1
        return datetime.strptime(date_string, fmt)


def test_iso_input_never_reaches_strptime(monkeypatch):
    """The actual subject of #981, and the only test here that fails without the fix.

    Everything above pins EQUIVALENCE — which the pre-#981 implementation satisfies by
    construction, so those tests stay green with the bug in place. They guard the
    reordering against changing behaviour; they cannot guard against the bug being
    reintroduced. This asserts what the issue is actually about: for an ISO-8601 date,
    the locale-locking `strptime` must not run at all.
    """
    monkeypatch.setattr(parser_module, "datetime", _CountingDatetime)
    _CountingDatetime.calls = 0
    assert EntityFactsParser._parse_date("2024-03-31") == date(2024, 3, 31)
    assert _CountingDatetime.calls == 0


def test_non_iso_input_does_reach_strptime(monkeypatch):
    """The positive half of the pair: without it, a `_parse_date` that had dropped the
    strptime loop entirely would still satisfy the test above."""
    monkeypatch.setattr(parser_module, "datetime", _CountingDatetime)
    _CountingDatetime.calls = 0
    assert EntityFactsParser._parse_date("03/31/2024") == date(2024, 3, 31)
    assert _CountingDatetime.calls >= 1
