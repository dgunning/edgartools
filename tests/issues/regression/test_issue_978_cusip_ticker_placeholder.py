"""
GH #978 — the bundled CUSIP->ticker table shipped 1,843 rows whose symbol was a
real ticker with a literal `XXXX` placeholder concatenated onto it, so
get_ticker_from_cusip("G3421J106") returned 'FERGXXXX' instead of 'FERG' and the
13F parsers rendered that straight into a user-facing Ticker column.

The durable fix is upstream (edgar-storage#5, which generates the dataset) plus
sanitize_cusip_tickers() in the merge step, since the build script's fallback
branch reuses rows from the previously shipped file. These tests cover the
sanitizer; tests/test_reference.py guards the bundled file itself.

Tracked as edgartools-78ay.
"""
import pandas as pd
import pytest

from edgar.reference.tickers import sanitize_cusip_tickers


def _frame(pairs):
    return pd.DataFrame(pairs, columns=["Cusip", "Ticker"])


def test_placeholder_suffix_is_stripped_not_dropped():
    """The suffix hides a recoverable ticker, so strip it rather than lose the row.

    Verified against the pre-corruption ct.pq (f0ddf361): 1,842 of the 1,843
    affected CUSIPs appear there, and stripping reproduces that file's ticker for
    1,749 of them. The reporter's workaround discarded all 1,843.
    """
    cleaned, stats = sanitize_cusip_tickers(
        _frame([
            ("G3421J106", "FERGXXXX"),
            ("13645T100", "CPXXXX"),
            ("001228105", "MITTXXXX"),
        ])
    )

    assert list(cleaned["Ticker"]) == ["FERG", "CP", "MITT"]
    assert stats["placeholder_suffix_stripped"] == 3
    assert stats["dropped_empty"] == 0


def test_bare_placeholder_row_is_dropped():
    """`063679567 -> XXXX` predates the corruption: the feed's unknown-symbol
    marker standing alone. Stripping leaves nothing, so the row must go."""
    cleaned, stats = sanitize_cusip_tickers(_frame([("063679567", "XXXX")]))

    assert cleaned.empty
    assert stats["dropped_empty"] == 1


@pytest.mark.parametrize(
    "junk",
    [
        "**********",       # 55 such rows in the shipped file
        "0974PAYRTS",       # corporate-action artifact
        "Q999SPNOFF",
        "T014RTSPYMNT",
        "3111REG",
        "9105",             # bare CUSIP fragment
        "ferg",             # a feed that switches case is a break, not a ticker
    ],
)
def test_unresolvable_symbols_are_dropped(junk):
    """Family 2 and 3 from the sanitizer's comment — none of these resolve, and a
    rendered `Q999SPNOFF` is worse than an empty cell."""
    cleaned, stats = sanitize_cusip_tickers(_frame([("000000000", junk)]))

    assert cleaned.empty
    assert stats["dropped_malformed"] == 1


@pytest.mark.parametrize(
    "ticker",
    [
        "F",         # single letter
        "AAPL",
        "PGUCY",     # 5-char ADR
        "BRK.A",     # class suffix, dot form
        "BF-B",      # class suffix, dash form
        "MITTPRA",   # 7 chars: this feed's preferred-share convention
    ],
)
def test_real_symbols_survive(ticker):
    cleaned, _ = sanitize_cusip_tickers(_frame([("000000000", ticker)]))

    assert list(cleaned["Ticker"]) == [ticker]


def test_stats_account_for_every_row():
    cleaned, stats = sanitize_cusip_tickers(
        _frame([
            ("G3421J106", "FERGXXXX"),   # stripped, kept
            ("063679567", "XXXX"),       # stripped to empty, dropped
            ("004949103", "**********"),  # malformed, dropped
            ("037833100", "AAPL"),       # untouched
        ])
    )

    assert stats["rows_in"] == 4
    assert stats["rows_out"] == 2 == len(cleaned)
    assert stats["dropped_empty"] + stats["dropped_malformed"] == 2
    assert stats["placeholder_suffix_stripped"] == 2  # 'FERGXXXX' and bare 'XXXX'


def test_sanitizing_is_idempotent():
    """A rebuild reuses rows from the previously shipped file, so the pass runs
    over already-clean data on every regeneration."""
    once, _ = sanitize_cusip_tickers(
        _frame([("G3421J106", "FERGXXXX"), ("037833100", "AAPL")])
    )
    twice, stats = sanitize_cusip_tickers(once)

    assert list(twice["Ticker"]) == list(once["Ticker"])
    assert stats["dropped_empty"] == stats["dropped_malformed"] == 0
