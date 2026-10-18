"""Regression test for bead edgartools-ts80b.

get_cik_ticker_lookup() picked a CIK's primary ticker as the shortest one, so
dual-class issuers and issuers with listed notes got the wrong line: Alphabet
came back as GOOG, Fox as FOX, Navient as JSM (a note). SEC lists a CIK's
tickers primary-first, so the listed order now decides after demoting OTC and
derivative (preferred/unit/warrant) tickers.

Origin: bead edgartools-ts80b (found while fixing the same rule in edgar-storage).
"""
import pandas as pd
import pytest

from edgar.reference import tickers
from edgar.reference.tickers import _is_derivative_ticker, find_ticker, get_cik_ticker_lookup


@pytest.mark.parametrize("cik, expected", [
    (1652044, "GOOGL"),   # Alphabet: GOOGL, GOOG
    (1754301, "FOXA"),    # Fox: FOXA, FOX
    (1593538, "NAVI"),    # Navient: NAVI, JSM (senior note)
    (1390777, "BNY"),     # Bank of New York Mellon: BNY, BK, BK-PK, BNY-PK
    (1166691, "CMCSA"),   # Comcast: CMCSA before the CCZ note, no override needed
    (1787518, "DFNS"),    # T3 Defense: DFNS, not the DFNSW warrant
    (1506307, "KMI"),     # Kinder Morgan (GH #745)
    (19617, "JPM"),
    (320193, "AAPL"),
])
def test_primary_ticker_follows_sec_order(cik, expected):
    assert find_ticker(cik) == expected


def test_one_primary_per_cik():
    raw = tickers._get_company_tickers_raw()
    lookup = get_cik_ticker_lookup()
    assert set(lookup) == set(raw['cik'])
    owned = set(zip(raw['cik'], raw['ticker'], strict=True))
    assert all((cik, ticker) in owned for cik, ticker in lookup.items())


@pytest.mark.parametrize("ticker, siblings, expected", [
    ("JPM-PC", ["JPM", "JPM-PC"], True),
    ("KCAC-UN", ["KCAC-UN", "KCAC-WT"], True),
    ("BEATW", ["BEAT", "BEATW"], True),
    ("ALFUU", ["ALFU", "ALFUU"], True),
    ("FOXA", ["FOXA", "FOX"], False),     # share-class letter, not a derivative
    ("GOOGL", ["GOOGL", "GOOG"], False),
    ("JSM", ["NAVI", "JSM"], False),
])
def test_is_derivative_ticker(ticker, siblings, expected):
    assert _is_derivative_ticker(ticker, siblings) is expected


@pytest.fixture
def raw_frame(monkeypatch):
    def install(df):
        monkeypatch.setattr(tickers, "_get_company_tickers_raw", lambda: df)
        get_cik_ticker_lookup.cache_clear()
        return get_cik_ticker_lookup()
    yield install
    get_cik_ticker_lookup.cache_clear()


def test_otc_and_derivatives_are_demoted_but_a_missing_exchange_is_not(raw_frame):
    lookup = raw_frame(pd.DataFrame({
        'cik':      [1,      1,      2,       2,      3,       3],
        'ticker':   ["GWHT", "GWH",  "BEATW", "BEAT", "AFNX",  "AFNXU"],
        'exchange': ["OTC",  "NYSE", "Nasdaq", "Nasdaq", None, "Nasdaq"],
    }))
    assert lookup == {1: "GWH", 2: "BEAT", 3: "AFNX"}


def test_sec_api_frame_without_exchange_column_uses_listed_order(raw_frame):
    lookup = raw_frame(pd.DataFrame({
        'cik': [1, 1, 2, 2],
        'ticker': ["GOOGL", "GOOG", "SRG-PA", "SRG"],
    }))
    assert lookup == {1: "GOOGL", 2: "SRG"}
