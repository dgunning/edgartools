"""Regression test for issue #1178.

`find()` matched ordinary tickers with `^[A-WYZ]{1,5}...`, a character class that
excludes `X` in every position — not just the trailing position that marks a
mutual fund.  XOM, AXP and FIX therefore fell through to ranked company-name
search and came back as `CompanySearchResults` instead of a `Company`.

The fix orders the `^[A-Z]{4}X$` fund pattern ahead of the ticker pattern, so
fund routing is preserved without excluding `X` from ordinary symbols.
"""

import re

import pytest

import edgar

# The two patterns from find(), in dispatch order.
FUND_TICKER = re.compile(r"^[A-Z]{4}X$")
ORDINARY_TICKER = re.compile(r"^[A-Z]{1,5}([.-][A-Z])?$")


def route(search_id: str) -> str:
    """Which of the two ticker branches claims this identifier."""
    if FUND_TICKER.match(search_id):
        return "fund"
    if ORDINARY_TICKER.match(search_id):
        return "ticker"
    return "name-search"


@pytest.mark.parametrize("ticker", ["XOM", "AXP", "FIX", "X", "NFLX", "XYZ", "BRK-B"])
def test_ordinary_tickers_containing_x_route_to_the_ticker_branch(ticker):
    assert route(ticker) == "ticker"


@pytest.mark.parametrize("ticker", ["VFIAX", "SPHIX", "FXAIX"])
def test_five_letter_trailing_x_still_routes_to_the_fund_branch(ticker):
    assert route(ticker) == "fund"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "BRK.B"])
def test_tickers_without_x_are_unaffected(ticker):
    assert route(ticker) == "ticker"


def test_find_source_uses_the_inclusive_ticker_class():
    """The dispatch chain in edgar/__init__.py must not exclude X."""
    source = (edgar.__file__)
    with open(source) as fh:
        text = fh.read()
    assert "[A-WYZ]" not in text
    assert 'r"^[A-Z]{1,5}([.-][A-Z])?$"' in text


@pytest.mark.network
@pytest.mark.parametrize("ticker,cik", [("XOM", 34088), ("AXP", 4962), ("FIX", 1035983)])
def test_find_resolves_x_tickers_to_companies(ticker, cik):
    result = edgar.find(ticker)
    assert isinstance(result, edgar.Entity)
    assert result.cik == cik
